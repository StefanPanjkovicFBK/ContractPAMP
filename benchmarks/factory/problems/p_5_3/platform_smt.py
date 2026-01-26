import sys
sys.path.insert(0, '/home/stefan/pacti/src')

import z3

from pacti.contracts import SmtIoContract


##### WORK CONTRACT #####

work_start = z3.Real("t_0")
work_end = z3.Real("t_1")
cooldown_time_entry = z3.Real("cmachine.__CLOCK__c_1_entry")
cooldown_time_exit = z3.Real("cmachine.__CLOCK__c_1_exit")
cooling_entry = z3.Bool("BOOL_cooling_entry")
cooling_exit = z3.Bool("BOOL_cooling_exit")
work_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "cmachine.__CLOCK__c_1_entry",
        "BOOL_cooling_entry",
        "t_0",
        "t_1",
    ],
    output_vars = [
        "cmachine.__CLOCK__c_1_exit",
        "BOOL_cooling_exit",
    ],
    assumptions = [
        5 < work_end - work_start,
        work_end < 117,
        cooldown_time_entry > 10,
    ],
    guarantees = [
        cooling_exit,
        0 <= cooldown_time_exit,
        cooldown_time_exit <= 7,
    ]
)

##### COOLDOWN CONTRACT #####

cooldown_start = z3.Real("t_0")
cooldown_end = z3.Real("t_1")
cooldown_time_entry = z3.Real("cmachine.__CLOCK__c_1_entry")
cooldown_time_exit = z3.Real("cmachine.__CLOCK__c_1_exit")
cooling_entry = z3.Bool("BOOL_cooling_entry")
cooling_exit = z3.Bool("BOOL_cooling_exit")
cooldown_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "cmachine.__CLOCK__c_1_entry",
        "BOOL_cooling_entry",
        "t_0",
        "t_1",
    ],
    output_vars = [
        "cmachine.__CLOCK__c_1_exit",
        "BOOL_cooling_exit",
    ],
    assumptions = [
        0 <= cooldown_end - cooldown_start,
        cooldown_end - cooldown_start <= 2,
        cooling_entry,
        cooldown_time_entry < 8,
    ],
    guarantees = [
        cooldown_time_exit > 10,
    ]
)

##### CONCURRENCY #####

CONCURRENCY_spec = {}

##### SAFETY CONTRACT #####

cooldown_time_entry = z3.Real("cmachine.__CLOCK__c_1_entry")
SAFETY_spec = SmtIoContract.from_z3_terms(
    input_vars = [
        "cmachine.__CLOCK__c_1_entry",
    ],
    output_vars = [],
    assumptions = [
        cooldown_time_entry == 11
    ],
    guarantees = []
)

##### PLATFORM #####

platform = {
    "theory" : "SMT",
    "work" : work_spec,
    "cooldown" : cooldown_spec,
    "CONCURRENCY" : CONCURRENCY_spec,
    "SAFETY" : SAFETY_spec,
}


