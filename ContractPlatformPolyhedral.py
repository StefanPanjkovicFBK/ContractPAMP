import sys
sys.path.insert(0, '/home/stefan/pacti/src')

import z3

from pacti.contracts import PolyhedralIoContract
from pacti.iocontract import Var
from ContractUtils import *

# Parameters:
# - s: index of the timeline variables
# - generation: (min, max) rate of battery charge during the task instance
def CHRG_power(s: int, generation: Tuple[float, float]) -> PolyhedralIoContract:
  spec = PolyhedralIoContract.from_strings(
    input_vars = [
      f"soc{s}_entry",          # initial battery SOC
      f"duration_charging{s}",  # variable task duration
    ],
    output_vars = [
      f"soc{s}_exit",           # final battery SOC
    ],
    assumptions = [
      # Task has a positive scheduled duration
      f"0 <= duration_charging{s}",
      # Lower and upper bound on entry soc
      f"0 <= soc{s}_entry",
      # The increase under the maximum generation rate should not overcharge the battery.
      #f"soc{s}_entry + {generation[1]}*duration_charging{s} <= 100",
    ],
    guarantees = [
      # duration*generation(min) <= soc{exit} - soc{entry} <= duration*generation(max)
      f"{generation[0]}*duration_charging{s} <= soc{s}_exit - soc{s}_entry <= {generation[1]}*duration_charging{s}",

      # Battery cannot exceed maximum SOC
      #f"soc{s}_exit <= 100.0",
      
      # Battery should not completely discharge
      f"0 <= soc{s}_exit",
    ])
  return spec


# Parameters:
# - s: start index of the timeline variables
# - consumption: (min, max) rate of battery discharge during the task instance
def power_consumer(s: int, task: str, consumption: Tuple[float, float]) -> PolyhedralIoContract:
  spec = PolyhedralIoContract.from_strings(
    input_vars = [
      f"soc{s}_entry",          # initial battery SOC
      f"duration_{task}{s}",    # variable task duration
    ],
    output_vars = [
      f"soc{s}_exit",           # final battery SOC
    ],
    assumptions = [
        # Task has a positive scheduled duration
        f"0 <= duration_{task}{s}",
        # Upper bound on entry soc
        #f"soc{s}_entry <= 100.0",
        # Lower bound on entry soc
        f"0 <= soc{s}_entry",
        # Battery has enough energy for worst-case consumption throughout the task instance
        f"soc{s}_entry >= {consumption[1]}*duration_{task}{s}",
    ],
    guarantees=[
        # duration*consumption(min) <= soc{entry} - soc{exit} <= duration*consumption(max)
        f"{consumption[0]}*duration_{task}{s} <= soc{s}_entry - soc{s}_exit <= {consumption[1]}*duration_{task}{s}",
        # Battery cannot exceed maximum SOC
        #f"soc{s}_exit <= 100",
        # Battery should not completely discharge
        f"0 <= soc{s}_exit",
    ])
  return spec
