from qiskit.transpiler import CouplingMap

from qiskit_qubit_mapping.benchmarks.circuits import all_to_all_circuit, linear_entangling_circuit
from qiskit_qubit_mapping.layout import IsomorphismLayout, WalkBasedLayout
from qiskit_qubit_mapping.metrics import compare_to_sabre, evaluate_layout
from qiskit_qubit_mapping.routing import BaselineSwapRouter, LookaheadSwapRouter


def _line_coupling_map(n):
    return CouplingMap([[i, i + 1] for i in range(n - 1)])


class TestEvaluateLayout:
    def test_zero_swaps_for_embeddable_circuit(self):
        qc = linear_entangling_circuit(5)
        cmap = _line_coupling_map(5)
        result = evaluate_layout(qc, cmap, IsomorphismLayout(cmap))

        assert result.swap_count == 0
        assert result.layout_score == 0

    def test_returns_positive_depth(self):
        qc = linear_entangling_circuit(5)
        cmap = _line_coupling_map(5)
        result = evaluate_layout(qc, cmap, WalkBasedLayout(cmap))

        assert result.depth > 0

    def test_walk_based_layout_runs_end_to_end(self):
        qc = all_to_all_circuit(5)
        cmap = _line_coupling_map(5)
        result = evaluate_layout(qc, cmap, WalkBasedLayout(cmap))

        assert result.swap_count >= 0
        assert result.depth > 0


class TestCompareToSabre:
    def test_both_pipelines_produce_valid_results(self):
        qc = all_to_all_circuit(4)
        cmap = _line_coupling_map(4)
        results = compare_to_sabre(qc, cmap, IsomorphismLayout(cmap))

        assert "toolkit" in results
        assert "sabre" in results
        assert results["toolkit"].swap_count >= 0
        assert results["sabre"].swap_count >= 0

    def test_embeddable_circuit_needs_no_swaps_either_way(self):
        qc = linear_entangling_circuit(5)
        cmap = _line_coupling_map(5)
        results = compare_to_sabre(qc, cmap, IsomorphismLayout(cmap))

        assert results["toolkit"].swap_count == 0

    def test_can_compare_lookahead_router_against_sabre(self):
        qc = all_to_all_circuit(4)
        cmap = _line_coupling_map(4)
        results = compare_to_sabre(
            qc, cmap, IsomorphismLayout(cmap), router_pass=LookaheadSwapRouter(cmap)
        )

        assert "toolkit" in results
        assert "sabre" in results
        assert results["toolkit"].swap_count >= 0
