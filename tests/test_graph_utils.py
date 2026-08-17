from qiskit.circuit import QuantumCircuit
from qiskit.transpiler import CouplingMap

from qiskit_qubit_mapping._graph_utils import coupling_graph, interaction_graph, total_edge_distance


def test_interaction_graph_basic():
    qc = QuantumCircuit(3)
    qc.h(0)
    qc.cx(0, 1)
    qc.cx(0, 1)  # repeated pair -> weight 2
    qc.cx(1, 2)

    graph = interaction_graph(qc)
    assert set(graph.nodes) == {0, 1, 2}
    assert graph[0][1]["weight"] == 2
    assert graph[1][2]["weight"] == 1


def test_interaction_graph_includes_isolated_qubits():
    qc = QuantumCircuit(4)
    qc.cx(0, 1)
    graph = interaction_graph(qc)
    assert set(graph.nodes) == {0, 1, 2, 3}
    assert graph.degree(2) == 0
    assert graph.degree(3) == 0


def test_coupling_graph_undirected():
    cmap = CouplingMap([[0, 1], [1, 2]])
    graph = coupling_graph(cmap)
    assert graph.has_edge(0, 1)
    assert graph.has_edge(1, 0)
    assert graph.has_edge(1, 2)
    assert graph.number_of_nodes() == 3


def test_total_edge_distance_zero_for_adjacent_layout():
    qc = QuantumCircuit(2)
    qc.cx(0, 1)
    interaction = interaction_graph(qc)
    cmap = CouplingMap([[0, 1]])
    hw_graph = coupling_graph(cmap)
    distance = total_edge_distance(interaction, hw_graph, {0: 0, 1: 1})
    assert distance == 0


def test_total_edge_distance_counts_hops():
    qc = QuantumCircuit(2)
    qc.cx(0, 1)
    interaction = interaction_graph(qc)
    cmap = CouplingMap([[0, 1], [1, 2]])
    hw_graph = coupling_graph(cmap)
    # logical 0 -> physical 0, logical 1 -> physical 2: 2 hops apart,
    # so bringing them adjacent costs 1 SWAP.
    distance = total_edge_distance(interaction, hw_graph, {0: 0, 1: 2})
    assert distance == 1
