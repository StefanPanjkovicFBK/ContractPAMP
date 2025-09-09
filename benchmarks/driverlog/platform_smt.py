import sys
sys.path.insert(0, '/home/stefan/pacti/src')

import z3

from pacti.contracts import SmtIoContract

##### driveleft CONTRACT #####

driveleft_start = z3.Real("t_0")
driveleft_end = z3.Real("t_1")
weight_entry = z3.Real("weight_entry")
pos_entry = z3.Real("pos_entry")
pos_exit = z3.Real("pos_exit")
driveleft_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "weight_entry",
        "pos_entry",
        "t_0",
        "t_1",
    ],
    output_vars = [
        "pos_exit",
    ],
    assumptions = [
        0 <= driveleft_end - driveleft_start,
    ],
    guarantees = [
        pos_exit = pos_entry - (driveleft_end - driveleft_start) / weight_entry
    ]
)

##### driveright CONTRACT #####

driveright_start = z3.Real("t_0")
driveright_end = z3.Real("t_1")
weight_entry = z3.Real("weight_entry")
pos_entry = z3.Real("pos_entry")
pos_exit = z3.Real("pos_exit")
driveright_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "weight_entry",
        "pos_entry",
        "t_0",
        "t_1",
    ],
    output_vars = [
        "pos_exit",
    ],
    assumptions = [
        0 <= driveright_end - driveright_start,
    ],
    guarantees = [
        pos_exit = pos_entry + (driveright_end - driveright_start) / weight_entry
    ]
)

##### load CONTRACT #####

load_start = z3.Real("t_0")
load_end = z3.Real("t_1")
weight_entry = z3.Real("weight_entry")
weight_exit = z3.Real("weight_exit")
load_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "weight_entry",
        "t_0",
        "t_1",
    ],
    output_vars = [
        "weight_exit",
    ],
    assumptions = [
        0 <= load_end - load_start,
    ],
    guarantees = [
        weight_exit = weight_entry + 1
    ]
)

##### unload CONTRACT #####

unload_start = z3.Real("t_0")
unload_end = z3.Real("t_1")
weight_entry = z3.Real("weight_entry")
weight_exit = z3.Real("weight_exit")
unload_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "weight_entry",
        "t_0",
        "t_1",
    ],
    output_vars = [
        "weight_exit",
    ],
    assumptions = [
        0 <= unload_end - unload_start,
    ],
    guarantees = [
        weight_exit = weight_entry - 1
    ]
)

##### CONCURRENCY #####

CONCURRENCY_spec = {}

##### SAFETY CONTRACT #####

weight_entry = z3.Real("weight_entry")
pos_entry = z3.Real("pos_entry")
pos_exit = z3.Real("pos_exit")
SAFETY_spec = SmtIoContract.from_z3_terms(
    input_vars = ["pos_entry"],
    output_vars = ["pos_exit"],
    assumptions = [
        weight_entry == 0.1,
        pos_entry == 0,
    ],
    guarantees = [
        (pos_exit == 0) | (pos_exit == 100) | (pos_exit == 200) | (pos_exit == 300) | (pos_exit == 400) | (pos_exit == 500)
    ]
)

##### PLATFORM #####

platform = {
    "theory" : "SMT",
    "driveleft" : driveleft_spec,
    "driveright" : driveright_spec,
    "load" : load_spec,
    "unload" : unload_spec,
    "CONCURRENCY" : CONCURRENCY_spec,
    "SAFETY" : SAFETY_spec,
}

