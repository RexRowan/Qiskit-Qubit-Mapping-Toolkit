"""
qiskit-qubit-mapping-toolkit
=============================

Graph-theoretic initial layout and routing heuristics for mapping logical
quantum circuits onto hardware coupling maps.

The toolkit provides two families of layout heuristics:

* :class:`~qiskit_qubit_mapping.layout.IsomorphismLayout` -- finds
  near-isomorphic embeddings of a circuit's interaction graph into the
  hardware coupling graph via VF2-based subgraph matching.
* :class:`~qiskit_qubit_mapping.layout.WalkBasedLayout` -- scores candidate
  placements using continuous-time quantum walk (CTQW) mixing properties,
  reusing the walk machinery from ``qiskit-graph-walks``.

and a baseline shortest-path routing pass,
:class:`~qiskit_qubit_mapping.routing.BaselineSwapRouter`, plus an
evaluation harness in :mod:`qiskit_qubit_mapping.metrics` for comparing
mapping quality against Qiskit's built-in Sabre passes.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("qiskit-qubit-mapping-toolkit")
except PackageNotFoundError:  # pragma: no cover - local/dev install
    __version__ = "0.1.0.dev0"

from qiskit_qubit_mapping.layout.isomorphism import IsomorphismLayout
from qiskit_qubit_mapping.layout.walk_based import WalkBasedLayout
from qiskit_qubit_mapping.routing.baseline import BaselineSwapRouter
from qiskit_qubit_mapping.routing.lookahead import LookaheadSwapRouter

__all__ = [
    "__version__",
    "IsomorphismLayout",
    "WalkBasedLayout",
    "BaselineSwapRouter",
    "LookaheadSwapRouter",
]
