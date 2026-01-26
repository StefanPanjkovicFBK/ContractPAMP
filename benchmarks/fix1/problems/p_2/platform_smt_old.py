import sys
sys.path.insert(0, '/home/stefan/pacti/src')

import z3

from pacti.contracts import SmtIoContract


##### SWITCH CONTRACT #####

switch_start = z3.Real("t_0")
switch_end = z3.Real("t_1")
fixed_entry = z3.Bool("BOOL_fixed_entry")
fixed_exit = z3.Bool("BOOL_fixed_exit")
x_entry = z3.Real("ccontroller.x_entry")
x_exit = z3.Real("ccontroller.x_exit")
switch_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "BOOL_fixed_entry",
        "ccontroller.x_entry",
        "t_0",
        "t_1",
    ],
    output_vars = [
        "BOOL_fixed_exit",
        "ccontroller.x_exit",
    ],
    assumptions = [
        0 <= switch_end - switch_start,
        fixed_entry,
    ],
    guarantees = [
        z3.Not(fixed_exit),
        x_exit == 0,
    ]
)

##### FIX CONTRACT #####

fix_start = z3.Real("t_0")
fix_end = z3.Real("t_1")
fixed_entry = z3.Bool("BOOL_fixed_entry")
fixed_exit = z3.Bool("BOOL_fixed_exit")
x_entry = z3.Real("ccontroller.x_entry")
x_exit = z3.Real("ccontroller.x_exit")
fix_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "BOOL_fixed_entry",
        "ccontroller.x_entry",
        "t_0",
        "t_1",
    ],
    output_vars = [
        "BOOL_fixed_exit",
        "ccontroller.x_exit",
    ],
    assumptions = [
        0 <= fix_end - fix_start,
    ],
    guarantees = [
        x_exit == x_entry + 1,
        fixed_exit | (x_exit <= 1),
    ]
    # guarantees = [
    #     z3.Not(fixed_entry) | fixed_exit,
    #     fixed_entry | fixed_exit | ((z3.Not(fixed_exit)) & (x_exit == x_entry + 1) & (x_exit <= 1)),
    # ]
)

##### CONCURRENCY #####

CONCURRENCY_spec = {}

##### SAFETY CONTRACT #####

SAFETY_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "BOOL_fixed_entry",
        "ccontroller.x_entry",
    ],
    output_vars = [],
    assumptions = [
        fixed_entry,
        x_entry == 0,
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


