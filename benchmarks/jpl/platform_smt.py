import sys
sys.path.insert(0, '/home/stefan/pacti/src')

import z3

from pacti.contracts import SmtIoContract


##### CHARGE CONTRACT #####

CHARGE_start = z3.Real("t_0")
CHARGE_end = z3.Real("t_1")
soc_entry = z3.Real("soc_entry")
soc_exit = z3.Real("soc_exit")
CHARGE_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "soc_entry",
        "t_0",
        "t_1",
    ],
    output_vars = [
        "soc_exit",
    ],
    assumptions = [
        0 <= CHARGE_end - CHARGE_start,
        0 <= soc_entry,
    ],
    guarantees = [
        4.0*(CHARGE_end-CHARGE_start) <= soc_exit - soc_entry,
        soc_exit - soc_entry <= 5.0*(CHARGE_end-CHARGE_start),
        0 <= soc_exit,
    ]
)

##### DSN CONTRACT #####

DSN_start = z3.Real("t_0")
DSN_end = z3.Real("t_1")
soc_entry = z3.Real("soc_entry")
soc_exit = z3.Real("soc_exit")
DSN_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "soc_entry",
        "t_0",
        "t_1",
    ],
    output_vars = [
        "soc_exit",
    ],
    assumptions = [
        0 <= DSN_end-DSN_start,
        0 <= soc_entry,
        soc_entry >= 2.2 * (DSN_end-DSN_start),
    ],
    guarantees = [
        2.0 * (DSN_end-DSN_start) <= soc_entry - soc_exit,
        soc_entry - soc_exit <= 2.2 * (DSN_end-DSN_start),
        0 <= soc_exit,
    ]
)

##### SBO CONTRACT #####

SBO_start = z3.Real("t_0")
SBO_end = z3.Real("t_1")
soc_entry = z3.Real("soc_entry")
soc_exit = z3.Real("soc_exit")
SBO_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "soc_entry",
        "t_0",
        "t_1"
    ],
    output_vars = [
        "soc_exit",
    ],
    assumptions = [
        0 <= SBO_end-SBO_start,
        0 <= soc_entry,
        soc_entry >= 0.2 * (SBO_end-SBO_start),
    ],
    guarantees = [
        0.1 * (SBO_end-SBO_start) <= soc_entry - soc_exit,
        soc_entry - soc_exit <= 0.2 * (SBO_end-SBO_start),
        0 <= soc_exit,
    ]
)

##### TCM CONTRACT #####

TCM_start = z3.Real("t_0")
TCM_end = z3.Real("t_1")
soc_entry = z3.Real("soc_entry")
soc_exit = z3.Real("soc_exit")
TCM_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "soc_entry",
        "t_0",
        "t_1"
    ],
    output_vars = [
        "soc_exit",
    ],
    assumptions = [
        0 <= TCM_end-TCM_start,
        0 <= soc_entry,
        soc_entry >= 1.1 * (TCM_end-TCM_start),
    ],
    guarantees = [
        0.9 * (TCM_end-TCM_start) <= soc_entry - soc_exit,
        soc_entry - soc_exit <= 1.1 * (TCM_end-TCM_start),
        0 <= soc_exit,
    ]
)

##### CHARGE_DSN CONTRACT #####

t_0 = z3.Real("t_0")
t_1 = z3.Real("t_1")
t_2 = z3.Real("t_2")
t_3 = z3.Real("t_3")
soc_entry = z3.Real("soc_entry")
soc_exit = z3.Real("soc_exit")
CHARGE_DSN_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "soc_entry",
        "t_0",
        "t_1",
        "t_2",
        "t_3",
    ],
    output_vars = [
        "soc_exit",
    ],
    assumptions = [
        0 <= t_3-t_0,
        0 <= soc_entry,
        soc_entry <= 200,
    ],
    guarantees = [
        1.8*(t_3-t_0) <= soc_exit - soc_entry,
        soc_exit - soc_entry <= 3.0*(t_3-t_0),
        0 <= soc_exit,
    ]
)

##### CHARGE_SBO CONTRACT #####

t_0 = z3.Real("t_0")
t_1 = z3.Real("t_1")
t_2 = z3.Real("t_2")
t_3 = z3.Real("t_3")
soc_entry = z3.Real("soc_entry")
soc_exit = z3.Real("soc_exit")
CHARGE_SBO_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "soc_entry",
        "t_0",
        "t_1",
        "t_2",
        "t_3",
    ],
    output_vars = [
        "soc_exit",
    ],
    assumptions = [
        0 <= t_3-t_0,
        0 <= soc_entry,
        soc_entry <= 200,
    ],
    guarantees = [
        3.8*(t_3-t_0) <= soc_exit - soc_entry,
        soc_exit - soc_entry <= 4.9*(t_3-t_0),
        0 <= soc_exit,
    ]
)

##### CHARGE_TCM CONTRACT #####

t_0 = z3.Real("t_0")
t_1 = z3.Real("t_1")
t_2 = z3.Real("t_2")
t_3 = z3.Real("t_3")
soc_entry = z3.Real("soc_entry")
soc_exit = z3.Real("soc_exit")
CHARGE_TCM_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "soc_entry",
        "t_0",
        "t_1",
        "t_2",
        "t_3",
    ],
    output_vars = [
        "soc_exit",
    ],
    assumptions = [
        0 <= t_3-t_0,
        0 <= soc_entry,
        soc_entry <= 200,
    ],
    guarantees = [
        2.9*(t_3-t_0) <= soc_exit - soc_entry,
        soc_exit - soc_entry <= 4.1*(t_3-t_0),
        0 <= soc_exit,
    ]
)

##### CONCURRENCY #####

CONCURRENCY_spec = {
    ("CHARGE_start", "DSN_start", "CHARGE_end", "DSN_end") : ("CHARGE_DSN", CHARGE_DSN_spec),
    ("CHARGE_start", "DSN_start", "DSN_end", "CHARGE_end") : ("CHARGE_DSN", CHARGE_DSN_spec),
    ("DSN_start", "CHARGE_start", "DSN_end", "CHARGE_end") : ("CHARGE_DSN", CHARGE_DSN_spec),
    ("DSN_start", "CHARGE_start", "CHARGE_end", "DSN_end") : ("CHARGE_DSN", CHARGE_DSN_spec),

    ("CHARGE_start", "SBO_start", "CHARGE_end", "SBO_end") : ("CHARGE_SBO", CHARGE_SBO_spec),
    ("CHARGE_start", "SBO_start", "SBO_end", "CHARGE_end") : ("CHARGE_SBO", CHARGE_SBO_spec),
    ("SBO_start", "CHARGE_start", "SBO_end", "CHARGE_end") : ("CHARGE_SBO", CHARGE_SBO_spec),
    ("SBO_start", "CHARGE_start", "CHARGE_end", "SBO_end") : ("CHARGE_SBO", CHARGE_SBO_spec),

    ("CHARGE_start", "TCM_start", "CHARGE_end", "TCM_end") : ("CHARGE_TCM", CHARGE_TCM_spec),
    ("CHARGE_start", "TCM_start", "TCM_end", "CHARGE_end") : ("CHARGE_TCM", CHARGE_TCM_spec),
    ("TCM_start", "CHARGE_start", "TCM_end", "CHARGE_end") : ("CHARGE_TCM", CHARGE_TCM_spec),
    ("TCM_start", "CHARGE_start", "CHARGE_end", "TCM_end") : ("CHARGE_TCM", CHARGE_TCM_spec),
}

##### SAFETY CONTRACT #####

soc_entry = z3.Real("soc_entry")
soc_exit = z3.Real("soc_exit")
SAFETY_spec = SmtIoContract.from_z3_terms(
    input_vars = ["soc_entry"],
    output_vars = ["soc_exit"],
    assumptions = [
        soc_entry == 200,
    ],
    guarantees = [
        soc_exit >= 40,
    ]
)

##### PLATFORM #####

platform = {
    "theory" : "SMT",
    "CHARGE" : CHARGE_spec,
    "DSN" : DSN_spec,
    "SBO" : SBO_spec,
    "TCM" : TCM_spec,
    "CONCURRENCY" : CONCURRENCY_spec,
    "SAFETY" : SAFETY_spec,
}


