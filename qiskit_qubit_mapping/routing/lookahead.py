from __future__ import annotations

import networkx as nx
from qiskit.circuit import QuantumCircuit
from qiskit.circuit.library import SwapGate
from qiskit.converters import circuit_to_dag, dag_to_circuit
from qiskit.transpiler import CouplingMap, Layout
from qiskit.transpiler.basepasses import TransformationPass

from qiskit_qubit_mapping._graph_utils import coupling_graph


def route_circuit_lookahead(
    circuit: QuantumCircuit,
    coupling_map: CouplingMap,
    initial_layout: dict[int, int] | None = None,
    lookahead_size: int = 20,
    lookahead_weight: float = 0.5,
) -> tuple[QuantumCircuit, dict[int, int]]:
    """Route ``circuit`` with a lookahead SWAP-selection heuristic.

    This follows the same overall shape as Sabre's routing heuristic
    (though without Sabre's bidirectional/iterative layout refinement --
    see :func:`~qiskit_qubit_mapping.routing.baseline.route_circuit` for a
    simpler non-lookahead baseline, and :mod:`qiskit_qubit_mapping.metrics`
    for a like-for-like comparison against the real thing):

    1. Maintain a *front layer* of gates whose dependencies are already
       satisfied (via :meth:`DAGCircuit.front_layer`). Execute every
       front-layer gate that is either single-qubit or, for two-qubit
       gates, already hardware-adjacent under the current mapping.
    2. Once no more front-layer gates can execute directly, some pending
       two-qubit gate's operands are non-adjacent and a SWAP is needed.
       Candidate SWAPs are every hardware edge touching a qubit involved
       in a *pending* front-layer two-qubit gate.
    3. Score each candidate SWAP by how much it would reduce the total
       hardware distance summed over (a) the pending front-layer gates and
       (b) a lookahead window of upcoming two-qubit gates, weighted by
       ``lookahead_weight``. Apply the lowest-scoring SWAP and repeat from
       step 1.

    Parameters
    ----------
    circuit:
        Logical circuit to route.
    coupling_map:
        Target hardware topology.
    initial_layout:
        Logical qubit index -> physical qubit index. Defaults to the
        identity mapping.
    lookahead_size:
        Number of upcoming two-qubit gates (beyond the current front
        layer) to include when scoring candidate SWAPs. Larger values bias
        SWAP choices toward reducing cost further into the circuit at the
        expense of more scoring work per SWAP decision; ``0`` reduces this
        to a greedy front-layer-only heuristic.
    lookahead_weight:
        Relative weight given to the lookahead window's distance versus
        the front layer's distance in the SWAP-selection score. The front
        layer always has weight 1; this is the "W" that scales the
        lookahead term (i.e. ``score = front_cost + lookahead_weight *
        lookahead_cost``).

    Returns
    -------
    (QuantumCircuit, dict[int, int])
        The routed circuit over ``coupling_map.size()`` physical qubits,
        and the final logical-to-physical mapping.

    Notes
    -----
    The lookahead window is derived from a single global topological
    ordering of the circuit's two-qubit gates computed once up front,
    rather than the DAG's precise "extended set" at each step (which
    would require re-deriving valid successors dynamically as gates
    execute out of strict topological order). For circuits where
    single-qubit gates are interleaved between two-qubit gates in the
    usual way, this is a close approximation; it is not exact for
    circuits with unusual gate orderings or heavy branching in the
    dependency DAG.
    """
    hw_graph = coupling_graph(coupling_map)
    n_physical = coupling_map.size()
    distances = dict(nx.all_pairs_shortest_path_length(hw_graph))

    if initial_layout is None:
        initial_layout = {i: i for i in range(circuit.num_qubits)}
    logical_to_physical = dict(initial_layout)
    physical_to_logical = {p: l for l, p in logical_to_physical.items()}

    dag = circuit_to_dag(circuit)
    routed = QuantumCircuit(n_physical, circuit.num_clbits)
    clbit_index = {clbit: i for i, clbit in enumerate(circuit.clbits)}

    # Global topological order of two-qubit gates, used to build the
    # lookahead window (see Notes above).
    two_qubit_sequence: list[tuple[int, int]] = []
    for node in circuit_to_dag(circuit).topological_op_nodes():
        if len(node.qargs) == 2:
            two_qubit_sequence.append(
                (circuit.qubits.index(node.qargs[0]), circuit.qubits.index(node.qargs[1]))
            )
    executed_two_qubit_count = 0

    def logical_pair(node):
        i = dag.qubits.index(node.qargs[0])
        j = dag.qubits.index(node.qargs[1])
        return i, j

    def cost_of_pair(l1, l2, tentative_swap=None):
        p1, p2 = logical_to_physical[l1], logical_to_physical[l2]
        if tentative_swap is not None:
            a, b = tentative_swap
            if p1 == a:
                p1 = b
            elif p1 == b:
                p1 = a
            if p2 == a:
                p2 = b
            elif p2 == b:
                p2 = a
        return max(distances[p1][p2] - 1, 0)

    while dag.op_nodes():
        # Step 1: execute everything immediately runnable.
        progressed = True
        while progressed:
            progressed = False
            for node in dag.front_layer():
                qargs = node.qargs
                if len(qargs) == 2:
                    l1, l2 = logical_pair(node)
                    p1, p2 = logical_to_physical[l1], logical_to_physical[l2]
                    if not hw_graph.has_edge(p1, p2):
                        continue
                    clbits = [routed.clbits[clbit_index[c]] for c in node.cargs]
                    routed.append(node.op, [routed.qubits[p1], routed.qubits[p2]], clbits)
                    dag.remove_op_node(node)
                    executed_two_qubit_count += 1
                    progressed = True
                elif len(qargs) <= 1:
                    physical_qubits = [
                        routed.qubits[logical_to_physical[dag.qubits.index(q)]] for q in qargs
                    ]
                    clbits = [routed.clbits[clbit_index[c]] for c in node.cargs]
                    routed.append(node.op, physical_qubits, clbits)
                    dag.remove_op_node(node)
                    progressed = True
                else:
                    # e.g. barriers spanning >2 qubits: translate directly.
                    physical_qubits = [
                        routed.qubits[logical_to_physical[dag.qubits.index(q)]] for q in qargs
                    ]
                    clbits = [routed.clbits[clbit_index[c]] for c in node.cargs]
                    routed.append(node.op, physical_qubits, clbits)
                    dag.remove_op_node(node)
                    progressed = True

        if not dag.op_nodes():
            break

        # Step 2: gather candidate SWAPs from qubits touched by pending
        # front-layer two-qubit gates.
        front = dag.front_layer()
        pending_pairs = [logical_pair(n) for n in front if len(n.qargs) == 2]
        active_physical = set()
        for l1, l2 in pending_pairs:
            active_physical.add(logical_to_physical[l1])
            active_physical.add(logical_to_physical[l2])

        candidates = set()
        for p in active_physical:
            for neighbor in hw_graph.neighbors(p):
                edge = tuple(sorted((p, neighbor)))
                candidates.add(edge)

        lookahead_pairs = two_qubit_sequence[
            executed_two_qubit_count : executed_two_qubit_count + lookahead_size
        ]

        # Step 3: score and apply the best candidate SWAP.
        best_swap, best_score = None, None
        for swap in sorted(candidates):
            front_cost = sum(cost_of_pair(l1, l2, swap) for l1, l2 in pending_pairs)
            lookahead_cost = sum(cost_of_pair(l1, l2, swap) for l1, l2 in lookahead_pairs)
            score = front_cost + lookahead_weight * lookahead_cost
            if best_score is None or score < best_score:
                best_score, best_swap = score, swap

        a, b = best_swap
        routed.append(SwapGate(), [routed.qubits[a], routed.qubits[b]])
        la, lb = physical_to_logical.get(a), physical_to_logical.get(b)
        physical_to_logical[a], physical_to_logical[b] = lb, la
        if la is not None:
            logical_to_physical[la] = b
        if lb is not None:
            logical_to_physical[lb] = a

    return routed, logical_to_physical


class LookaheadSwapRouter(TransformationPass):
    """PassManager-compatible wrapper around :func:`route_circuit_lookahead`.

    Reads ``property_set["layout"]`` if a prior layout pass has already
    run, otherwise routes from the identity layout. See
    :func:`route_circuit_lookahead` for the routing algorithm and its
    parameters.
    """

    def __init__(self, coupling_map: CouplingMap, lookahead_size: int = 20, lookahead_weight: float = 0.5):
        super().__init__()
        self.coupling_map = coupling_map
        self.lookahead_size = lookahead_size
        self.lookahead_weight = lookahead_weight

    def run(self, dag):
        circuit = dag_to_circuit(dag)

        layout = self.property_set.get("layout")
        if layout is not None:
            initial_layout = {
                circuit.qubits.index(qubit): physical
                for qubit, physical in layout.get_virtual_bits().items()
            }
        else:
            initial_layout = None

        routed, final_mapping = route_circuit_lookahead(
            circuit,
            self.coupling_map,
            initial_layout,
            lookahead_size=self.lookahead_size,
            lookahead_weight=self.lookahead_weight,
        )
        self.property_set["final_layout"] = Layout(
            {routed.qubits[p]: l for l, p in final_mapping.items()}
        )
        return circuit_to_dag(routed)
