"""Internal helpers shared by the layout and routing modules.

Not part of the public API -- import from :mod:`qiskit_qubit_mapping`
top-level or the ``layout``/``routing``/``metrics`` subpackages instead.
"""

from __future__ import annotations

import networkx as nx
from qiskit.circuit import QuantumCircuit
from qiskit.transpiler import CouplingMap


def interaction_graph(circuit: QuantumCircuit, weighted: bool = True) -> nx.Graph:
    """Build the two-qubit interaction graph of a circuit.

    Nodes are logical qubit indices. An edge ``(i, j)`` is added for every
    two-qubit gate acting on qubits ``i`` and ``j``; if ``weighted`` is
    True, the edge weight is the number of such gates (a proxy for how
    costly it is to keep that pair far apart on hardware).

    Parameters
    ----------
    circuit:
        The logical circuit to analyze.
    weighted:
        Whether to accumulate a ``weight`` attribute counting repeated
        interactions between the same pair of qubits.

    Returns
    -------
    networkx.Graph
        Graph with one node per logical qubit (including qubits with no
        two-qubit interactions, so indices line up with ``circuit.qubits``).
    """
    graph = nx.Graph()
    graph.add_nodes_from(range(circuit.num_qubits))

    qubit_index = {qubit: i for i, qubit in enumerate(circuit.qubits)}

    for instruction in circuit.data:
        qubits = instruction.qubits
        if len(qubits) != 2:
            continue
        i, j = qubit_index[qubits[0]], qubit_index[qubits[1]]
        if i == j:
            continue
        if graph.has_edge(i, j):
            if weighted:
                graph[i][j]["weight"] += 1
        else:
            graph.add_edge(i, j, weight=1)

    return graph


def coupling_graph(coupling_map: CouplingMap) -> nx.Graph:
    """Convert a Qiskit :class:`CouplingMap` into an undirected networkx graph.

    Directed edges in the coupling map collapse to a single undirected edge
    (most current hardware supports bidirectional two-qubit gates after
    Qiskit's own direction-fixing pass, and for placement/routing purposes
    only reachability matters).
    """
    graph = nx.Graph()
    graph.add_nodes_from(range(coupling_map.size()))
    for i, j in coupling_map.get_edges():
        graph.add_edge(i, j)
    return graph


def total_edge_distance(interaction: nx.Graph, hw_graph: nx.Graph, layout: dict[int, int]) -> int:
    """Sum of expected SWAP counts for every interacting pair under ``layout``.

    ``layout`` maps logical qubit index -> physical qubit index. For a
    pair placed at hardware distance ``d`` (shortest-path hop count),
    bringing them adjacent costs ``d - 1`` SWAPs (``d == 1`` means already
    adjacent, i.e. zero SWAPs). This is a cheap proxy for expected routing
    cost, used to score and compare layouts before any routing pass runs.
    """
    distances = dict(nx.all_pairs_shortest_path_length(hw_graph))
    total = 0
    for i, j, data in interaction.edges(data=True):
        weight = data.get("weight", 1)
        pi, pj = layout[i], layout[j]
        total += weight * max(distances[pi][pj] - 1, 0)
    return total
