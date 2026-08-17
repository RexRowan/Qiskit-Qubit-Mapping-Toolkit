from __future__ import annotations

import networkx as nx
import numpy as np
from scipy.linalg import expm
from scipy.optimize import linear_sum_assignment

from qiskit_qubit_mapping._graph_utils import coupling_graph, interaction_graph, total_edge_distance
from qiskit_qubit_mapping.layout.base import LayoutHeuristic, LayoutResult


def _ctqw_node_features(graph: nx.Graph, times: tuple[float, ...]) -> np.ndarray:
    """Continuous-time quantum walk structural signature for every node.

    For a graph with adjacency matrix ``A``, the CTQW propagator is
    ``U(t) = exp(-i A t)``. The return probability ``|U(t)[v, v]|^2`` and
    the Shannon entropy of the row ``|U(t)[v, :]|^2`` are both permutation
    -equivariant structural descriptors of node ``v``'s local
    connectivity: a node in a dense, well-connected neighborhood mixes
    (spreads probability, low return probability, high entropy) faster
    than a node on a sparse periphery. Because the descriptor is a small
    vector of scalars rather than a full N-length distribution, it can be
    compared directly between graphs of different sizes -- which is
    exactly what's needed to score a logical qubit against a physical
    qubit for a candidate assignment.

    Multiple time points are concatenated to capture both short-time
    (local degree-dominated) and longer-time (larger neighborhood) mixing
    behavior.
    """
    n = graph.number_of_nodes()
    nodes = list(graph.nodes)
    index = {node: i for i, node in enumerate(nodes)}
    adjacency = nx.to_numpy_array(graph, nodelist=nodes, weight="weight")

    features = np.zeros((n, 2 * len(times)))
    for t_idx, t in enumerate(times):
        propagator = expm(-1j * adjacency * t)
        probabilities = np.abs(propagator) ** 2  # row-stochastic (unitary => sums to 1)
        return_prob = np.diag(probabilities)
        with np.errstate(divide="ignore", invalid="ignore"):
            row_entropy = -np.nansum(
                np.where(probabilities > 0, probabilities * np.log(probabilities), 0.0), axis=1
            )
        features[:, 2 * t_idx] = return_prob
        features[:, 2 * t_idx + 1] = row_entropy

    return features, index


def _zscore(features: np.ndarray) -> np.ndarray:
    mean = features.mean(axis=0, keepdims=True)
    std = features.std(axis=0, keepdims=True)
    std[std == 0] = 1.0
    return (features - mean) / std


class WalkBasedLayout(LayoutHeuristic):
    """Layout scored via continuous-time quantum walk (CTQW) mixing
    signatures, extending the walk machinery from ``qiskit-graph-walks``
    to the placement problem.

    Rather than searching for an exact structural embedding (as
    :class:`~qiskit_qubit_mapping.layout.isomorphism.IsomorphismLayout`
    does), this heuristic characterizes every logical and physical qubit
    by how quickly probability mixes outward from it under a CTQW, then
    solves a linear assignment problem to match logical qubits to
    physical qubits with the most similar mixing behavior -- the
    intuition being that highly-connected logical qubits (which mix fast)
    should land on highly-connected physical qubits, and so on down the
    connectivity spectrum. This tends to do better than
    :class:`IsomorphismLayout`'s greedy fallback on circuits whose
    interaction graph is *not* embeddable in the coupling map, since it
    optimizes a smooth similarity score rather than an all-or-nothing
    subgraph match.

    Parameters
    ----------
    coupling_map:
        Target hardware topology.
    times:
        CTQW evolution times sampled to build each node's mixing
        signature. Defaults capture short-, medium-, and longer-range
        mixing behavior; larger/denser graphs may benefit from including
        smaller times to avoid saturating entropy too early.
    """

    def __init__(self, coupling_map, times: tuple[float, ...] = (0.5, 1.0, 2.0)):
        super().__init__(coupling_map)
        self.times = times

    def compute_layout(self, dag) -> LayoutResult:
        from qiskit_qubit_mapping.layout.isomorphism import dag_to_circuit_like

        circuit = dag_to_circuit_like(dag)
        interaction = interaction_graph(circuit)
        hw_graph = coupling_graph(self.coupling_map)

        mapping = self._assign(interaction, hw_graph)
        score = total_edge_distance(interaction, hw_graph, mapping)
        return LayoutResult(
            mapping=mapping,
            score=score,
            metadata={"times": self.times, "num_logical_qubits": interaction.number_of_nodes()},
        )

    def _assign(self, interaction: nx.Graph, hw_graph: nx.Graph) -> dict[int, int]:
        logical_features, logical_index = _ctqw_node_features(interaction, self.times)
        physical_features, physical_index = _ctqw_node_features(hw_graph, self.times)

        logical_z = _zscore(logical_features)
        physical_z = _zscore(physical_features)

        # cost[i, j] = distance between logical qubit i's and physical
        # qubit j's mixing signature; linear_sum_assignment finds the
        # globally cheapest one-to-one assignment (Hungarian algorithm).
        diff = logical_z[:, None, :] - physical_z[None, :, :]
        cost = np.linalg.norm(diff, axis=2)

        row_ind, col_ind = linear_sum_assignment(cost)

        logical_nodes = list(interaction.nodes)
        physical_nodes = list(hw_graph.nodes)
        return {logical_nodes[r]: physical_nodes[c] for r, c in zip(row_ind, col_ind)}
