import sys
sys.path.insert(0, '/home/stefan/pacti/src')

import z3

from pacti.contracts import SmtIoContract

##### switch CONTRACT #####

switch_start = z3.Real("t_0")
switch_end = z3.Real("t_1")
attempts_entry = z3.Real("attempts_entry")
attempts_exit = z3.Real("attempts_exit")
switch_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "attempts_entry",
        "t_0",
        "t_1",
    ],
    output_vars = [
        "attempts_exit",
    ],
    assumptions = [
        0 <= switch_end - switch_start,
        attempts_entry >= 2,
    ],
    guarantees = [
        attempts_exit == 0
    ]
)

##### fix CONTRACT #####

fix_start = z3.Real("t_0")
fix_end = z3.Real("t_1")
attempts_entry = z3.Real("attempts_entry")
attempts_exit = z3.Real("attempts_exit")
fix_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "attempts_entry",
        "t_0",
        "t_1",
    ],
    output_vars = [
        "attempts_exit",
    ],
    assumptions = [
        0 <= fix_end - fix_start,
    ],
    guarantees = [
        attempts_exit == attempts_entry + 1,
    ]
)

##### CONCURRENCY #####

CONCURRENCY_spec = {}

##### SAFETY CONTRACT #####

attempts_entry = z3.Real("attempts_entry")
SAFETY_spec = SmtIoContract.from_z3_terms(
    input_vars = ["attempts_entry"],
    output_vars = [],
    assumptions = [
        attempts_entry == 0,
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

