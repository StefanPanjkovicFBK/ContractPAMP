import sys
sys.path.insert(0, '/home/stefan/pacti/src')

import z3

from pacti.contracts import SmtIoContract
from pacti.iocontract import Var
from ContractUtils import *

# Parameters:
# - s: index of the timeline variables
# - generation: (min, max) rate of battery charge during the task instance
def CHRG_power(s: int, generation: Tuple[float, float]) -> SmtIoContract:
  duration_charging_s = z3.Real(f"duration_charging{s}")
  soc_s_entry = z3.Real(f"soc{s}_entry")
  soc_s_exit = z3.Real(f"soc{s}_exit")
  spec = SmtIoContract.from_z3_terms(
    input_vars = [
      f"soc{s}_entry",          # initial battery SOC
      f"duration_charging{s}",  # variable task duration
    ],
    output_vars = [
      f"soc{s}_exit",           # final battery SOC
    ],
    assumptions = [
      # Task has a positive scheduled duration
      0 <= duration_charging_s,
      # Lower and upper bound on entry soc
      0 <= soc_s_entry,
      # The increase under the maximum generation rate should not overcharge the battery.
      #f"soc{s}_entry + {generation[1]}*duration_charging{s} <= 100",
    ],
    guarantees = [
      # duration*generation(min) <= soc{exit} - soc{entry} <= duration*generation(max)
      generation[0]*duration_charging_s <= soc_s_exit - soc_s_entry,
      soc_s_exit - soc_s_entry <= generation[1]*duration_charging_s,

      # Battery cannot exceed maximum SOC
      #f"soc{s}_exit <= 100.0",
      
      # Battery should not completely discharge
      0 <= soc_s_exit,
    ])
  return spec


# Parameters:
# - s: start index of the timeline variables
# - consumption: (min, max) rate of battery discharge during the task instance
def power_consumer(s: int, task: str, consumption: Tuple[float, float]) -> SmtIoContract:
  soc_s_entry = z3.Real(f"soc{s}_entry")
  duration_task_s = z3.Real(f"duration_{task}{s}")
  soc_s_exit = z3.Real(f"soc{s}_exit")
  spec = SmtIoContract.from_z3_terms(
    input_vars = [
      f"soc{s}_entry",          # initial battery SOC
      f"duration_{task}{s}",    # variable task duration
    ],
    output_vars = [
      f"soc{s}_exit",           # final battery SOC
    ],
    assumptions = [
        # Task has a positive scheduled duration
        0 <= duration_task_s,
        # Upper bound on entry soc
        #f"soc{s}_entry <= 100.0",
        # Lower bound on entry soc
        0 <= soc_s_entry,
        # Battery has enough energy for worst-case consumption throughout the task instance
        soc_s_entry >= consumption[1] * duration_task_s,
    ],
    guarantees=[
        # duration*consumption(min) <= soc{entry} - soc{exit} <= duration*consumption(max)
        consumption[0] * duration_task_s <= soc_s_entry - soc_s_exit,
        soc_s_entry - soc_s_exit <= consumption[1] * duration_task_s,
        # Battery cannot exceed maximum SOC
        #f"soc{s}_exit <= 100",
        # Battery should not completely discharge
        0 <= soc_s_exit,
    ])
  return spec
