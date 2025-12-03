import sys
sys.path.insert(0, '/home/stefan/pacti/src')

from pacti.contracts import PolyhedralIoContract


##### CHARGE CONTRACT #####

CHARGE_spec = PolyhedralIoContract.from_strings(
    input_vars = [
        "soc_entry",
        "t_0",
        "t_1",
    ],
    output_vars = [
        "soc_exit",
    ],
    assumptions = [
        "0 <= t_1 - t_0",
        "0 <= soc_entry",
        "soc_entry <= 200",
    ],
    guarantees = [
        "4.0*(t_1-t_0) <= soc_exit - soc_entry",
        "soc_exit - soc_entry <= 5.0*(t_1-t_0)",
        "0 <= soc_exit",
    ]
)

##### DSN CONTRACT #####

DSN_spec = PolyhedralIoContract.from_strings(
    input_vars = [
        "soc_entry",
        "t_0",
        "t_1",
    ],
    output_vars = [
        "soc_exit",
    ],
    assumptions = [
        "0 <= t_1 - t_0",
        "0 <= soc_entry",
        "soc_entry <= 200",
        "soc_entry >= 2.2 * (t_1-t_0)",
    ],
    guarantees = [
        "2.0 * (t_1-t_0) <= soc_entry - soc_exit",
        "soc_entry - soc_exit <= 2.2 * (t_1-t_0)",
        "0 <= soc_exit",
    ]
)

##### SBO CONTRACT #####

SBO_spec = PolyhedralIoContract.from_strings(
    input_vars = [
        "soc_entry",
        "t_0",
        "t_1",
    ],
    output_vars = [
        "soc_exit",
    ],
    assumptions = [
        "0 <= t_1 - t_0",
        "0 <= soc_entry",
        "soc_entry <= 200",
        "soc_entry >= 0.2 * (t_1-t_0)",
    ],
    guarantees = [
        "0.1 * (t_1-t_0) <= soc_entry - soc_exit",
        "soc_entry - soc_exit <= 0.2 * (t_1-t_0)",
        "0 <= soc_exit",
    ]
)

##### TCM CONTRACT #####

TCM_spec = PolyhedralIoContract.from_strings(
    input_vars = [
        "soc_entry",
        "t_0",
        "t_1",
    ],
    output_vars = [
        "soc_exit",
    ],
    assumptions = [
        "0 <= t_1 - t_0",
        "0 <= soc_entry",
        "soc_entry <= 200",
        "soc_entry >= 1.1 * (t_1-t_0)",
    ],
    guarantees = [
        "0.9 * (t_1-t_0) <= soc_entry - soc_exit",
        "soc_entry - soc_exit <= 1.1 * (t_1-t_0)",
        "0 <= soc_exit",
    ]
)

##### CHARGE_DSN CONTRACT #####

CHARGE_DSN_spec = PolyhedralIoContract.from_strings(
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
        "0 <= t_3-t_0",
        "0 <= soc_entry",
        "soc_entry <= 200",
    ],
    guarantees = [
        "1.8*(t_3-t_0) <= soc_exit - soc_entry",
        "soc_exit - soc_entry <= 3.0*(t_3-t_0)",
        "0 <= soc_exit",
    ]
)

##### CHARGE_SBO CONTRACT #####

CHARGE_SBO_spec = PolyhedralIoContract.from_strings(
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
        "0 <= t_3-t_0",
        "0 <= soc_entry",
        "soc_entry <= 200",
    ],
    guarantees = [
        "3.8*(t_3-t_0) <= soc_exit - soc_entry",
        "soc_exit - soc_entry <= 4.9*(t_3-t_0)",
        "0 <= soc_exit",
    ]
)

##### CHARGE_TCM CONTRACT #####

CHARGE_TCM_spec = PolyhedralIoContract.from_strings(
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
        "0 <= t_3-t_0",
        "0 <= soc_entry",
        "soc_entry <= 200",
    ],
    guarantees = [
        "2.9*(t_3-t_0) <= soc_exit - soc_entry",
        "soc_exit - soc_entry <= 4.1*(t_3-t_0)",
        "0 <= soc_exit",
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

SAFETY_spec = PolyhedralIoContract.from_strings(
    input_vars = ["soc_entry"],
    output_vars = ["soc_exit"],
    assumptions = [
        "soc_entry == 200",
    ],
    guarantees = [
        "soc_exit >= 40",
    ]
)

##### PLATFORM #####

platform = {
    "theory" : "POLYHEDRAL",
    "CHARGE" : CHARGE_spec,
    "DSN" : DSN_spec,
    "SBO" : SBO_spec,
    "TCM" : TCM_spec,
    "CONCURRENCY" : CONCURRENCY_spec,
    "SAFETY" : SAFETY_spec,
}


