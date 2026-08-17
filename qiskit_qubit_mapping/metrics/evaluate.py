from __future__ import annotations

from dataclasses import dataclass

from qiskit.circuit import QuantumCircuit
from qiskit.circuit.library import SwapGate
from qiskit.transpiler import CouplingMap, PassManager
from qiskit.transpiler.passes import SabreLayout, SabreSwap

from qiskit_qubit_mapping.routing.baseline import BaselineSwapRouter


@dataclass
class EvaluationResult:
    """Result of routing a circuit with a given layout+routing pipeline."""

    swap_count: int
    depth: int
    layout_score: float | None = None
    metadata: dict | None = None

    def __repr__(self) -> str:  # concise, useful in notebooks/REPLs
        return f"EvaluationResult(swap_count={self.swap_count}, depth={self.depth})"


def _count_swaps(circuit: QuantumCircuit) -> int:
    return sum(1 for instruction in circuit.data if isinstance(instruction.operation, SwapGate))


def evaluate_layout(
    circuit: QuantumCircuit,
    coupling_map: CouplingMap,
    layout_pass,
    router_pass=None,
) -> EvaluationResult:
    """Run ``layout_pass`` followed by a routing pass and report SWAP
    count and depth of the routed circuit.

    Parameters
    ----------
    circuit:
        Logical circuit to route.
    coupling_map:
        Target hardware topology.
    layout_pass:
        An instantiated layout pass, e.g.
        ``IsomorphismLayout(coupling_map)`` or
        ``WalkBasedLayout(coupling_map)``.
    router_pass:
        An instantiated routing pass, e.g. ``BaselineSwapRouter(coupling_map)``
        or ``LookaheadSwapRouter(coupling_map)``. Defaults to
        ``BaselineSwapRouter(coupling_map)`` if not provided.
    """
    if router_pass is None:
        router_pass = BaselineSwapRouter(coupling_map)
    pm = PassManager([layout_pass, router_pass])
    routed = pm.run(circuit)

    layout_result = pm.property_set.get("qubit_mapping_result")
    return EvaluationResult(
        swap_count=_count_swaps(routed),
        depth=routed.depth(),
        layout_score=layout_result.score if layout_result is not None else None,
        metadata=layout_result.metadata if layout_result is not None else None,
    )


def compare_to_sabre(
    circuit: QuantumCircuit,
    coupling_map: CouplingMap,
    layout_pass,
    router_pass=None,
    seed: int = 0,
) -> dict[str, EvaluationResult]:
    """Evaluate ``layout_pass`` + a routing pass alongside Qiskit's
    built-in ``SabreLayout`` + ``SabreSwap`` on the same circuit and
    coupling map, for a like-for-like comparison.

    ``router_pass`` defaults to :class:`BaselineSwapRouter`; pass a
    :class:`~qiskit_qubit_mapping.routing.lookahead.LookaheadSwapRouter`
    instance instead to compare the lookahead router against Sabre.

    Returns a dict with keys ``"toolkit"`` and ``"sabre"``, each mapping
    to an :class:`EvaluationResult`.
    """
    toolkit_result = evaluate_layout(circuit, coupling_map, layout_pass, router_pass)

    sabre_pm = PassManager(
        [
            SabreLayout(coupling_map, seed=seed),
            SabreSwap(coupling_map, seed=seed),
        ]
    )
    sabre_routed = sabre_pm.run(circuit)
    sabre_result = EvaluationResult(
        swap_count=_count_swaps(sabre_routed),
        depth=sabre_routed.depth(),
    )

    return {"toolkit": toolkit_result, "sabre": sabre_result}
