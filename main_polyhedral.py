import sys
sys.path.append('/home/stefan/tamerlite')

import argparse
import z3
from unified_planning.shortcuts import *
from unified_planning.io import ANMLReader
from unified_planning.plans import TimeTriggeredPlan

import heapq

from tamerlite.core import wastar_search, astar_search, gbfs_search
from tamerlite.core import bfs_search, dfs_search, ehc_search
from tamerlite.core import multiqueue_search
from tamerlite.core import evaluate, make_fluent_node
from tamerlite.core import HFF, HAdd, CustomHeuristic, RLRank, RLHeuristic
from tamerlite.converter import Converter
from tamerlite.encoder import Encoder, get_encoders
from tamerlite.core.search import PrioritizedItem
from tamerlite.core.search_space import OperatorNode

from ContractPlatformPolyhedral import *



def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', type=argparse.FileType('r'), default=sys.stdin, metavar='domain',
        help="The abstract domain", dest='domain')
    parser.add_argument('-i', type=argparse.FileType('r'), default=sys.stdin, metavar='instance',
        help="The abstract instance", dest='instance')
    parser.add_argument('-o', type=argparse.FileType('w'), default=sys.stdout, metavar='output',
        help="The output file, defaults to the standard output", dest='output')
    res = parser.parse_args()
    return res


class Solver():
    def initialize_search(self, problem):
        self.encoder = Encoder(problem)
        self.bad_prefixes = []
        self.open = []
        self.heuristic = HFF(self.encoder.fluents, self.encoder.objects, self.encoder.events, self.encoder.goal)
        self.init = self.encoder.search_space.initial_state()
        init_h = self.heuristic.eval(self.init, self.encoder.search_space)
        if init_h is None:
            return False
        heapq.heappush(self.open, PrioritizedItem(init_h, self.init))
        return True
    
    def check_state_path(self, state):
        for prefix in self.bad_prefixes:
            if len(prefix) <= len(state.path):
                match = True
                for i in range(0, len(prefix)):
                    pre_event, pre_id = prefix[i]
                    path_event, path_id = state.path[i]
                    if (pre_event.action != path_event.action) or (pre_event.pos != path_event.pos):
                        match = False
                        break
                if match:
                    return False
        return True
    
    def search(self):
        while self.open:
            item = heapq.heappop(self.open)
            state = item.state
            if not self.check_state_path(state):
                continue
            if self.encoder.search_space.goal_reached(state):
                return state.temporal_network, state.path
            for succ_state in self.encoder.search_space.get_successor_states(state):
                if not self.check_state_path(succ_state):
                    continue
                h = self.heuristic.eval(succ_state, self.encoder.search_space)
                if h is not None:
                    f = 0.5*succ_state.g + 0.5*h
                    heapq.heappush(self.open, PrioritizedItem(f, succ_state))
        return None, None
    
    def get_lifted_name(self, action):
        lifted_action = self.map_back_action_instance(self.problem.action(action)())
        return lifted_action.action.name
    
    def generate_contract(self, name, pos):
        if name == "CHARGE":
            return CHRG_power(s=pos, generation=(4.0, 5.0))
        elif name == "DSN":
            return power_consumer(s=pos, task="DSN", consumption=(2.0, 2.2))
        elif name == "SBO":
            return power_consumer(s=pos, task="SBO", consumption=(0.1, 0.2))
        elif name == "TCM":
            return power_consumer(s=pos, task="TCM", consumption=(0.9, 1.1))
        else:
            raise Exception("Invalid action name")
    
    def generate_durations_contract(self, tn, path):
        tn_constraints = tn.get_constraints()
        input_vars = []
        assumptions = []
        for i in range(0, int(len(path)/2)):
            event, eventID = path[2*i]
            actionName = self.get_lifted_name(event.action)
            input_vars.append(f"duration_{actionName}{i}")
            startEvent = (event.action, True, eventID-1)
            endEvent = (event.action, False, eventID-1)
            for ev1 in tn_constraints:
                for (B, ev2) in tn_constraints[ev1]:
                    if ev1 == startEvent and ev2 == endEvent:
                        lb = -1 * B
                        assumptions.append(f"duration_{actionName}{i} >= {lb}")
                    elif ev1 == endEvent and ev2 == startEvent:
                        ub = B
                        assumptions.append(f"duration_{actionName}{i} <= {ub}")
        return PolyhedralIoContract.from_strings(input_vars=input_vars, output_vars=[], assumptions=assumptions, guarantees=[])
    
    def generate_safety_contract(self, steps):
        input_vars = ["soc0_entry"]
        output_vars = []
        assumptions = ["soc0_entry == 120"]
        guarantees = []
        for i in range(0, steps):
            output_vars.append(f"output_soc{i}")
            guarantees.append(f"output_soc{i} >= 40")
        return PolyhedralIoContract.from_strings(input_vars=input_vars, output_vars=output_vars, assumptions=assumptions, guarantees=guarantees)

    def build_durations_formula(self, quotientContract):
        formula = []
        for term in quotientContract.g.terms:
            summation = []
            varlist = list(term.variables.items())
            for var, coeff in varlist:
                summation.append(z3.RealVal(coeff) * z3.Real(var.name))
            formula.append(z3.Sum(summation) <= z3.RealVal(term.constant))
        return z3.And(formula)

    def extract_plan(self, path, model, planningProblem):
        plan_steps = []
        currentTime = Fraction(0)
        for i in range(0, int(len(path)/2)):
            event, eventID = path[2*i]
            actionName = self.get_lifted_name(event.action)
            duration = model[z3.Real(f"duration_{actionName}{i}")]
            plan_steps.append((currentTime, self.problem.action(event.action)(), duration.as_fraction()))
            currentTime = currentTime + duration.as_fraction() + 1
        plan = TimeTriggeredPlan(plan_steps)
        plan = plan.replace_action_instances(self.map_back_action_instance)
        return plan
    
    def validate(self, tn, path, planningProblem):
        contractSequence = []
        for i in range(0, int(len(path)/2)):
            event, eventID = path[2*i]
            actionName = self.get_lifted_name(event.action)
            contractSequence.append(self.generate_contract(actionName, i))

        for i in range(0, len(contractSequence)):
            print(f"contract {i}:")
            print(contractSequence[i])
            print("\n")

        composedContract = contractSequence[0]
        for i in range(1, len(contractSequence)):
            #try:
                composedContract = scenario_sequence(c1=composedContract, c2=contractSequence[i], variables=["soc"], c1index=i-1)
            # except:
            #     print("Bad prefix:")
            #     for (ev, id) in path[:(i+1)]:
            #         if ev.pos == 0:
            #             print(f"{ev.action} START")
            #         else:
            #             print(f"{ev.action} END")
            #     print("\n")
            #     return False, None, path[:(i+1)]
        composedContract = composedContract.rename_variables([(f"soc{len(contractSequence)-1}_exit", f"output_soc{len(contractSequence)-1}")])
        durationsContract = self.generate_durations_contract(tn, path)
        safetyContract = self.generate_safety_contract(int(len(path)/2))

        print("composedContract:")
        print(composedContract)
        print("\n")
        print("durationsContract:")
        print(durationsContract)
        print("\n")
        composedDurationsContract = composedContract.merge(durationsContract)
        print("composedDurationsContract:")
        print(composedDurationsContract)
        print("\n")
        print("safetyContract:")
        print(safetyContract)
        print("\n")
        try:
            quotientContract = safetyContract.quotient(composedDurationsContract)
        except:
            print("Bad prefix:")
            for (ev, id) in path:
                if ev.pos == 0:
                    print(f"{ev.action} START")
                else:
                    print(f"{ev.action} END")
            print("\n")
            return False, None, path
        print("quotientContract:")
        print(quotientContract)
        print("\n")
        durationsFormula = self.build_durations_formula(quotientContract)
        print("durationsFormula:")
        print(durationsFormula)
        print("\n")
        
        z3Solver = z3.Solver()
        z3Solver.add(durationsFormula)
        result = z3Solver.check()
        if result == z3.sat:
            plan = self.extract_plan(path, z3Solver.model(), planningProblem)
            return True, plan, None
        elif result == z3.unknown:
            raise ValueError("SMT solver could not check formula")
        else:
            return False, None, path

    def solve(self, planningDomain, planningInstance):
        reader = ANMLReader()
        planningProblem = reader.parse_problem([planningDomain.name, planningInstance.name])
        with planningProblem.environment.factory.Compiler(compilation_kind="GROUNDING", problem_kind=planningProblem.kind) as compiler:
            compilation_res = compiler.compile(planningProblem)
            self.map_back_action_instance = compilation_res.map_back_action_instance
        self.original_problem = planningProblem
        self.problem = compilation_res.problem
        if not self.initialize_search(self.problem):
            print("problem unsolvable")
            return

        counter = 0
        while True:
            counter += 1
            tn, path = self.search()
            print("candidate path:")
            for (ev, id) in path:
                if ev.pos == 0:
                    print(f"{ev.action} START")
                else:
                    print(f"{ev.action} END")
            print("\n")
            if tn is not None:
                outcome, sol, pre = self.validate(tn, path, self.problem)
                if outcome:
                    print(sol)
                    print(f"Number of loops: {counter}")
                    break
                else:
                    self.bad_prefixes.append(pre)
            else:
                print("problem unsolvable")


def main():
    args = parse_args()
    planningDomain = args.domain
    planningInstance = args.instance

    s = Solver()
    s.solve(planningDomain, planningInstance)

if __name__ == '__main__':
    main()