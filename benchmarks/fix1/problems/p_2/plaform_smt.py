import sys
sys.path.insert(0, '/home/stefan/pacti/src')

import z3

from pacti.contracts import SmtIoContract


switch_running_entry = z3.Bool("BOOL_switch_running_entry")
fix_running_entry = z3.Bool("BOOL_fix_running_entry")

##### SWITCH CONTRACT #####

switch_start = z3.Real("t_0")
switch_end = z3.Real("t_1")
x_entry = z3.Real("x_entry")
x_exit = z3.Real("x_exit")
switch_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "x_entry",
        "t_0",
        "t_1",
        "BOOL_switch_running_entry",
        "BOOL_fix_running_entry",
    ],
    output_vars = [
        "x_exit",
    ],
    assumptions = [
        0 <= switch_end - switch_start,
        x_entry >= 2,
        z3.Not(switch_running_entry),
        z3.Not(fix_running_entry),
    ],
    guarantees = [
        x_exit = 0,
    ]
)

##### FIX CONTRACT #####

fix_start = z3.Real("t_0")
fix_end = z3.Real("t_1")
x_entry = z3.Real("x_entry")
x_exit = z3.Real("x_exit")
fix_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "x_entry",
        "t_0",
        "t_1",
        "BOOL_switch_running_entry",
        "BOOL_fix_running_entry",
    ],
    output_vars = [
        "x_exit",
    ],
    assumptions = [
        0 <= fix_end - fix_start,
        z3.Not(switch_running_entry),
        z3.Not(fix_running_entry),
    ],
    guarantees = [
        x_exit >= x_entry + 1,
    ]
)

##### CONCURRENCY #####

CONCURRENCY_spec = {}

##### SAFETY CONTRACT #####

SAFETY_spec = SmtIoContract.from_z3_terms(
    input_vars = ["x_entry",
                  "BOOL_switch_running_entry",
                  "BOOL_fix_running_entry",
    ],
    output_vars = [],
    assumptions = [
        x_entry = 0,
        z3.Not(switch_running_entry),
        z3.Not(fix_running_entry),
    ],
    guarantees = []
)

##### PLATFORM #####

platform = {
    "theory" : "SMT",
    "switch" : switch_spec,
    "fix" : fix_spec,
    "CONCURRENCY" : CONCURRENCY_spec,
    "SAFETY" : SAFETY_spec,
}


