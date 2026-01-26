import sys
sys.path.insert(1, '/home/stefan/tamerlite')

import argparse
import pysmt
from pyvmt.vmtlib.reader import read
from pyvmt.solvers.ic3ia import Ic3iaSolver
from pyvmt.model import Model
import pyvmt.shortcuts as vmtshortcuts
from unified_planning.shortcuts import *
from unified_planning.io import ANMLReader
from unified_planning.plans import TimeTriggeredPlan
from unified_planning.model.walkers import AnyChecker
import pysmt.shortcuts as pyshortcuts
from pysmt.shortcuts import qelim
import pysmt.typing as types
# from tempest.encoders import MonolithicEncoder

import heapq

from tamerlite.core import wastar_search, astar_search, gbfs_search
from tamerlite.core import bfs_search, dfs_search, ehc_search
from tamerlite.core import multiqueue_search
from tamerlite.core import evaluate, make_fluent_node
from tamerlite.core import HFF, HAdd, CustomHeuristic
from tamerlite.converter import Converter
from tamerlite.encoder import Encoder, get_encoders
from tamerlite.core.search import PrioritizedItem
from tamerlite.core.search_space import OperatorNode


QELIM_SOLVER = "z3"

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', type=argparse.FileType('r'), default=sys.stdin, metavar='domain',
        help="The abstract domain", dest='domain')
    parser.add_argument('-i', type=argparse.FileType('r'), default=sys.stdin, metavar='instance',
        help="The abstract instance", dest='instance')
    parser.add_argument('-p', type=argparse.FileType('r'), default=sys.stdin, metavar='platform',
        help="The platform model", dest='platform')
    parser.add_argument('-f', '--future', action='store_true')
    parser.add_argument('-s', '--futuresafety', action='store_true')
    parser.add_argument('-o', type=argparse.FileType('w'), default=sys.stdout, metavar='output',
        help="The output file, defaults to the standard output", dest='output')
    res = parser.parse_args()
    return res

class Solver():
    def generalize_seq(self, seq):
        generalizedSeq = []
        parameterChecker = AnyChecker(lambda e: e.is_parameter_exp())
        for (event, eventID) in seq:
            liftedAction = self.map_back_action_instance(self.problem.action(event.action)())
            if parameterChecker.any(liftedAction._action.duration.lower) or parameterChecker.any(liftedAction._action.duration.upper):
                generalizedSeq.append((event, eventID, False))
            else:
                generalizedSeq.append((event, eventID, True))
        return generalizedSeq

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
                    pre_event, pre_id, lifted = prefix[i]
                    path_event, path_id = state.path[i]
                    if lifted:
                        liftedActionPre = self.get_lifted_name(pre_event.action)
                        liftedActionPath = self.get_lifted_name(path_event.action)
                        if (liftedActionPre != liftedActionPath) or (pre_event.pos != path_event.pos):
                            match = False
                            break
                    else:
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
    
    def build_automaton(self, pysmtEnv, path, last_idx, future_indexes, psi, platformModel, futureSafety):
        mgr = pysmtEnv.formula_manager

        productModel = Model()
        for var in platformModel.get_state_vars():
            productModel.add_state_var(var)
        for var in platformModel.get_input_vars():
            productModel.add_input_var(var)
        for f in platformModel.get_init_constraints():
            productModel.add_init(f)
        for f in platformModel.get_trans_constraints():
            productModel.add_trans(f)

        planLocation = productModel.create_state_var('planLocation', types.REAL)
        planLocationNext = vmtshortcuts.Next(planLocation)
        planLocationRange = []
        planLocationNextRange = []
        for i in range(0, last_idx+len(future_indexes)+3):
            planLocationRange.append(mgr.Equals(planLocation, mgr.Real(i)))
            planLocationNextRange.append(mgr.Equals(planLocationNext, mgr.Real(i)))
        productModel.add_init(mgr.Or(planLocationRange))
        productModel.add_trans(mgr.Or(planLocationRange))
        productModel.add_trans(mgr.Or(planLocationNextRange))

        planEvent = productModel.create_input_var('planEvent', types.REAL)
        planEventRange = []
        for i in range(0, last_idx+1):
            planEventRange.append(mgr.Equals(planEvent, mgr.Real(i)))
        for i in future_indexes:
            planEventRange.append(mgr.Equals(planEvent, mgr.Real(i)))
        planEventRange.append(mgr.Equals(planEvent, mgr.Real(len(path))))
        planEventRange.append(mgr.Equals(planEvent, mgr.Real(len(path)+1)))
        productModel.add_trans(mgr.Or(planEventRange))

        for i in range(0, last_idx+1):
            productModel.create_frozen_var(f"t@{i}", types.REAL)
        for i in future_indexes:
            productModel.create_frozen_var(f"t@{i}", types.REAL)
        productModel.add_init(mgr.Equals(planLocation, mgr.Real(0)))
        productModel.add_init(psi)

        timeVar = mgr.Symbol(f"time__AT0", types.REAL)
        timeNextVar = vmtshortcuts.Next(timeVar)
        global_clock = mgr.Symbol(f"global_clock__AT0", types.REAL)
        global_clock_next = vmtshortcuts.Next(global_clock)

        for i in range(0, last_idx+1):
            t_i = mgr.Symbol(f"t@{i}", types.REAL)
            productModel.add_init(mgr.Implies(mgr.Equals(planLocation, mgr.Real(i)), mgr.LE(global_clock, t_i)))
            productModel.add_trans(mgr.Implies(mgr.Equals(planLocation, mgr.Real(i)), mgr.LE(global_clock, t_i)))
            productModel.add_trans(mgr.Implies(mgr.Equals(planLocationNext, mgr.Real(i)), mgr.LE(global_clock_next, t_i)))
        for i in range(last_idx+1, last_idx+len(future_indexes)+1):
            invariant = []
            invariantNext = []
            for j in future_indexes:
                t_j = mgr.Symbol(f"t@{j}", types.REAL)
                if len(future_indexes) == 1:
                    invariant.append(mgr.Implies(mgr.Equals(planLocation, mgr.Real(i)), mgr.LE(global_clock, t_j)))
                    invariantNext.append(mgr.Implies(mgr.Equals(planLocationNext, mgr.Real(i)), mgr.LE(global_clock_next, t_j)))
                else:
                    ite_list = []
                    for k in future_indexes:
                        if k != j:
                            t_k = mgr.Symbol(f"t@{k}", types.REAL)
                            ite_list.append(mgr.Ite(mgr.LT(t_k, t_j), mgr.Real(1), mgr.Real(0)))
                    invariant.append(mgr.Implies(mgr.And(mgr.Equals(planLocation, mgr.Real(i)), mgr.Equals(mgr.Plus(ite_list), mgr.Real(i-last_idx-1))), mgr.LE(global_clock, t_j)))
                    invariantNext.append(mgr.Implies(mgr.And(mgr.Equals(planLocationNext, mgr.Real(i)), mgr.Equals(mgr.Plus(ite_list), mgr.Real(i-last_idx-1))), mgr.LE(global_clock_next, t_j)))
            productModel.add_init(mgr.And(invariant))
            productModel.add_trans(mgr.And(invariant))
            productModel.add_trans(mgr.And(invariantNext))

        for i in range(0, last_idx+1):
            t_i = mgr.Symbol(f"t@{i}", types.REAL)
            transFormula = mgr.Implies(mgr.Equals(planEvent, mgr.Real(i)),
                                       mgr.And(mgr.Equals(planLocation, mgr.Real(i)),
                                               mgr.Equals(planLocationNext, mgr.Real(i+1)),
                                               mgr.Equals(global_clock, t_i)))
            productModel.add_trans(mgr.Implies(mgr.Equals(timeVar, timeNextVar), transFormula))
        for i in future_indexes:
            t_i = mgr.Symbol(f"t@{i}", types.REAL)
            disjunction = []
            for j in range(last_idx+1, last_idx+len(future_indexes)+1):
                if len(future_indexes) == 1:
                    disjunction.append(mgr.And(mgr.Equals(planLocation, mgr.Real(j)),
                                               mgr.Equals(planLocationNext, mgr.Real(j+1)),
                                               mgr.Equals(global_clock, t_i)))
                else:
                    ite_list = []
                    for k in future_indexes:
                        if k != i:
                            t_k = mgr.Symbol(f"t@{k}", types.REAL)
                            ite_list.append(mgr.Ite(mgr.LT(t_k, t_i), mgr.Real(1), mgr.Real(0)))
                    disjunction.append(mgr.And(mgr.Equals(planLocation, mgr.Real(j)),
                                            mgr.Equals(planLocationNext, mgr.Real(j+1)),
                                            mgr.Equals(global_clock, t_i),
                                            mgr.Equals(mgr.Plus(ite_list), mgr.Real(j-last_idx-1))))
            transFormula = mgr.Implies(mgr.Equals(planEvent, mgr.Real(i)), mgr.Or(disjunction))
            productModel.add_trans(mgr.Implies(mgr.Equals(timeVar, timeNextVar), transFormula))

        transFormula = mgr.Implies(mgr.Equals(planEvent, mgr.Real(len(path)+1)), mgr.Equals(planLocation, planLocationNext))
        productModel.add_trans(mgr.Implies(mgr.Equals(timeVar, timeNextVar), transFormula))

        for i in range(0, last_idx+1):
            event, ev_id = path[i]
            lifted_name = self.get_lifted_name(event.action)
            if event.pos == 0:
                tau = mgr.Symbol(f"t{lifted_name}.start__AT0")
            elif event.pos == 1:
                tau = mgr.Symbol(f"t{lifted_name}.end__AT0")
            else:
                raise Exception("Event with pos > 0")
            transFormula = mgr.Implies(mgr.Equals(planEvent, mgr.Real(i)), tau)
            productModel.add_trans(mgr.Implies(mgr.Equals(timeVar, timeNextVar), transFormula))
        for i in future_indexes:
            event, ev_id = path[i]
            lifted_name = self.get_lifted_name(event.action)
            if event.pos == 0:
                tau = mgr.Symbol(f"t{lifted_name}.start__AT0")
            elif event.pos == 1:
                tau = mgr.Symbol(f"t{lifted_name}.end__AT0")
            else:
                raise Exception("Event with pos > 0")
            transFormula = mgr.Implies(mgr.Equals(planEvent, mgr.Real(i)), tau)
            productModel.add_trans(mgr.Implies(mgr.Equals(timeVar, timeNextVar), transFormula))

        for a in self.original_problem.actions:
            lifted_action_name = a.name
            tau_a_start = mgr.Symbol(f"t{lifted_action_name}.start__AT0")
            tau_a_end = mgr.Symbol(f"t{lifted_action_name}.end__AT0")
            start_event = []
            end_event = []
            for i in range(0, last_idx+1):
                event, ev_id = path[i]
                lifted_name = self.get_lifted_name(event.action)
                if lifted_name == lifted_action_name:
                    if event.pos == 0:
                        start_event.append(mgr.Equals(planEvent, mgr.Real(i)))
                    elif event.pos == 1:
                        end_event.append(mgr.Equals(planEvent, mgr.Real(i)))
                    else:
                        raise Exception("Event with pos > 0")
            for i in future_indexes:
                event, ev_id = path[i]
                lifted_name = self.get_lifted_name(event.action)
                if lifted_name == lifted_action_name:
                    if event.pos == 0:
                        start_event.append(mgr.Equals(planEvent, mgr.Real(i)))
                    elif event.pos == 1:
                        end_event.append(mgr.Equals(planEvent, mgr.Real(i)))
                    else:
                        raise Exception("Event with pos > 0")
            transFormulaStart = mgr.Implies(tau_a_start, mgr.Or(start_event))
            transFormulaEnd = mgr.Implies(tau_a_end, mgr.Or(end_event))
            productModel.add_trans(mgr.Implies(mgr.Equals(timeVar, timeNextVar), transFormulaStart))
            productModel.add_trans(mgr.Implies(mgr.Equals(timeVar, timeNextVar), transFormulaEnd))
        
        for var in productModel.get_state_vars():
            if var.symbol_name().startswith('__PLANNING__'):
                effect_pos = set()
                varNext = vmtshortcuts.Next(var)
                planning_var_name = (var.symbol_name())[12:(len(var.symbol_name())-5)]
                if type(self.init.get_value(planning_var_name)) is bool:
                    if self.init.get_value(planning_var_name):
                        productModel.add_init(mgr.Symbol(var.symbol_name(), types.BOOL))
                    else:
                        productModel.add_init(mgr.Not(mgr.Symbol(var.symbol_name(), types.BOOL)))
                elif (type(self.init.get_value(planning_var_name)) is int) or (type(self.init.get_value(planning_var_name)) is float):
                     productModel.add_init(mgr.Equals(mgr.Symbol(var.symbol_name(), types.REAL), mgr.Real(self.init.get_value(planning_var_name))))
                else:
                    raise Exception("The supported types for __PLANNING__ vars are only bool, int and float")
                for i in range(0, len(path)):
                    event, ev_id = path[i]
                    added = False
                    for effect in event.effects:
                        if effect.fluent == planning_var_name:
                            if not added:
                                effect_pos.add(i)
                                added = True
                            op = 0
                            for e in effect.value:
                                if isinstance(e, OperatorNode):
                                    if e.kind == "+":
                                        op = 1
                                        break
                                    elif e.kind == "-":
                                        op = 2
                                        break
                                    else:
                                        raise Exception("Effects on shared vars can only be assignments of constants or additions/subtractions")
                            if op == 0:
                                if type((effect.value)[0]) is bool:
                                    transFormula = mgr.Implies(mgr.Equals(planEvent, mgr.Real(i)),
                                                               mgr.Equals(varNext, mgr.Bool((effect.value)[0])))
                                elif (type((effect.value)[0]) is int) or (type((effect.value)[0]) is float):
                                    transFormula = mgr.Implies(mgr.Equals(planEvent, mgr.Real(i)),
                                                               mgr.Equals(varNext, mgr.Real((effect.value)[0])))
                                else:
                                    raise Exception("Effects on shared vars can only be assignments of bool/int/float constants or additions/subtractions")
                            elif op == 1:
                                if len(effect.value) != 3:
                                    raise Exception("Addition effects on shared vars can only be in the form x := x + c")
                                v = (effect.value)[0]
                                c = (effect.value)[1]
                                if v != planning_var_name:
                                    raise Exception("Addition effects on shared vars can only be in the form x := x + c")
                                if not ((type(c) is int) or (type(c) is float)):
                                    raise Exception("Addition effects on shared vars can only be in the form x := x + c")
                                transFormula = mgr.Implies(mgr.Equals(planEvent, mgr.Real(i)),
                                                           mgr.Equals(varNext, mgr.Plus(var, mgr.Real(c))))
                            elif op == 2:
                                if len(effect.value) != 3:
                                    raise Exception("Subtraction effects on shared vars can only be in the form x := x - c")
                                v = (effect.value)[0]
                                c = (effect.value)[1]
                                if v != planning_var_name:
                                    raise Exception("Subtraction effects on shared vars can only be in the form x := x - c")
                                if not ((type(c) is int) or (type(c) is float)):
                                    raise Exception("Subtraction effects on shared vars can only be in the form x := x - c")
                                transFormula = mgr.Implies(mgr.Equals(planEvent, mgr.Real(i)),
                                                           mgr.Equals(varNext, mgr.Minus(var, mgr.Real(c))))
                            else:
                                raise Exception("Unknown effect on shared var")
                            productModel.add_trans(mgr.Implies(mgr.Equals(timeVar, timeNextVar), transFormula))
                disjunction = []
                for i in effect_pos:
                    disjunction.append(mgr.Equals(planEvent, mgr.Real(i)))
                transFormula = mgr.Implies(mgr.Not(mgr.Equals(var, varNext)), mgr.Or(disjunction))
                productModel.add_trans(mgr.Implies(mgr.Equals(timeVar, timeNextVar), transFormula))
                productModel.add_trans(mgr.Implies(mgr.Not(mgr.Equals(timeVar, timeNextVar)), mgr.Equals(var, varNext)))

        productModel.add_trans(mgr.Implies(mgr.Not(mgr.Equals(timeVar, timeNextVar)),
                                           mgr.Equals(planLocation, planLocationNext)))

        productModelStateVars = productModel.get_state_vars()
        productModelInputVars = productModel.get_input_vars()
        time_subs = {}
        existVars = []
        for v in productModelStateVars:
            next_v = vmtshortcuts.Next(v)
            v_prime = mgr.Symbol("%s@prime" % (v.symbol_name()), v.symbol_type())
            time_subs[next_v] = v_prime
            if v.symbol_name() == '__iota__AT0':
                time_subs[v] = mgr.Bool(True)
            if v.symbol_name().endswith(".start__AT0") or v.symbol_name().endswith(".end__AT0"):
                existVars.append(v)
            existVars.append(v_prime)
        for v in productModelInputVars:
            next_v = vmtshortcuts.Next(v)
            v_prime = mgr.Symbol("%s@prime" % (v.symbol_name()), v.symbol_type())
            time_subs[next_v] = v_prime
            if v.symbol_name() == '__delta__AT0':
                time_subs[v] = mgr.Real(0)
                existVars.append(v_prime)
            elif v.symbol_name() == 'planEvent':
                existVars.append(v_prime)
            else:
                existVars.append(v)
                existVars.append(v_prime)
        trans = mgr.And(productModel.get_trans_constraints()).substitute(time_subs)
        # print("exist formula:")
        # print(mgr.Exists(existVars, trans).serialize())
        print("qelim trans start")
        exist_trans = qelim(mgr.Exists(existVars, trans), solver_name=QELIM_SOLVER).simplify()
        print("qelim trans end")
        error_transition = []
        for i in range(0, last_idx+1):
            t_i = mgr.Symbol(f"t@{i}", types.REAL)
            subs = {}
            for v in productModelInputVars:
                if v.symbol_name() == 'planEvent':
                    subs[v] = mgr.Real(i)
            exist_trans_i = exist_trans.substitute(subs).simplify()
            error_transition.append(mgr.And(mgr.Equals(planLocation, mgr.Real(i)),
                                            mgr.Equals(planLocationNext, mgr.Real(last_idx+len(future_indexes)+2)),
                                            mgr.Equals(global_clock, t_i),
                                            mgr.Not(exist_trans_i)))
        for i in future_indexes:
            for j in range(last_idx+1, last_idx+len(future_indexes)+1):
                t_i = mgr.Symbol(f"t@{i}", types.REAL)
                subs = {}
                for v in productModelInputVars:
                    if v.symbol_name() == 'planEvent':
                        subs[v] = mgr.Real(i)
                exist_trans_i = exist_trans.substitute(subs).simplify()
                if len(future_indexes) == 1:
                    error_transition.append(mgr.And(mgr.Equals(planLocation, mgr.Real(j)),
                                                    mgr.Equals(planLocationNext, mgr.Real(last_idx+len(future_indexes)+2)),
                                                    mgr.Equals(global_clock, t_i),
                                                    mgr.Not(exist_trans_i)))
                else:
                    ite_list = []
                    for k in future_indexes:
                        if k != i:
                            t_k = mgr.Symbol(f"t@{k}", types.REAL)
                            ite_list.append(mgr.Ite(mgr.LT(t_k, t_i), mgr.Real(1), mgr.Real(0)))
                    error_transition.append(mgr.And(mgr.Equals(planLocation, mgr.Real(j)),
                                                    mgr.Equals(planLocationNext, mgr.Real(last_idx+len(future_indexes)+2)),
                                                    mgr.Equals(global_clock, t_i),
                                                    mgr.Equals(mgr.Plus(ite_list), mgr.Real(j-last_idx-1)),
                                                    mgr.Not(exist_trans_i)))

        transFormula = mgr.Implies(mgr.Equals(planEvent, mgr.Real(len(path))), mgr.Or(error_transition))
        productModel.add_trans(mgr.Implies(mgr.Equals(timeVar, timeNextVar), transFormula))

        props = platformModel.get_invar_properties()
        t_last = mgr.Symbol(f"t@{last_idx}", types.REAL)
        for idx in props:
            if futureSafety:
                productModel.add_invar_property(props[idx].formula)
            else:
                productModel.add_invar_property(mgr.Implies(mgr.LE(global_clock, t_last), props[idx].formula)) 
        
        productModel.add_invar_property(mgr.Not(mgr.Equals(planLocation, mgr.Real(last_idx+len(future_indexes)+2))))
        return productModel

    def check_model(self, productModel):
        solver = Ic3iaSolver(productModel)
        # productModel.serialize(sys.stdout)
        # print("Init:")
        # print(productModel.get_init_constraint().serialize())
        # print("Trans:")
        # print(productModel.get_trans_constraint().serialize())
        results = solver.check_properties()
        if results[0].is_unsafe():
            return False, results[0].get_trace()
        if results[1].is_unsafe():
            return False, results[1].get_trace()
        return True, None

    def extract_plan(self, pysmtEnv, path, psi):
        mgr = pysmtEnv.formula_manager
        with pysmtEnv.factory.Solver(logic="QF_LRA", random_seed=73) as smt:
            smt.add_assertion(psi)
            if smt.solve():
                model = smt.get_model()
                plan_steps = []
                start_times = {}
                for i in range(0, len(path)):
                    ev, ev_id = path[i]
                    t_i = mgr.Symbol(f"t@{i}", types.REAL)
                    if ev.pos == 0:
                        start_times[ev.action] = model.get_py_value(t_i)
                    elif ev.pos == 1:
                        dur = model.get_py_value(t_i) - start_times[ev.action]
                        plan_steps.append((Fraction(start_times[ev.action]), self.problem.action(ev.action)(), Fraction(dur)))
                    else:
                        raise Exception("Event with pos > 1")
                plan = TimeTriggeredPlan(plan_steps)
                plan = plan.replace_action_instances(self.map_back_action_instance)
                return plan
            else:
                raise Exception("psi UNSAT but was previously SAT")

    def get_subs(self, pysmtEnv, vars, i):
        mgr = pysmtEnv.formula_manager
        subs_i = {}
        for v in vars:
            next_v = vmtshortcuts.Next(v)
            if v.symbol_name().startswith("t@"):
                v_i = v
                v_iplus1 = v
            else:
                v_i = mgr.Symbol("%s@%d" % (v.symbol_name(), i), v.symbol_type())
                v_iplus1 = mgr.Symbol("%s@%d" % (v.symbol_name(), i+1), v.symbol_type())
            subs_i[v] = v_i
            subs_i[next_v] = v_iplus1
        return subs_i
    
    def encode_bmc(self, pysmtEnv, productModel, h):
        mgr = pysmtEnv.formula_manager
        productModelVars = productModel.get_state_vars()
        productModelVars.extend(productModel.get_input_vars())
        init = mgr.And(productModel.get_init_constraints()).substitute(self.get_subs(pysmtEnv, productModelVars, 0))
        trans = []
        for i in range(0, h-1):
            subs = self.get_subs(pysmtEnv, productModelVars, i)
            trans_i = mgr.And(productModel.get_trans_constraints()).substitute(subs)
            trans.append(trans_i)
        bmc = mgr.And(init, mgr.And(trans))
        return bmc

    def update_psi(self, pysmtEnv, productModel, path, last_idx, psi, trace):
        mgr = pysmtEnv.formula_manager
        bmc = self.encode_bmc(pysmtEnv, productModel, trace.steps_count())
        subs = {}
        existVars = []
        for i in range(0, trace.steps_count()):
            step_i = trace.get_step(i)
            for svar in productModel.get_state_vars():
                if not svar.symbol_name().startswith('t@'):
                    svar_i = mgr.Symbol("%s@%d" % (svar.symbol_name(), i), svar.symbol_type())
                    if svar.symbol_name() != 'time__AT0' and svar.symbol_name() != 'global_clock__AT0' and ('__CLOCK__' not in svar.symbol_name()):
                        subs[svar_i] = step_i.get_assignment(svar)
                    else:
                        existVars.append(svar_i)
            if i < trace.steps_count()-1:
                for ivar in productModel.get_input_vars():
                    ivar_i = mgr.Symbol("%s@%d" % (ivar.symbol_name(), i), ivar.symbol_type())
                    if ivar.symbol_name() != '__delta__AT0':
                        subs[ivar_i] = step_i.get_assignment(ivar)
                    else:
                        existVars.append(ivar_i)
        exist_trace = qelim(mgr.Exists(existVars, bmc.substitute(subs)), solver_name=QELIM_SOLVER).simplify()
        new_psi = mgr.And(psi, mgr.Not(exist_trace))
        return new_psi

    def validate(self, pysmtEnv, tn, path, planningProblem, platformModel, future, futureSafety):
        mgr = pysmtEnv.formula_manager

        psi = mgr.Bool(True)
        tn_constraints = tn.get_constraints()
        explored_events = {}
        future_indexes = set()
        for i in range(0, len(path)):
            print("i:")
            print(i)

            if str(path[:(i+1)]) in self.cut_cache:
                print("Reusing cache")
                if i == len(path)-1:
                    raise Exception("Error: the algorithm should have finished earlier with this path")
                psi = self.cut_cache[str(path[:(i+1)])]
                event, ev_id = path[i]
                if future:
                    if event.pos == 0:
                        explored_events[path[i]] = i
                        associated_start = (event.action, True, ev_id-1)
                        explored_events[associated_start] = i
                        for j in range(i+1, len(path)):
                            event2, ev_id2 = path[j]
                            if event.action == event2.action:
                                end_pos = j
                                break
                        future_indexes.add(end_pos)
                        explored_events[path[end_pos]] = end_pos
                        associated_end = (event.action, False, ev_id-1)
                        explored_events[associated_end] = end_pos
                    if event.pos == 1:
                        future_indexes.remove(i)
                else:
                    if event.pos == 0:
                        associated_event = (event.action, True, ev_id-1)
                    if event.pos == 1:
                        associated_event = (event.action, False, ev_id-2)
                    explored_events[path[i]] = i
                    explored_events[associated_event] = i
            else:
                new_psi = []
                new_psi.append(psi)
                if i > 0:
                    t_i = mgr.Symbol(f"t@{i}", types.REAL)
                    t_i_prev = mgr.Symbol(f"t@{i-1}", types.REAL)
                    new_psi.append(mgr.LT(t_i_prev, t_i))

                event, ev_id = path[i]
                if future:
                    if event.pos == 0:
                        explored_events[path[i]] = i
                        associated_start = (event.action, True, ev_id-1)
                        explored_events[associated_start] = i
                        for j in range(i+1, len(path)):
                            event2, ev_id2 = path[j]
                            if event.action == event2.action:
                                end_pos = j
                                break
                        future_indexes.add(end_pos)
                        explored_events[path[end_pos]] = end_pos
                        associated_end = (event.action, False, ev_id-1)
                        explored_events[associated_end] = end_pos
                        t_i = mgr.Symbol(f"t@{i}", types.REAL)
                        t_end = mgr.Symbol(f"t@{end_pos}", types.REAL)
                        new_psi.append(mgr.GE(t_i, mgr.Real(0)))
                        new_psi.append(mgr.GE(t_end, mgr.Real(0)))
                        for ev1 in tn_constraints:
                            for (B, ev2) in tn_constraints[ev1]:
                                if (ev1 in explored_events) and (ev2 in explored_events) and (ev1 == path[i] or ev1 == path[end_pos] or ev1 == associated_start or ev1 == associated_end or ev2 == path[i] or ev2 == path[end_pos] or ev2 == associated_start or ev2 == associated_end) and (explored_events[ev1] <= i or explored_events[ev2] <= i):
                                    t1 = mgr.Symbol(f"t@{explored_events[ev1]}", types.REAL)
                                    t2 = mgr.Symbol(f"t@{explored_events[ev2]}", types.REAL)
                                    new_psi.append(mgr.LE(mgr.Minus(t1, t2), mgr.Real(B)))
                        psi = mgr.And(new_psi)
                    if event.pos == 1:
                        future_indexes.remove(i)
                        associated_end = (event.action, False, ev_id-2)
                        for ev1 in tn_constraints:
                            for (B, ev2) in tn_constraints[ev1]:
                                if (ev1 in explored_events) and (ev2 in explored_events) and ((ev1 == path[i] and explored_events[ev2] >= i) or (ev1 == associated_end and explored_events[ev2] >= i) or (ev2 == path[i] and explored_events[ev1] >= i) or (ev2 == associated_end and explored_events[ev1] >= i)):
                                    t1 = mgr.Symbol(f"t@{explored_events[ev1]}", types.REAL)
                                    t2 = mgr.Symbol(f"t@{explored_events[ev2]}", types.REAL)
                                    new_psi.append(mgr.LE(mgr.Minus(t1, t2), mgr.Real(B)))
                        psi = mgr.And(new_psi)
                else:
                    if event.pos == 0:
                        associated_event = (event.action, True, ev_id-1)
                    if event.pos == 1:
                        associated_event = (event.action, False, ev_id-2)
                    explored_events[path[i]] = i
                    explored_events[associated_event] = i
                    t_i = mgr.Symbol(f"t@{i}", types.REAL)
                    new_psi.append(mgr.GE(t_i, mgr.Real(0)))
                    for ev1 in tn_constraints:
                        for (B, ev2) in tn_constraints[ev1]:
                            if (ev1 in explored_events) and (ev2 in explored_events) and (ev1 == path[i] or ev1 == associated_event or ev2 == path[i] or ev2 == associated_event):
                                t1 = mgr.Symbol(f"t@{explored_events[ev1]}", types.REAL)
                                t2 = mgr.Symbol(f"t@{explored_events[ev2]}", types.REAL)
                                new_psi.append(mgr.LE(mgr.Minus(t1, t2), mgr.Real(B)))
                    psi = mgr.And(new_psi)

                # print("psi:")
                # print(psi)
                # print("end psi")

                with pysmtEnv.factory.Solver(logic="QF_LRA", random_seed=73) as smt:
                    smt.add_assertion(psi)
                    print("Start solving psi")
                    if not smt.solve():
                        print("End solving psi")
                        print("BAD")
                        print("i:")
                        print(i)
                        print("path:")
                        for j in range(0, i+1):
                            (ev, id) = path[j]
                            print(ev.action)
                        return False, None, path[:(i+1)]
                    else:
                        print("End solving psi")
                
                while True:
                    # print("ciao")
                    # print(psi.serialize())
                    productModel = self.build_automaton(pysmtEnv, path, i, future_indexes, psi, platformModel, futureSafety)
                    # print("init:")
                    # print(productModel.get_init_constraint().serialize())
                    # print("trans:")
                    # print(productModel.get_trans_constraint().serialize())
                    print("Start model checking")
                    safe, trace = self.check_model(productModel)
                    print("End model checking")
                    if safe:
                        if i == len(path)-1:
                            plan = self.extract_plan(pysmtEnv, path, psi)
                            return True, plan, None
                        else:
                            # if str(path[:(i+1)]) in self.cut_cache:
                            #     assertion_f = mgr.Not(mgr.Iff(psi, self.cut_cache[str(path[:(i+1)])]))
                            #     with pysmtEnv.factory.Solver(logic="QF_LRA", random_seed=73) as smt:
                            #         smt.add_assertion(assertion_f)
                            #         if smt.solve():
                            #             raise Exception("Not equivalent psi")
                            #         else:
                            #             print("equivalent!")
                            self.cut_cache[str(path[:(i+1)])] = psi
                            break
                    else:
                        # print("trace:")
                        # for step in trace.get_steps():
                        #     print("step:")
                        #     print(step.get_assignments())
                        print("Start computing psi")
                        psi = self.update_psi(pysmtEnv, productModel, path, i, psi, trace)
                        print("End computing psi")
                        with pysmtEnv.factory.Solver(logic="QF_LRA", random_seed=73) as smt:
                            smt.add_assertion(psi)
                            print("Start solving psi")
                            if not smt.solve():
                                print("End solving psi")
                                print("BAD")
                                print("i:")
                                print(i)
                                print("path:")
                                for j in range(0, i+1):
                                    (ev, id) = path[j]
                                    print(ev.action)
                                return False, None, path[:(i+1)]
                            else:
                                print("End solving psi")

    def solve(self, pysmtEnv, planningDomain, planningInstance, platformModel, future, futureSafety):
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

        self.cut_cache = {}
        counter = 0
        while True:
            counter += 1
            tn, path = self.search()
            print("candidate path:")
            for (ev, id) in path:
                print(ev.action)
            if tn is not None:
                outcome, sol, pre = self.validate(pysmtEnv, tn, path, self.problem, platformModel, future, futureSafety)
                if outcome:
                    print(sol)
                    print(f"Number of loops: {counter}")
                    break
                else:
                    self.bad_prefixes.append(self.generalize_seq(pre))
            else:
                print("problem unsolvable")


def main():
    pysmtEnv = vmtshortcuts.get_env()

    args = parse_args()
    planningDomain = args.domain
    planningInstance = args.instance
    platformModel = read(args.platform)
    future = args.future
    futureSafety = args.futuresafety

    s = Solver()
    s.solve(pysmtEnv, planningDomain, planningInstance, platformModel, future, futureSafety)


if __name__ == '__main__':
    main()