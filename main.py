import sys
sys.path.append('/home/stefan/tamerlite')
sys.path.insert(0, '/home/stefan/pacti/src')

import string
import secrets
import importlib
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

from pacti.contracts import SmtIoContract, PolyhedralIoContract


epsilon = 0.01

def gensym(length=32, prefix="gensym_"):
    alphabet = string.ascii_uppercase + string.ascii_lowercase + string.digits
    symbol = "".join([secrets.choice(alphabet) for i in range(length)])

    return prefix + symbol


def load_module(source, module_name=None):
    if module_name is None:
        module_name = gensym()

    spec = importlib.util.spec_from_file_location(module_name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return module

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', type=argparse.FileType('r'), default=sys.stdin, metavar='domain',
        help="The abstract domain", dest='domain')
    parser.add_argument('-i', type=argparse.FileType('r'), default=sys.stdin, metavar='instance',
        help="The abstract instance", dest='instance')
    parser.add_argument('-p', type=argparse.FileType('r'), default=sys.stdin, metavar='platform',
        help="The contract-based platform description", dest='platform')
    parser.add_argument('-o', type=argparse.FileType('w'), default=sys.stdout, metavar='output',
        help="The output file, defaults to the standard output", dest='output')
    res = parser.parse_args()
    return res


class Solver():
    def get_lifted_name(self, action):
        lifted_action = self.map_back_action_instance(self.problem.action(action)())
        return lifted_action.action.name

    def maximal_overlapping_seqs(self, seq):
        overlapping_seqs = []
        last_index = 0
        runningActions = set()
        for i in range(0, len(seq)):
            event, eventID = seq[i]
            if event.pos == 0:
                runningActions.add(event.action)
            else:
                runningActions.remove(event.action)
                if len(runningActions) == 0:
                    overlapping_seqs.append(seq[last_index:(i+1)])
                    last_index = i+1
        if last_index < len(seq):
            overlapping_seqs.append(seq[last_index:])
        return overlapping_seqs

    def initialize_search(self, problem):
        self.encoder = Encoder(problem)
        self.bad_prefixes = []
        self.bad_sequences = []
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
        for seq in self.bad_sequences:
            if len(seq) <= len(state.path):
                for i in range(0, len(state.path)-len(seq)+1):
                    match = True
                    for j in range(i, i+len(seq)):
                        seq_event, seq_id = seq[j-i]
                        path_event, path_id = state.path[j]
                        if (seq_event.action != path_event.action) or (seq_event.pos != path_event.pos):
                            match = False
                            break
                    if match:
                        return False
        overlappingSeqs = self.maximal_overlapping_seqs(state.path)
        if len(overlappingSeqs) == 0:
            return True
        lastOverlapping = overlappingSeqs[-1]
        if len(lastOverlapping) == 1:
            return True
        if len(lastOverlapping) == 2:
            ev1, evID1 = lastOverlapping[0]
            ev2, evID2 = lastOverlapping[1]
            if ev1.action == ev2.action:
                return True

        overlappingGood = False
        for allowedSeq in self.allowed_overlappings:
            if len(lastOverlapping) <= len(allowedSeq):
                goodMatch = True
                for i in range(0, len(lastOverlapping)):
                    event, eventID = lastOverlapping[i]
                    actionName = self.get_lifted_name(event.action)
                    if event.pos == 0:
                        actionName += "_start"
                    else:
                        actionName += "_end"
                    if actionName != allowedSeq[i]:
                        goodMatch = False
                        break
                if goodMatch:
                    overlappingGood = True
                    break
        return overlappingGood
    
    def search(self):
        while self.open:
            item = heapq.heappop(self.open)
            state = item.state
            if not self.check_state_path(state):
                # print("Bad path:")
                # print(state.path)
                continue
            if self.encoder.search_space.goal_reached(state):
                return state.temporal_network, state.path
            for succ_state in self.encoder.search_space.get_successor_states(state):
                if not self.check_state_path(succ_state):
                    # print("Bad path:")
                    # print(state.path)
                    continue
                h = self.heuristic.eval(succ_state, self.encoder.search_space)
                if h is not None:
                    f = 0.5*succ_state.g + 0.5*h
                    heapq.heappush(self.open, PrioritizedItem(f, succ_state))
        return None, None
    
    def rename_vars(self, c, stateIndex, timeIndex):
        varsRenamed = []
        for v in (c.inputvars + c.outputvars):
            if v.name.endswith("_entry"):
                varsRenamed.append((v.name, f"{(v.name)[:-5]}{stateIndex}"))
            elif v.name.endswith("_exit"):
                varsRenamed.append((v.name, f"{(v.name)[:-4]}{stateIndex+1}"))
            elif v.name.startswith("t_"):
                tIndex = ord((v.name)[2]) - ord('0') + timeIndex
                varsRenamed.append((v.name, "t_"+str(tIndex)))
            else:
                raise ValueError("Contract variables must be of type *_entry, *_exit, t_i")
        return c.rename_variables(varsRenamed)
    
    def generate_durations_contract(self, tn, path, platform, theory, indexOffset):
        tnConstraints = tn.get_constraints()
        input_vars = []
        assumptions = []
        eventIndex = {}
        #print("*****")
        for i in range(0, len(path)):
            event, eventID = path[i]
            if event.pos == 0:
                associatedEvent = (event.action, True, eventID-1)
            if event.pos == 1:
                associatedEvent = (event.action, False, eventID-2)
            eventIndex[path[i]] = i + indexOffset
            eventIndex[associatedEvent] = i + indexOffset
            input_vars.append(f"t_{i+indexOffset}")
            if theory == "SMT":
                t_i = z3.Real(f"t_{i+indexOffset}")
                assumptions.append(t_i >= 0)
                if i > 0:
                    t_i_prev = z3.Real(f"t_{i+indexOffset-1}")
                    assumptions.append(t_i_prev < t_i)
            elif theory == "POLYHEDRAL":
                #print(f"t_{i+indexOffset} >= 0")
                assumptions.append(f"t_{i+indexOffset} >= 0")
                if i > 0:
                    #print(f"t_{i+indexOffset-1} + {epsilon} <= t_{i+indexOffset}")
                    assumptions.append(f"t_{i+indexOffset-1} + {epsilon} <= t_{i+indexOffset}")
            else:
                raise ValueError(f"Theory {theory} not supported")
        for ev1 in tnConstraints:
            for (B, ev2) in tnConstraints[ev1]:
                if (ev1 in eventIndex) and (ev2 in eventIndex):
                    if theory == "SMT":
                        t1 = z3.Real(f"t_{eventIndex[ev1]}")
                        t2 = z3.Real(f"t_{eventIndex[ev2]}")
                        assumptions.append(t1 - t2 <= B)
                    elif theory == "POLYHEDRAL":
                        #print(f"t_{eventIndex[ev1]} - t_{eventIndex[ev2]} <= {float(B)}")
                        assumptions.append(f"t_{eventIndex[ev1]} - t_{eventIndex[ev2]} <= {float(B)}")
                    else:
                        raise ValueError(f"Theory {theory} not supported")

        if theory == "SMT":
            return SmtIoContract.from_z3_terms(input_vars=input_vars, output_vars=[], assumptions=assumptions, guarantees=[])
        elif theory == "POLYHEDRAL":
            return PolyhedralIoContract.from_strings(input_vars=input_vars, output_vars=[], assumptions=assumptions, guarantees=[])
        else:
            raise ValueError(f"Theory {theory} not supported")
    
    def generate_safety_contract(self, firstStep, finalStep, safetySpec, theory):
        safetySpec0 = self.rename_vars(safetySpec, 0, 0)
        input_vars = safetySpec0.inputvars
        output_vars = []
        guarantees = []
        if theory == "SMT":
            assumptions = [term.expression for term in safetySpec0.a.terms]
            for i in range(firstStep, finalStep):
                safetySpecI = self.rename_vars(safetySpec, i, 0)
                output_vars.extend(safetySpecI.outputvars)
                guarantees.extend([term.expression for term in safetySpecI.g.terms])
            return SmtIoContract.from_z3_terms(input_vars=input_vars, output_vars=output_vars, assumptions=assumptions, guarantees=guarantees)
        elif theory == "POLYHEDRAL":
            assumptions = safetySpec0.a.to_str_list()
            for i in range(firstStep, finalStep):
                safetySpecI = self.rename_vars(safetySpec, i, 0)
                output_vars.extend(safetySpecI.outputvars)
                guarantees.extend(safetySpecI.g.to_str_list())
            return PolyhedralIoContract.from_strings(input_vars=input_vars, output_vars=output_vars, assumptions=assumptions, guarantees=guarantees)
        else:
            raise ValueError(f"Theory {theory} not supported")
    
    def check_merged_contract(self, mergedContract, theory):
        if theory == "SMT":
            assumptionsFormula = z3.And(*[term.expression for term in mergedContract.a.terms])
        elif theory == "POLYHEDRAL":
            formula = []
            for term in mergedContract.a.terms:
                summation = []
                varlist = list(term.variables.items())
                for var, coeff in varlist:
                    summation.append(z3.RealVal(coeff) * z3.Real(var.name))
                formula.append(z3.Sum(summation) <= z3.RealVal(term.constant))
            assumptionsFormula = z3.And(formula)
        else:
            raise ValueError(f"Theory {theory} not supported")
        
        z3Solver = z3.Solver()
        z3Solver.add(assumptionsFormula)
        result = z3Solver.check()
        if result == z3.sat:
            return True
        elif result == z3.unknown:
            raise ValueError("SMT solver could not check formula")
        else:
            return False
    
    def build_durations_formula(self, quotientContract, theory):
        if theory == "SMT":
            return z3.And(*[term.expression for term in quotientContract.g.terms])
        elif theory == "POLYHEDRAL":
            formula = []
            for term in quotientContract.g.terms:
                summation = []
                varlist = list(term.variables.items())
                for var, coeff in varlist:
                    summation.append(z3.RealVal(coeff) * z3.Real(var.name))
                formula.append(z3.Sum(summation) <= z3.RealVal(term.constant))
            return z3.And(formula)
        else:
            raise ValueError(f"Theory {theory} not supported")

    def extract_plan(self, path, model, planningProblem):
        plan_steps = []
        start_times = {}
        for i in range(0, len(path)):
            ev, ev_id = path[i]
            t_i = model[z3.Real(f"t_{i}")].as_fraction()
            if ev.pos == 0:
                start_times[ev.action] = t_i
            else:
                dur = t_i - start_times[ev.action]
                plan_steps.append((start_times[ev.action], self.problem.action(ev.action)(), dur))
        plan = TimeTriggeredPlan(plan_steps)
        plan = plan.replace_action_instances(self.map_back_action_instance)
        return plan

    def find_bad_seq(self, tn, path, platform, overlappingSeqs):
        print("Analyzing prefix")
        currentTimepoint = 0
        for i in range(0, len(overlappingSeqs)):
            currentTimepoint += len(overlappingSeqs[i])
        for i in range(len(overlappingSeqs)-1, 0, -1):
            print(f"i = {i}")
            seq = overlappingSeqs[i]
            currentTimepoint -= len(seq)
            if len(seq) == 2:
                event, eventID = seq[0]
                actionName = self.get_lifted_name(event.action)
                newContract = platform[actionName]
            else:
                actionList = []
                for (event, eventID) in seq:
                    actionName = self.get_lifted_name(event.action)
                    if event.pos == 0:
                        actionName += "_start"
                    else:
                        actionName += "_end"
                    actionList.append(actionName)
                newContract = platform["CONCURRENCY"][tuple(actionList)][1]
            
            if i == len(overlappingSeqs)-1:
                composedContract = self.rename_vars(newContract, i, currentTimepoint)
            else:
                newContractRenamed = self.rename_vars(newContract, i, currentTimepoint)
                print("Composing:")
                print(newContractRenamed)
                print(composedContract)
                try:
                    composedContract = newContractRenamed.compose(composedContract, vars_to_keep=newContractRenamed.outputvars)
                except:
                    print("Bad sequence:")
                    for j in range(currentTimepoint, len(path)):
                        ev, evID = path[j]
                        if ev.pos == 0:
                            print(f"{ev.action} START")
                        else:
                            print(f"{ev.action} END")
                    print("\n")
                    return path[currentTimepoint:]
            
            print("composedContract:")
            print(composedContract)
            durationsContract = self.generate_durations_contract(tn, path[currentTimepoint:], platform, platform["theory"], currentTimepoint)
            print("durationsContract:")
            print(durationsContract)
            safetyContract = self.generate_safety_contract(i, len(overlappingSeqs), platform["SAFETY"], platform["theory"])
            print("safetyContract:")
            print(safetyContract)

            try:
                composedDurationsContract = composedContract.merge(durationsContract)
            except:
                print("Bad sequence:")
                for j in range(currentTimepoint, len(path)):
                    ev, evID = path[j]
                    if ev.pos == 0:
                        print(f"{ev.action} START")
                    else:
                        print(f"{ev.action} END")
                print("\n")
                return path[currentTimepoint:]
            if not self.check_merged_contract(composedDurationsContract, platform["theory"]):
                print("Bad sequence:")
                for j in range(currentTimepoint, len(path)):
                    ev, evID = path[j]
                    if ev.pos == 0:
                        print(f"{ev.action} START")
                    else:
                        print(f"{ev.action} END")
                print("\n")
                return path[currentTimepoint:]
            
            try:
                quotientContract = safetyContract.quotient(composedDurationsContract)
            except:
                print("Bad sequence:")
                for j in range(currentTimepoint, len(path)):
                    ev, evID = path[j]
                    if ev.pos == 0:
                        print(f"{ev.action} START")
                    else:
                        print(f"{ev.action} END")
                print("\n")
                return path[currentTimepoint:]
            print("quotientContract:")
            print(quotientContract)
        return None
    
    def validate(self, tn, path, planningProblem, platform):
        overlappingSeqs = self.maximal_overlapping_seqs(path)
        print("overlappingSeqs:")
        for seq in overlappingSeqs:
            for (ev, id) in seq:
                if ev.pos == 0:
                    print(f"{ev.action} START")
                else:
                    print(f"{ev.action} END")
            print("-----")
        currentTimepoint = 0
        for i in range(0, len(overlappingSeqs)):
            print(f"i = {i}")
            seq = overlappingSeqs[i]
            if len(seq) == 2:
                event, eventID = seq[0]
                actionName = self.get_lifted_name(event.action)
                newContract = platform[actionName]
            else:
                actionList = []
                for (event, eventID) in seq:
                    actionName = self.get_lifted_name(event.action)
                    if event.pos == 0:
                        actionName += "_start"
                    else:
                        actionName += "_end"
                    actionList.append(actionName)
                newContract = platform["CONCURRENCY"][tuple(actionList)][1]
            
            if i == 0:
                composedContract = self.rename_vars(newContract, i, currentTimepoint)
                currentTimepoint += len(seq)
            else:
                newContractRenamed = self.rename_vars(newContract, i, currentTimepoint)
                currentTimepoint += len(seq)
                print("Composing:")
                print(composedContract)
                print(newContractRenamed)
                try:
                    composedContract = composedContract.compose(newContractRenamed, vars_to_keep=composedContract.outputvars)
                except:
                    print("Bad prefix:")
                    for (ev, id) in path[:currentTimepoint]:
                        if ev.pos == 0:
                            print(f"{ev.action} START")
                        else:
                            print(f"{ev.action} END")
                    print("\n")
                    badSeq = self.find_bad_seq(tn, path[:currentTimepoint], platform, overlappingSeqs[:(i+1)])
                    return False, None, path[:currentTimepoint], badSeq
            
            print("composedContract:")
            print(composedContract)
            durationsContract = self.generate_durations_contract(tn, path[:currentTimepoint], platform, platform["theory"], 0)
            print("durationsContract:")
            print(durationsContract)
            safetyContract = self.generate_safety_contract(0, i+1, platform["SAFETY"], platform["theory"])
            print("safetyContract:")
            print(safetyContract)

            try:
                composedDurationsContract = composedContract.merge(durationsContract)
            except:
                print("Bad prefix:")
                for (ev, id) in path[:currentTimepoint]:
                    if ev.pos == 0:
                        print(f"{ev.action} START")
                    else:
                        print(f"{ev.action} END")
                print("\n")
                badSeq = self.find_bad_seq(tn, path[:currentTimepoint], platform, overlappingSeqs[:(i+1)])
                return False, None, path[:currentTimepoint], badSeq
            if not self.check_merged_contract(composedDurationsContract, platform["theory"]):
                print("Bad prefix:")
                for (ev, id) in path[:currentTimepoint]:
                    if ev.pos == 0:
                        print(f"{ev.action} START")
                    else:
                        print(f"{ev.action} END")
                print("\n")
                badSeq = self.find_bad_seq(tn, path[:currentTimepoint], platform, overlappingSeqs[:(i+1)])
                return False, None, path[:currentTimepoint], badSeq
            
            try:
                quotientContract = safetyContract.quotient(composedDurationsContract)
            except:
                print("Bad prefix:")
                for (ev, id) in path[:currentTimepoint]:
                    if ev.pos == 0:
                        print(f"{ev.action} START")
                    else:
                        print(f"{ev.action} END")
                print("\n")
                badSeq = self.find_bad_seq(tn, path[:currentTimepoint], platform, overlappingSeqs[:(i+1)])
                return False, None, path[:currentTimepoint], badSeq
            print("composedDurationsContract:")
            print(composedDurationsContract)
            print("quotientContract:")
            print(quotientContract)
            print("\n")
            resultingSystemContract = quotientContract.compose(composedDurationsContract)
            assert resultingSystemContract.refines(safetyContract)
        
        durationsFormula = self.build_durations_formula(quotientContract, platform["theory"])
        print("durationsFormula:")
        print(durationsFormula)
        print("\n")
        
        z3Solver = z3.Solver()
        z3Solver.add(durationsFormula)
        result = z3Solver.check()
        if result == z3.sat:
            plan = self.extract_plan(path, z3Solver.model(), planningProblem)
            return True, plan, None, None
        elif result == z3.unknown:
            raise ValueError("SMT solver could not check formula")
        else:
            raise ValueError("Empty quotient returned")

    def solve(self, planningDomain, planningInstance, platform):
        reader = ANMLReader()
        planningProblem = reader.parse_problem([planningDomain.name, planningInstance.name])
        with planningProblem.environment.factory.Compiler(compilation_kind="GROUNDING", problem_kind=planningProblem.kind) as compiler:
            compilation_res = compiler.compile(planningProblem)
            self.map_back_action_instance = compilation_res.map_back_action_instance
        self.original_problem = planningProblem
        self.problem = compilation_res.problem
        self.allowed_overlappings = list(platform["CONCURRENCY"].keys())
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
                outcome, sol, pre, seq = self.validate(tn, path, self.problem, platform)
                if outcome:
                    print(sol)
                    print(f"Number of loops: {counter}")
                    break
                else:
                    self.bad_prefixes.append(pre)
                    if seq != None:
                        self.bad_sequences.append(seq)
            else:
                print("problem unsolvable")


def main():
    args = parse_args()
    planningDomain = args.domain
    planningInstance = args.instance
    platform = load_module(args.platform.name).platform

    s = Solver()
    s.solve(planningDomain, planningInstance, platform)

if __name__ == '__main__':
    main()