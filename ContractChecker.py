# Copyright (C) 2026 PSO Unit, Fondazione Bruno Kessler
# This file is part of Platform-Aware Mission Planning with Task-Level Contracts (PAMP-TLC).
#
# PAMP-TLC is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PAMP-TLC is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#

import z3

import string
import secrets
import importlib
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

from pacti.contracts import SmtIoContract, PolyhedralIoContract

QELIM_SOLVER = "z3"
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
    parser.add_argument('-t', type=argparse.FileType('r'), default=sys.stdin, metavar='tts',
        help="The TTS platform description", dest='tts')
    parser.add_argument('-o', type=argparse.FileType('w'), default=sys.stdout, metavar='output',
        help="The output file, defaults to the standard output", dest='output')
    res = parser.parse_args()
    return res


class Checker():
    def build_automaton(self, pysmtEnv, contractName, contractSpec, ttsPlatform, safetyContract):
        mgr = pysmtEnv.formula_manager
        z3Solver = pysmtEnv.factory.Solver(name="z3")

        composedModel = Model()
        runningVars = []
        for var in ttsPlatform.get_state_vars():
            mgr.Symbol((var.symbol_name())[:-5]+"_entry", var.symbol_type())
            mgr.Symbol((var.symbol_name())[:-5]+"_exit", var.symbol_type())
            composedModel.add_state_var(var)
            if var.symbol_name().endswith("_running___AT0"):
                runningVars.append(var)
        for var in ttsPlatform.get_input_vars():
            composedModel.add_input_var(var)
        for f in ttsPlatform.get_trans_constraints():
            composedModel.add_trans(f)
        
        planLocation = composedModel.create_state_var('planLocation', types.REAL)
        planLocationNext = vmtshortcuts.Next(planLocation)
        planLocationRange = []
        planLocationNextRange = []
        for i in range(0, 4):
            planLocationRange.append(mgr.Equals(planLocation, mgr.Real(i)))
            planLocationNextRange.append(mgr.Equals(planLocationNext, mgr.Real(i)))
        composedModel.add_init(mgr.Or(planLocationRange))
        composedModel.add_trans(mgr.Or(planLocationRange))
        composedModel.add_trans(mgr.Or(planLocationNextRange))

        planEvent = composedModel.create_input_var('planEvent', types.REAL)
        planEventRange = []
        for i in range(0, 4):
            planEventRange.append(mgr.Equals(planEvent, mgr.Real(i)))
        composedModel.add_trans(mgr.Or(planEventRange))

        for i in range(0, 2):
            composedModel.create_frozen_var(f"t_{i}", types.REAL)
        composedModel.add_init(mgr.Equals(planLocation, mgr.Real(0)))

        timeVar = mgr.Symbol(f"time__AT0", types.REAL)
        timeNextVar = vmtshortcuts.Next(timeVar)
        global_clock = mgr.Symbol(f"global_clock__AT0", types.REAL)
        global_clock_next = vmtshortcuts.Next(global_clock)

        for i in range(0, 2):
            t_i = mgr.Symbol(f"t_{i}", types.REAL)
            composedModel.add_init(mgr.Implies(mgr.Equals(planLocation, mgr.Real(i)), mgr.LE(global_clock, t_i)))
            composedModel.add_trans(mgr.Implies(mgr.Equals(planLocation, mgr.Real(i)), mgr.LE(global_clock, t_i)))
            composedModel.add_trans(mgr.Implies(mgr.Equals(planLocationNext, mgr.Real(i)), mgr.LE(global_clock_next, t_i)))
        
        for i in range(0, 2):
            t_i = mgr.Symbol(f"t_{i}", types.REAL)
            transFormula = mgr.Implies(mgr.Equals(planEvent, mgr.Real(i)),
                                       mgr.And(mgr.Equals(planLocation, mgr.Real(i)),
                                               mgr.Equals(planLocationNext, mgr.Real(i+1)),
                                               mgr.Equals(global_clock, t_i)))
            composedModel.add_trans(mgr.Implies(mgr.Equals(timeVar, timeNextVar), transFormula))
        
        transFormula = mgr.Implies(mgr.Equals(planEvent, mgr.Real(3)), mgr.Equals(planLocation, planLocationNext))
        composedModel.add_trans(mgr.Implies(mgr.Equals(timeVar, timeNextVar), transFormula))

        for i in range(0, 2):
            if i == 0:
                tau = mgr.Symbol(f"t{contractName}.start__AT0")
            else:
                tau = mgr.Symbol(f"t{contractName}.end__AT0")
            transFormula = mgr.Implies(mgr.Equals(planEvent, mgr.Real(i)), tau)
            composedModel.add_trans(mgr.Implies(mgr.Equals(timeVar, timeNextVar), transFormula))
        
        for a in self.planning_problem.actions:
            lifted_action_name = a.name
            tau_a_start = mgr.Symbol(f"t{lifted_action_name}.start__AT0")
            tau_a_end = mgr.Symbol(f"t{lifted_action_name}.end__AT0")
            if lifted_action_name == contractName:
                transFormulaStart = mgr.Implies(tau_a_start, mgr.Equals(planEvent, mgr.Real(0)))
                transFormulaEnd = mgr.Implies(tau_a_end, mgr.Equals(planEvent, mgr.Real(1)))
            else:
                transFormulaStart = mgr.Implies(tau_a_start, mgr.Bool(False))
                transFormulaEnd = mgr.Implies(tau_a_end, mgr.Bool(False))
            composedModel.add_trans(mgr.Implies(mgr.Equals(timeVar, timeNextVar), transFormulaStart))
            composedModel.add_trans(mgr.Implies(mgr.Equals(timeVar, timeNextVar), transFormulaEnd))
        
        composedModel.add_trans(mgr.Implies(mgr.Not(mgr.Equals(timeVar, timeNextVar)),
                                            mgr.Equals(planLocation, planLocationNext)))
        
        startVars = {}
        for var in ttsPlatform.get_state_vars():
            sVar = composedModel.create_frozen_var(var.symbol_name()+"_START", var.symbol_type())
            startVars[var] = sVar
        
        contractAssumptions = mgr.And(*[z3Solver.converter.back(term.expression) for term in contractSpec.a.terms])
        subs = {}
        for var in ttsPlatform.get_state_vars():
            varEntry = mgr.Symbol((var.symbol_name())[:-5]+"_entry", var.symbol_type())
            subs[varEntry] = var
        composedModel.add_init(contractAssumptions.substitute(subs))
        composedModel.add_init(mgr.Equals(global_clock, mgr.Symbol("t_0", types.REAL)))
        # composedModel.add_init(mgr.Equals(global_clock, mgr.Real(0)))
        # composedModel.add_init(mgr.Equals(mgr.Symbol("t_0", types.REAL), mgr.Real(0)))
        composedModel.add_init(mgr.And(*[mgr.Not(v) for v in runningVars]))
        for (var, sVar) in startVars.items():
            if var.symbol_type() != sVar.symbol_type():
                raise Exception("var and sVar different types")
            elif var.symbol_type() == types.BOOL:
                composedModel.add_init(mgr.Iff(var, sVar))
            elif var.symbol_type() == types.REAL:
                composedModel.add_init(mgr.Equals(var, sVar))
            else:
                raise Exception("Variables can only have type BOOL or REAL")

        composedModelStateVars = composedModel.get_state_vars()
        composedModelInputVars = composedModel.get_input_vars()
        time_subs = {}
        existVars = []
        for v in composedModelStateVars:
            next_v = vmtshortcuts.Next(v)
            v_prime = mgr.Symbol("%s@prime" % (v.symbol_name()), v.symbol_type())
            time_subs[next_v] = v_prime
            if v.symbol_name() == '__iota__AT0':
                time_subs[v] = mgr.Bool(True)
            if v.symbol_name().endswith(".start__AT0") or v.symbol_name().endswith(".end__AT0"):
                existVars.append(v)
            existVars.append(v_prime)
        for v in composedModelInputVars:
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
        trans = mgr.And(composedModel.get_trans_constraints()).substitute(time_subs)
        exist_trans = qelim(mgr.Exists(existVars, trans), solver_name=QELIM_SOLVER).simplify()
        error_transition = []
        for i in range(0, 2):
            t_i = mgr.Symbol(f"t_{i}", types.REAL)
            subs = {}
            for v in composedModelInputVars:
                if v.symbol_name() == 'planEvent':
                    subs[v] = mgr.Real(i)
            exist_trans_i = exist_trans.substitute(subs).simplify()
            error_transition.append(mgr.And(mgr.Equals(planLocation, mgr.Real(i)),
                                            mgr.Equals(planLocationNext, mgr.Real(3)),
                                            mgr.Equals(global_clock, t_i),
                                            mgr.Not(exist_trans_i)))
        
        transFormula = mgr.Implies(mgr.Equals(planEvent, mgr.Real(2)), mgr.Or(error_transition))
        composedModel.add_trans(mgr.Implies(mgr.Equals(timeVar, timeNextVar), transFormula))

        contractGuarantees = mgr.And(*[z3Solver.converter.back(term.expression) for term in contractSpec.g.terms])
        subs = {}
        for var in ttsPlatform.get_state_vars():
            varEntry = mgr.Symbol((var.symbol_name())[:-5]+"_entry", var.symbol_type())
            varExit = mgr.Symbol((var.symbol_name())[:-5]+"_exit", var.symbol_type())
            varStart = mgr.Symbol(var.symbol_name()+"_START", var.symbol_type())
            subs[varEntry] = varStart
            subs[varExit] = var
        
        t1 = mgr.Symbol("t_1", types.REAL)
        taskRunning = mgr.Symbol(contractName+"_running___AT0", types.BOOL)
        gAfter = contractGuarantees.substitute(subs)
        # subs[t1] = global_clock
        # gDuring = contractGuarantees.substitute(subs)
        # safetyDuring = mgr.Implies(mgr.LE(global_clock, t1), gDuring)
        safetyAfter = mgr.Implies(mgr.And(mgr.LT(t1, global_clock), mgr.LE(global_clock, mgr.Plus(t1, mgr.Real(6)))), gAfter)

        safetyGuarantees = (mgr.And(*[z3Solver.converter.back(term.expression) for term in safetyContract.g.terms])).substitute(subs)
        convexSafety = mgr.Implies(mgr.And(safetyGuarantees, mgr.F(mgr.And(mgr.Equals(global_clock, t1),
                                                                           mgr.Not(taskRunning),
                                                                           safetyGuarantees))),
                                   mgr.G(mgr.Implies(mgr.LE(global_clock, mgr.Plus(t1, mgr.Real(6))), safetyGuarantees)))

        composedModel.add_invar_property(safetyAfter)
        composedModel.add_invar_property(mgr.Not(mgr.Equals(planLocation, mgr.Real(3))))
        composedModel.add_ltl_property(convexSafety)
        # print("property 1:")
        # print(safetyAfter.serialize())
        # print("property 2:")
        # print(mgr.Not(mgr.Equals(planLocation, mgr.Real(3))).serialize())
        # print("property 3:")
        # print(convexSafety.serialize())
        return composedModel

    def check_model(self, model):
        solver = Ic3iaSolver(model)
        results = solver.check_properties()
        if results[0].is_unsafe():
            print("property 1 violated")
            return False, results[0].get_trace()
        if results[1].is_unsafe():
            print("property 2 violated")
            return False, results[1].get_trace()
        if results[2].is_unsafe():
            print("property 3 violated")
            return False, results[2].get_trace()
        return True, None

    def check(self, pysmtEnv, planningDomain, planningInstance, contractPlatform, ttsPlatform):
        reader = ANMLReader()
        self.planning_problem = reader.parse_problem([planningDomain.name, planningInstance.name])
        success = True
        for (contractName, contractSpec) in contractPlatform.items():
            if contractName != "theory" and contractName != "CONCURRENCY" and contractName != "SAFETY":
                composedAutomaton = self.build_automaton(pysmtEnv, contractName, contractSpec, ttsPlatform, contractPlatform["SAFETY"])
                # print("Start model checking")
                # print(contractName)
                # print(contractSpec)
                safe, trace = self.check_model(composedAutomaton)
                # print("End model checking")
                if safe:
                    print("Contract OK!")
                else:
                    success = False
                    print("Contract BAD!")
                    print("trace:")
                    for step in trace.get_steps():
                        print("step:")
                        print(step.get_assignments())
                #print(composedAutomaton)
        if success:
            print("Contract validation successful!")
        else:
            print("Contract validation failed!")


def main():
    pysmtEnv = vmtshortcuts.get_env()

    args = parse_args()
    planningDomain = args.domain
    planningInstance = args.instance
    contractPlatform = load_module(args.platform.name).platform
    ttsPlatform = read(args.tts)

    c = Checker()
    c.check(pysmtEnv, planningDomain, planningInstance, contractPlatform, ttsPlatform)


if __name__ == '__main__':
    main()