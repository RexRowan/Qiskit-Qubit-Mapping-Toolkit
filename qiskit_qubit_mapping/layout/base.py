from __future__ import annotations

from dataclasses import dataclass, field

from qiskit.transpiler import CouplingMap, Layout
from qiskit.transpiler.basepasses import AnalysisPass


@dataclass
class LayoutResult:
    """Result of running a layout heuristic.

    Attributes
    ----------
    mapping:
        Logical qubit index -> physical qubit index.
    score:
        Heuristic-specific quality score. Lower is better for every
        heuristic in this package (it is always some flavor of expected
        routing cost), so results from different heuristics on the *same*
        circuit/coupling map pair are comparable.
    metadata:
        Free-form extra information about how the result was produced
        (e.g. number of candidates considered, whether an exact isomorphism
        was found).
    """

    mapping: dict[int, int]
    score: float
    metadata: dict = field(default_factory=dict)

    def to_qiskit_layout(self, circuit) -> Layout:
        """Convert to a :class:`qiskit.transpiler.Layout` for use with
        ``PassManager`` / ``SetLayout``.
        """
        return Layout({circuit.qubits[logical]: physical for logical, physical in self.mapping.items()})


class LayoutHeuristic(AnalysisPass):
    """Common base class for the toolkit's layout passes.

    Subclasses implement :meth:`compute_layout`, which does the actual
    heuristic work and returns a :class:`LayoutResult`. The pass sets
    ``property_set["layout"]`` (matching Qiskit's own layout pass
    convention) and ``property_set["qubit_mapping_result"]`` (this
    package's richer result object, including the score) so both the
    standard transpiler pipeline and this toolkit's own
    :mod:`qiskit_qubit_mapping.metrics` can consume the output.
    """

    def __init__(self, coupling_map: CouplingMap):
        super().__init__()
        self.coupling_map = coupling_map

    def compute_layout(self, dag) -> LayoutResult:  # pragma: no cover - interface
        raise NotImplementedError

    def run(self, dag):
        circuit_qubits = dag.qubits
        result = self.compute_layout(dag)
        self.property_set["layout"] = Layout(
            {circuit_qubits[logical]: physical for logical, physical in result.mapping.items()}
        )
        self.property_set["qubit_mapping_result"] = result
