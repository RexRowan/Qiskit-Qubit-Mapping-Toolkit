import numpy as np
import pytest
from qiskit.circuit import QuantumCircuit
from qiskit.quantum_info import Statevector
from qiskit.transpiler import CouplingMap

from qiskit_qubit_mapping.benchmarks.circuits import all_to_all_circuit, linear_entangling_circuit
from qiskit_qubit_mapping.routing.baseline import route_circuit


def _line_coupling_map(n):
    return CouplingMap([[i, i + 1] for i in range(n - 1)])


class TestRouteCircuit:
    def test_no_swaps_needed_when_already_adjacent(self):
        qc = linear_entangling_circuit(4)
        cmap = _line_coupling_map(4)
        routed, final_mapping = route_circuit(qc, cmap, initial_layout={0: 0, 1: 1, 2: 2, 3: 3})

        swap_count = sum(1 for instr in routed.data if instr.operation.name == "swap")
        assert swap_count == 0
        assert routed.num_qubits == 4

    def test_inserts_swaps_when_needed(self):
        qc = QuantumCircuit(3)
        qc.cx(0, 2)  # not adjacent on a line: 0-1-2
        cmap = _line_coupling_map(3)
        routed, final_mapping = route_circuit(qc, cmap, initial_layout={0: 0, 1: 1, 2: 2})

        swap_count = sum(1 for instr in routed.data if instr.operation.name == "swap")
        assert swap_count >= 1

    def test_routed_circuit_preserves_semantics_on_bell_pair(self):
        # Bell pair created on non-adjacent logical qubits 0 and 2 of a
        # 3-qubit line. After routing, the marginal distribution over the
        # physical qubits now holding logical 0 and 2 (in that order)
        # should match the marginal distribution over logical qubits 0
        # and 2 in the unrouted, ideal circuit.
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.cx(0, 2)
        cmap = _line_coupling_map(3)
        routed, final_mapping = route_circuit(qc, cmap, initial_layout={0: 0, 1: 1, 2: 2})

        ideal_state = Statevector.from_instruction(qc)
        routed_state = Statevector.from_instruction(routed)

        ideal_probs = ideal_state.probabilities([0, 2])
        routed_probs = routed_state.probabilities([final_mapping[0], final_mapping[2]])

        np.testing.assert_allclose(routed_probs, ideal_probs, atol=1e-8)

    def test_routed_circuit_preserves_semantics_on_ghz_state(self):
        qc = QuantumCircuit(4)
        qc.h(0)
        qc.cx(0, 1)
        qc.cx(1, 2)
        qc.cx(2, 3)
        cmap = _line_coupling_map(4)
        routed, final_mapping = route_circuit(qc, cmap, initial_layout={0: 0, 1: 1, 2: 2, 3: 3})

        ideal_state = Statevector.from_instruction(qc)
        routed_state = Statevector.from_instruction(routed)

        logical_order = [0, 1, 2, 3]
        physical_order = [final_mapping[l] for l in logical_order]

        ideal_probs = ideal_state.probabilities(logical_order)
        routed_probs = routed_state.probabilities(physical_order)

        np.testing.assert_allclose(routed_probs, ideal_probs, atol=1e-8)

    def test_mapping_stays_a_bijection_after_routing(self):
        qc = all_to_all_circuit(4)
        cmap = _line_coupling_map(4)
        _, final_mapping = route_circuit(qc, cmap, initial_layout={0: 0, 1: 1, 2: 2, 3: 3})

        assert len(final_mapping) == 4
        assert len(set(final_mapping.values())) == 4

    def test_routed_circuit_uses_only_coupling_map_edges_for_two_qubit_gates(self):
        qc = all_to_all_circuit(5)
        cmap = _line_coupling_map(5)
        routed, _ = route_circuit(qc, cmap, initial_layout={i: i for i in range(5)})

        allowed_edges = set()
        for i, j in cmap.get_edges():
            allowed_edges.add((i, j))
            allowed_edges.add((j, i))

        for instr in routed.data:
            if len(instr.qubits) == 2:
                q0, q1 = (routed.qubits.index(q) for q in instr.qubits)
                assert (q0, q1) in allowed_edges, f"{instr.operation.name} on ({q0},{q1}) not adjacent"
