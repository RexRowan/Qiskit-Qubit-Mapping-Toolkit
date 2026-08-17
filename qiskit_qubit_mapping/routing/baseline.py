from __future__ import annotations

import networkx as nx
from qiskit.circuit import QuantumCircuit
from qiskit.circuit.library import SwapGate
from qiskit.converters import circuit_to_dag, dag_to_circuit
from qiskit.transpiler import CouplingMap, Layout
from qiskit.transpiler.basepasses import TransformationPass

from qiskit_qubit_mapping._graph_utils import coupling_graph


def route_circuit(
    circuit: QuantumCircuit,
    coupling_map: CouplingMap,
    initial_layout: dict[int, int] | None = None,
) -> tuple[QuantumCircuit, dict[int, int]]:
    """Route ``circuit`` onto ``coupling_map`` with greedy shortest-path SWAP insertion.

    This is a deliberately simple, easy-to-verify baseline: process gates
    in topological order and, whenever a two-qubit gate's operands are not
    adjacent on the device, insert SWAPs one step at a time along the
    shortest hardware path between them until they are. It does not do
    any lookahead or SWAP-choice optimization the way Sabre does -- it
    exists as a correctness-first reference implementation and a floor
    that smarter layout heuristics (see :mod:`qiskit_qubit_mapping.layout`)
    can be measured against via :mod:`qiskit_qubit_mapping.metrics`.

    Parameters
    ----------
    circuit:
        Logical circuit, defined over ``circuit.num_qubits`` logical qubits.
    coupling_map:
        Target hardware topology.
    initial_layout:
        Logical qubit index -> physical qubit index. Defaults to the
        identity mapping (logical qubit ``i`` starts on physical qubit
        ``i``) if not provided, or the output of a prior layout pass when
        called via :class:`BaselineSwapRouter`.

    Returns
    -------
    (QuantumCircuit, dict[int, int])
        The routed circuit, defined over ``coupling_map.size()`` physical
        qubits, and the final logical-to-physical mapping after all
        inserted SWAPs (needed to interpret measurement results or to
        chain further passes).
    """
    hw_graph = coupling_graph(coupling_map)
    n_physical = coupling_map.size()

    if initial_layout is None:
        initial_layout = {i: i for i in range(circuit.num_qubits)}

    logical_to_physical = dict(initial_layout)
    physical_to_logical = {p: l for l, p in logical_to_physical.items()}

    routed = QuantumCircuit(n_physical, circuit.num_clbits)

    distances = dict(nx.all_pairs_shortest_path_length(hw_graph))
    qubit_index = {qubit: i for i, qubit in enumerate(circuit.qubits)}
    clbit_index = {clbit: i for i, clbit in enumerate(circuit.clbits)}

    for instruction in circuit.data:
        op = instruction.operation
        logical_qubits = [qubit_index[q] for q in instruction.qubits]
        clbits = [routed.clbits[clbit_index[c]] for c in instruction.clbits]

        if len(logical_qubits) == 2:
            l1, l2 = logical_qubits
            p1, p2 = logical_to_physical[l1], logical_to_physical[l2]

            if distances[p1][p2] > 1:
                path = nx.shortest_path(hw_graph, p1, p2)
                # Walk the qubit at p1 down the path towards p2, one SWAP
                # per hop, until it lands adjacent to p2.
                for a, b in zip(path[:-2], path[1:-1]):
                    routed.append(SwapGate(), [routed.qubits[a], routed.qubits[b]])
                    la, lb = physical_to_logical.get(a), physical_to_logical.get(b)
                    physical_to_logical[a], physical_to_logical[b] = lb, la
                    if la is not None:
                        logical_to_physical[la] = b
                    if lb is not None:
                        logical_to_physical[lb] = a
                p1 = logical_to_physical[l1]

            routed.append(op, [routed.qubits[p1], routed.qubits[p2]])

        elif len(logical_qubits) == 1:
            p = logical_to_physical[logical_qubits[0]]
            routed.append(op, [routed.qubits[p]], clbits)

        elif len(logical_qubits) == 0:
            routed.append(op, [], clbits)

        else:
            physical_qubits = [routed.qubits[logical_to_physical[l]] for l in logical_qubits]
            routed.append(op, physical_qubits, clbits)

    return routed, logical_to_physical


class BaselineSwapRouter(TransformationPass):
    """PassManager-compatible wrapper around :func:`route_circuit`.

    Reads ``property_set["layout"]`` if a prior layout pass (e.g.
    :class:`~qiskit_qubit_mapping.layout.IsomorphismLayout` or
    :class:`~qiskit_qubit_mapping.layout.WalkBasedLayout`) has already run,
    otherwise routes from the identity layout.
    """

    def __init__(self, coupling_map: CouplingMap):
        super().__init__()
        self.coupling_map = coupling_map

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

        routed, final_mapping = route_circuit(circuit, self.coupling_map, initial_layout)
        self.property_set["final_layout"] = Layout(
            {routed.qubits[p]: l for l, p in final_mapping.items()}
        )
        return circuit_to_dag(routed)
