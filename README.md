# Qiskit Qubit Mapping Toolkit

Graph-theoretic **initial layout** and **routing** heuristics for mapping logical Qiskit circuits onto hardware coupling maps.

This project fills a gap in my own [Qiskit Ecosystem](https://www.ibm.com/quantum/ecosystem) portfolio: prior projects ([`qiskit-graph-walks`](https://github.com/RexRowan/qiskit-graph-walks), [`qiskit-zx-verified`](https://github.com/RexRowan/qiskit-zx-verified), [`qiskit-lean-bridge`](https://github.com/RexRowan/qiskit-lean-bridge), etc.) analyze, verify, or visualize circuits, but none of them touch the compilation/transpilation pipeline — getting a circuit *onto* real hardware efficiently. This toolkit is a first step into that space, built around two ideas:

1. **`IsomorphismLayout`** — search for a zero-SWAP embedding of the circuit's interaction graph into the device coupling graph via VF2 subgraph isomorphism, falling back to a degree-greedy placement when no exact embedding exists.
2. **`WalkBasedLayout`** — score candidate qubit assignments using continuous-time quantum walk (CTQW) mixing signatures, extending the walk machinery from `qiskit-graph-walks` to the placement problem, then solve the resulting assignment via the Hungarian algorithm.

Both plug into either a baseline shortest-path **SWAP router** or a **lookahead SWAP router** (Sabre-style candidate scoring over a front layer plus an upcoming-gates window), and an evaluation harness that benchmarks results against Qiskit's built-in `SabreLayout` + `SabreSwap`.

All four passes are also registered as **Qiskit transpiler stage plugins**, so they work directly through `transpile()` — see [Using it through `transpile()`](#using-it-through-transpile) below.

## Honest framing

This is a **research/pedagogical toolkit**, not a production replacement for Sabre. `BaselineSwapRouter` is a deliberately simple, easy-to-verify shortest-path SWAP inserter with no lookahead or SWAP-choice optimization — it exists as a correctness-first reference implementation so the *layout* heuristics can be measured on a level playing field, and as a floor to compare smarter routing against. `LookaheadSwapRouter` builds on that floor with a Sabre-style scoring function (front layer + weighted lookahead window) and closes most of the gap: on a 19-qubit heavy-hex topology it beats Sabre's SWAP count on structured circuits (line, ring) and comes within a few SWAPs on denser random circuits — see [`docs/algorithm_notes.md`](docs/algorithm_notes.md) for the full table. Where this toolkit wins outright regardless of router is on circuits whose interaction graph is exactly embeddable: `IsomorphismLayout` finds the zero-SWAP embedding directly rather than converging to it iteratively.

## Install

```bash
pip install qiskit-qubit-mapping-toolkit
```

Or from source:

```bash
git clone https://github.com/RexRowan/qiskit-qubit-mapping-toolkit
cd qiskit-qubit-mapping-toolkit
pip install -e ".[dev]"
```

Requires `qiskit>=2.0,<3` (this project's standard version bound across the Ecosystem portfolio).

## Using it through `transpile()`

Every layout heuristic and router is also registered as a Qiskit transpiler stage plugin, so you don't need to import anything from this package at all:

```python
from qiskit import transpile

transpiled = transpile(
    circuit,
    coupling_map=coupling_map,
    layout_method="qqm_isomorphism",   # or "qqm_walk_based"
    routing_method="qqm_lookahead",    # or "qqm_baseline"
)
```

Plugin names are prefixed with `qqm_` to avoid colliding with Qiskit's own built-in plugin names — notably `"lookahead"` (no prefix) is already a reserved built-in routing method. See registered names any time with:

```python
from qiskit.transpiler.preset_passmanagers.plugin import list_stage_plugins

list_stage_plugins("layout")    # [..., "qqm_isomorphism", "qqm_walk_based"]
list_stage_plugins("routing")   # [..., "qqm_baseline", "qqm_lookahead"]
```

## Quickstart

```python
from qiskit.transpiler import CouplingMap
from qiskit_qubit_mapping.benchmarks.circuits import linear_entangling_circuit
from qiskit_qubit_mapping.layout import IsomorphismLayout
from qiskit_qubit_mapping.metrics import compare_to_sabre

cmap = CouplingMap([[i, i + 1] for i in range(6)])   # a 7-qubit line
qc = linear_entangling_circuit(7)                     # interaction graph is also a line

results = compare_to_sabre(qc, cmap, IsomorphismLayout(cmap))
print(results["toolkit"])  # EvaluationResult(swap_count=0, depth=...)
print(results["sabre"])
```

For circuits without an exact embedding, use `WalkBasedLayout` instead, or run both and compare:

```python
from qiskit_qubit_mapping.layout import WalkBasedLayout
from qiskit_qubit_mapping.metrics import evaluate_layout

result = evaluate_layout(qc, cmap, WalkBasedLayout(cmap))
print(result.swap_count, result.depth, result.layout_score)
```

For denser circuits, swap in the lookahead router — it's the toolkit's strongest routing option and the one to reach for by default once you're past quick correctness checks:

```python
from qiskit_qubit_mapping.routing import LookaheadSwapRouter

result = evaluate_layout(qc, cmap, IsomorphismLayout(cmap), router_pass=LookaheadSwapRouter(cmap))
print(result.swap_count, result.depth)
```

Both layout heuristics are standard Qiskit `AnalysisPass` subclasses and compose with `BaselineSwapRouter` in a `PassManager`:

```python
from qiskit.transpiler import PassManager
from qiskit_qubit_mapping import IsomorphismLayout, BaselineSwapRouter

pm = PassManager([IsomorphismLayout(cmap), BaselineSwapRouter(cmap)])
routed_circuit = pm.run(qc)
```

## What's in the package

| Module | Contents |
|---|---|
| `qiskit_qubit_mapping.layout` | `IsomorphismLayout`, `WalkBasedLayout`, shared `LayoutResult` dataclass |
| `qiskit_qubit_mapping.routing` | `BaselineSwapRouter`, `LookaheadSwapRouter`, functional `route_circuit()` / `route_circuit_lookahead()` |
| `qiskit_qubit_mapping.metrics` | `evaluate_layout()`, `compare_to_sabre()`, `EvaluationResult` |
| `qiskit_qubit_mapping.benchmarks` | Small dependency-free benchmark circuit generators (line, ring, all-to-all, random-sparse) |

See [`docs/usage.md`](docs/usage.md) for a full walkthrough of each heuristic, and [`docs/algorithm_notes.md`](docs/algorithm_notes.md) for the reasoning behind the CTQW scoring function and measured Sabre comparisons.

## Testing

```bash
pip install -e ".[test]"
pytest tests/ -v
```

The test suite includes statevector-fidelity checks (`tests/test_routing.py`, `tests/test_lookahead_routing.py`) that verify both `BaselineSwapRouter`'s and `LookaheadSwapRouter`'s SWAP insertion is semantics-preserving, not just "runs without crashing" — routing a Bell pair, a GHZ state, and a denser random circuit across non-adjacent physical qubits and confirming the marginal measurement distributions match the unrouted circuit exactly. There's also a direct regression test that `LookaheadSwapRouter` never uses more SWAPs than `BaselineSwapRouter` on the same circuit.

## Roadmap

- [ ] Noise-aware layout scoring incorporating backend calibration data (readout/gate error rates), not just topology
- [ ] Bidirectional/iterative layout refinement (Sabre-style forward-backward passes) to close the remaining gap on very dense circuits
- [ ] Lean 4 verification that both routers' SWAP insertion preserves circuit semantics in general, extending the verification approach from `qiskit-zx-verified`

## License

Apache 2.0 — see [LICENSE](LICENSE).
