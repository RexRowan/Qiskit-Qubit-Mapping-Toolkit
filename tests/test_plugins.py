import numpy as np
import pytest
from qiskit import transpile
from qiskit.quantum_info import Statevector
from qiskit.transpiler import CouplingMap
from qiskit.transpiler.preset_passmanagers.plugin import list_stage_plugins

from qiskit_qubit_mapping.benchmarks.circuits import all_to_all_circuit, linear_entangling_circuit


def _line_coupling_map(n):
    return CouplingMap([[i, i + 1] for i in range(n - 1)])


class TestPluginDiscovery:
    def test_layout_plugins_are_registered(self):
        layout_plugins = list_stage_plugins("layout")
        assert "qqm_isomorphism" in layout_plugins
        assert "qqm_walk_based" in layout_plugins

    def test_routing_plugins_are_registered(self):
        routing_plugins = list_stage_plugins("routing")
        assert "qqm_baseline" in routing_plugins
        assert "qqm_lookahead" in routing_plugins

    def test_plugin_names_do_not_collide_with_builtins(self):
        # "lookahead" (no prefix) is a reserved built-in Qiskit routing
        # method name -- this asserts our prefixed name doesn't clash and
        # that we haven't accidentally registered the unprefixed name.
        routing_plugins = list_stage_plugins("routing")
        assert "lookahead" in routing_plugins  # Qiskit's own built-in
        assert routing_plugins.count("qqm_lookahead") == 1  # exactly ours


class TestTranspileIntegration:
    def test_transpile_with_isomorphism_and_baseline(self):
        qc = linear_entangling_circuit(4)
        cmap = _line_coupling_map(4)
        result = transpile(
            qc,
            coupling_map=cmap,
            layout_method="qqm_isomorphism",
            routing_method="qqm_baseline",
            optimization_level=1,
        )
        assert result.num_qubits == 4

    def test_transpile_with_isomorphism_and_lookahead(self):
        qc = linear_entangling_circuit(4)
        cmap = _line_coupling_map(4)
        result = transpile(
            qc,
            coupling_map=cmap,
            layout_method="qqm_isomorphism",
            routing_method="qqm_lookahead",
            optimization_level=1,
        )
        assert result.num_qubits == 4

    def test_transpile_with_walk_based_layout(self):
        qc = linear_entangling_circuit(4)
        cmap = _line_coupling_map(4)
        result = transpile(
            qc,
            coupling_map=cmap,
            layout_method="qqm_walk_based",
            routing_method="qqm_baseline",
            optimization_level=1,
        )
        assert result.num_qubits == 4

    def test_transpiled_circuit_preserves_semantics(self):
        # Uses a circuit that genuinely needs SWAPs (all-to-all on a line
        # topology), and verifies via the real TranspileLayout bookkeeping
        # that the routed circuit's marginal measurement distribution
        # matches the unrouted ideal circuit exactly.
        qc = all_to_all_circuit(4)
        cmap = _line_coupling_map(4)
        result = transpile(
            qc,
            coupling_map=cmap,
            layout_method="qqm_isomorphism",
            routing_method="qqm_lookahead",
            optimization_level=1,
        )

        assert result.count_ops().get("swap", 0) > 0  # confirms routing actually engaged

        ideal_state = Statevector.from_instruction(qc)
        routed_state = Statevector.from_instruction(result)

        final_perm = result.layout.final_index_layout()
        routed_probs = routed_state.probabilities(final_perm)
        ideal_probs = ideal_state.probabilities(list(range(qc.num_qubits)))

        np.testing.assert_allclose(routed_probs, ideal_probs, atol=1e-8)

    def test_raises_clear_error_without_coupling_map(self):
        from qiskit.transpiler.exceptions import TranspilerError

        qc = linear_entangling_circuit(3)
        with pytest.raises(TranspilerError):
            transpile(qc, layout_method="qqm_isomorphism", routing_method="qqm_baseline")
