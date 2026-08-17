from __future__ import annotations

import networkx as nx
from networkx.algorithms.isomorphism import GraphMatcher

from qiskit_qubit_mapping._graph_utils import coupling_graph, interaction_graph, total_edge_distance
from qiskit_qubit_mapping.layout.base import LayoutHeuristic, LayoutResult


class IsomorphismLayout(LayoutHeuristic):
    """Layout via VF2-based subgraph isomorphism search.

    Attempts to find a subgraph of the hardware coupling graph that is
    isomorphic to the circuit's interaction graph, i.e. a placement that
    needs *zero* SWAPs. This only succeeds when the interaction graph is
    "hardware-friendly" (sparse and locally similar to the device
    topology, e.g. line/ring/tree-shaped circuits on heavy-hex hardware).

    When no exact (subgraph-)isomorphism exists within ``time_budget``
    candidates, falls back to a greedy placement that minimizes
    :func:`~qiskit_qubit_mapping._graph_utils.total_edge_distance`,
    matching the highest-degree logical qubits to the highest-degree
    physical qubits first.

    Parameters
    ----------
    coupling_map:
        Target hardware topology.
    time_budget:
        Maximum number of candidate mappings the VF2 search will examine
        before giving up and falling back to the greedy heuristic. VF2
        subgraph isomorphism is worst-case exponential, so this bounds
        runtime on circuits whose interaction graph is not embeddable.
    """

    def __init__(self, coupling_map, time_budget: int = 50_000):
        super().__init__(coupling_map)
        self.time_budget = time_budget

    def compute_layout(self, dag) -> LayoutResult:
        circuit = dag_to_circuit_like(dag)
        interaction = interaction_graph(circuit)
        hw_graph = coupling_graph(self.coupling_map)

        mapping, exact = self._search_isomorphism(interaction, hw_graph)
        if mapping is None:
            mapping = self._greedy_fallback(interaction, hw_graph)
            exact = False

        score = total_edge_distance(interaction, hw_graph, mapping)
        return LayoutResult(
            mapping=mapping,
            score=score,
            metadata={"exact_isomorphism": exact, "num_logical_qubits": interaction.number_of_nodes()},
        )

    def _search_isomorphism(self, interaction: nx.Graph, hw_graph: nx.Graph):
        """Try to find a zero-SWAP embedding via VF2 subgraph matching.

        Isolated logical qubits (no two-qubit interactions) are dropped
        before matching -- they can be placed on any leftover physical
        qubit -- then reinserted afterwards.
        """
        active = [n for n in interaction.nodes if interaction.degree(n) > 0]
        idle = [n for n in interaction.nodes if interaction.degree(n) == 0]
        sub_interaction = interaction.subgraph(active).copy()

        if sub_interaction.number_of_nodes() == 0:
            # No two-qubit interactions at all; any bijection works.
            physical = list(hw_graph.nodes)[: interaction.number_of_nodes()]
            return {logical: physical[i] for i, logical in enumerate(interaction.nodes)}, True

        matcher = GraphMatcher(hw_graph, sub_interaction)
        count = 0
        for physical_to_logical in matcher.subgraph_isomorphisms_iter():
            count += 1
            if count > self.time_budget:
                break
            mapping = {logical: physical for physical, logical in physical_to_logical.items()}
            used_physical = set(mapping.values())
            free_physical = [p for p in hw_graph.nodes if p not in used_physical]
            for i, logical in enumerate(idle):
                mapping[logical] = free_physical[i]
            return mapping, True

        return None, False

    def _greedy_fallback(self, interaction: nx.Graph, hw_graph: nx.Graph) -> dict[int, int]:
        """Degree-greedy placement: highest-interaction-degree logical
        qubits go on highest-hardware-degree physical qubits, breaking
        ties by preferring physical neighbors of already-placed qubits.
        """
        logical_order = sorted(interaction.nodes, key=lambda n: interaction.degree(n))
        logical_order.reverse()

        physical_order = sorted(hw_graph.nodes, key=lambda n: hw_graph.degree(n), reverse=True)

        mapping: dict[int, int] = {}
        used_physical: set[int] = set()

        for logical in logical_order:
            placed_neighbors = [
                mapping[n] for n in interaction.neighbors(logical) if n in mapping
            ]
            candidate = None
            if placed_neighbors:
                # Prefer a free physical qubit adjacent to an already-placed
                # neighbor, closest by hardware distance if none are adjacent.
                distances = dict(nx.single_source_shortest_path_length(hw_graph, placed_neighbors[0]))
                for phys in sorted(distances, key=distances.get):
                    if phys not in used_physical:
                        candidate = phys
                        break
            if candidate is None:
                for phys in physical_order:
                    if phys not in used_physical:
                        candidate = phys
                        break
            mapping[logical] = candidate
            used_physical.add(candidate)

        return mapping


def dag_to_circuit_like(dag):
    """Adapter so :func:`interaction_graph` (which reads ``.data`` /
    ``.qubits`` off a QuantumCircuit) can be driven from a DAGCircuit as
    seen inside a transpiler pass, without a full DAG-to-circuit
    conversion.
    """

    class _View:
        pass

    view = _View()
    view.qubits = dag.qubits
    view.num_qubits = dag.num_qubits()
    view.data = [
        type("Instr", (), {"qubits": node.qargs})()
        for node in dag.topological_op_nodes()
    ]
    return view
