import pytest
from qiskit.converters import circuit_to_dag
from qiskit.transpiler import CouplingMap

from qiskit_qubit_mapping.benchmarks.circuits import (
    all_to_all_circuit,
    linear_entangling_circuit,
    random_sparse_circuit,
    ring_entangling_circuit,
)
from qiskit_qubit_mapping.layout import IsomorphismLayout, WalkBasedLayout


def _line_coupling_map(n):
    return CouplingMap([[i, i + 1] for i in range(n - 1)])


def _ring_coupling_map(n):
    edges = [[i, (i + 1) % n] for i in range(n)]
    return CouplingMap(edges)


class TestIsomorphismLayout:
    def test_finds_exact_embedding_for_line_circuit_on_line_hardware(self):
        qc = linear_entangling_circuit(5)
        cmap = _line_coupling_map(5)
        layout_pass = IsomorphismLayout(cmap)
        result = layout_pass.compute_layout(circuit_to_dag(qc))

        assert result.metadata["exact_isomorphism"] is True
        assert result.score == 0

    def test_finds_exact_embedding_for_ring_circuit_on_ring_hardware(self):
        qc = ring_entangling_circuit(5)
        cmap = _ring_coupling_map(5)
        layout_pass = IsomorphismLayout(cmap)
        result = layout_pass.compute_layout(circuit_to_dag(qc))

        assert result.metadata["exact_isomorphism"] is True
        assert result.score == 0

    def test_mapping_is_a_bijection_onto_distinct_physical_qubits(self):
        qc = all_to_all_circuit(4)
        cmap = _line_coupling_map(4)
        layout_pass = IsomorphismLayout(cmap)
        result = layout_pass.compute_layout(circuit_to_dag(qc))

        assert len(result.mapping) == 4
        assert len(set(result.mapping.values())) == 4

    def test_falls_back_gracefully_when_no_isomorphism_exists(self):
        # All-to-all interaction graph cannot embed with zero SWAPs into a
        # sparse line topology -- must fall back, not crash.
        qc = all_to_all_circuit(5)
        cmap = _line_coupling_map(5)
        layout_pass = IsomorphismLayout(cmap)
        result = layout_pass.compute_layout(circuit_to_dag(qc))

        assert result.metadata["exact_isomorphism"] is False
        assert result.score > 0


class TestWalkBasedLayout:
    def test_mapping_is_a_bijection_onto_distinct_physical_qubits(self):
        qc = random_sparse_circuit(6, 8, seed=1)
        cmap = _line_coupling_map(6)
        layout_pass = WalkBasedLayout(cmap)
        result = layout_pass.compute_layout(circuit_to_dag(qc))

        assert len(result.mapping) == 6
        assert len(set(result.mapping.values())) == 6

    def test_score_is_finite_and_nonnegative(self):
        qc = random_sparse_circuit(6, 10, seed=2)
        cmap = _line_coupling_map(6)
        layout_pass = WalkBasedLayout(cmap)
        result = layout_pass.compute_layout(circuit_to_dag(qc))

        assert result.score >= 0
        assert result.score == result.score  # not NaN

    def test_handles_circuit_with_no_two_qubit_gates(self):
        from qiskit.circuit import QuantumCircuit

        qc = QuantumCircuit(4)
        qc.h(0)
        qc.x(1)
        cmap = _line_coupling_map(4)
        layout_pass = WalkBasedLayout(cmap)
        result = layout_pass.compute_layout(circuit_to_dag(qc))

        assert len(result.mapping) == 4
        assert result.score == 0
