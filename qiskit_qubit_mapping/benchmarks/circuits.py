"""A handful of small, dependency-free benchmark circuits.

These are intentionally simple (no external benchmark-suite dependency)
so the test suite and README examples are self-contained. For larger-scale
comparisons against Sabre, point :func:`~qiskit_qubit_mapping.metrics.compare_to_sabre`
at circuits from QASMBench or MQT Bench instead.
"""

from __future__ import annotations

from qiskit.circuit import QuantumCircuit


def linear_entangling_circuit(n_qubits: int) -> QuantumCircuit:
    """A circuit whose interaction graph is a path graph 0-1-2-...-(n-1).

    Embeds with zero SWAPs on any coupling map containing a Hamiltonian
    path (e.g. heavy-hex, linear, ring topologies), which makes it a good
    sanity check for :class:`~qiskit_qubit_mapping.layout.IsomorphismLayout`.
    """
    qc = QuantumCircuit(n_qubits)
    for i in range(n_qubits - 1):
        qc.h(i)
        qc.cx(i, i + 1)
    return qc


def all_to_all_circuit(n_qubits: int) -> QuantumCircuit:
    """A circuit whose interaction graph is complete (every qubit pair
    interacts). Not embeddable without SWAPs on any sparse hardware
    topology -- exercises the greedy/assignment fallback paths.
    """
    qc = QuantumCircuit(n_qubits)
    for i in range(n_qubits):
        qc.h(i)
    for i in range(n_qubits):
        for j in range(i + 1, n_qubits):
            qc.cx(i, j)
    return qc


def ring_entangling_circuit(n_qubits: int) -> QuantumCircuit:
    """A circuit whose interaction graph is a ring 0-1-2-...-(n-1)-0."""
    qc = QuantumCircuit(n_qubits)
    for i in range(n_qubits):
        qc.h(i)
        qc.cx(i, (i + 1) % n_qubits)
    return qc


def random_sparse_circuit(n_qubits: int, n_two_qubit_gates: int, seed: int = 0) -> QuantumCircuit:
    """A circuit with random two-qubit interactions, roughly ``n_qubits``
    edges (sparse), useful as a "typical" mid-difficulty case between the
    embeddable and all-to-all extremes.
    """
    import random

    rng = random.Random(seed)
    qc = QuantumCircuit(n_qubits)
    for i in range(n_qubits):
        qc.h(i)
    for _ in range(n_two_qubit_gates):
        i, j = rng.sample(range(n_qubits), 2)
        qc.cx(i, j)
    return qc
