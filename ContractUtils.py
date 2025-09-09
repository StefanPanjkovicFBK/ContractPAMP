import sys
sys.path.insert(0, '/home/stefan/pacti/src')

"""Helper module for the space mission case study."""
from pacti.terms.smt import SmtTerm, SmtTermList
# from pacti.terms.polyhedra import PolyhedralTerm, PolyhedralTermList
from pacti.contracts import SmtIoContract
# from pacti.contracts import PolyhedralIoContract

from pacti import write_contracts_to_file
from pacti.iocontract import Var
from typing import Optional, List, Tuple, Union
from dataclasses import dataclass
import numpy as np
import pathlib
import operator

tuple2float = Tuple[float, float]

here = pathlib.Path(__file__).parent.resolve()

epsilon = 0

numeric = Union[int, float]

tuple2 = Tuple[Optional[numeric], Optional[numeric]]

# def bound(c: PolyhedralIoContract, var: str) -> Tuple[str, str]:
#     try:
#         b = c.get_variable_bounds(var)
#         if isinstance(b[0], float):
#             low = f"{b[0]:.2f}"
#         else:
#             low = "None"
#         if isinstance(b[1], float):
#             high = f"{b[1]:.2f}"
#         else:
#             high = "None"
#         return low, high
#     except ValueError:
#         return "unknown", "unknown"

# def bounds(c: PolyhedralIoContract) -> List[str]:
#     bounds=[]
#     for v in sorted(c.inputvars, key=operator.attrgetter('name')):
#         low, high = bound(c, v.name)
#         bounds.append(f" input {v.name} in [{low},{high}]")

#     for v in sorted(c.outputvars, key=operator.attrgetter('name')):
#         low, high = bound(c, v.name)
#         bounds.append(f"output {v.name} in [{low},{high}]")

#     return bounds

def scenario_sequence(
    c1: SmtIoContract,
    c2: SmtIoContract,
    variables: list[str],
    c1index: int,
    c2index: Optional[int] = None,
    file_name: Optional[str] = None,
) -> SmtIoContract:
    """
    Composes c1 with a c2 modified to rename its entry variables according to c1's exit variables

    Args:
        c1: preceding step in the scenario sequence
        c2: next step in the scenario sequence
        variables: list of entry/exit variable names for renaming
        c1index: the step number for c1's variable names
        c2index: the step number for c2's variable names; defaults ti c1index+1 if unspecified

    Returns:
        c1 composed with a c2 modified to rename its c2index-entry variables
        to c1index-exit variables according to the variable name correspondences
        with a post-composition renaming of c1's exit variables to fresh outputs
        according to the variable names.
    """
    if not c2index:
        c2index = c1index + 1
    c2_inputs_to_c1_outputs = [(f"{v}{c2index}_entry", f"{v}{c1index}_exit") for v in variables]
    keep_c1_outputs = [f"{v}{c1index}_exit" for v in variables]
    renamed_c1_outputs = [(f"{v}{c1index}_exit", f"output_{v}{c1index}") for v in variables]

    c2_with_inputs_renamed = c2.rename_variables(c2_inputs_to_c1_outputs)
    c12_with_outputs_kept = c1.compose(c2_with_inputs_renamed, vars_to_keep=keep_c1_outputs)
    c12 = c12_with_outputs_kept.rename_variables(renamed_c1_outputs)

    if file_name:
        write_contracts_to_file(
            contracts=[c1, c2_with_inputs_renamed, c12_with_outputs_kept],
            names=["c1", "c2_with_inputs_renamed", "c12_with_outputs_kept"],
            file_name=file_name,
        )

    return c12