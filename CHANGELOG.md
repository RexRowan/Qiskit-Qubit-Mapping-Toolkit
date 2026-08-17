# Changelog

All notable changes to this project are documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.1] - 2026-08-15

### Added
- `IsomorphismLayout`: VF2 subgraph-isomorphism-based initial layout, with degree-greedy fallback when no exact zero-SWAP embedding exists.
- `WalkBasedLayout`: continuous-time quantum walk (CTQW) mixing-signature layout heuristic, extending the walk machinery from `qiskit-graph-walks` to the placement problem.
- `BaselineSwapRouter`: shortest-path SWAP routing pass, verified semantics-preserving via statevector fidelity tests.
- `LookaheadSwapRouter`: Sabre-style SWAP-selection heuristic (front-layer + weighted lookahead window over upcoming two-qubit gates). Meaningfully reduces SWAP count and depth versus `BaselineSwapRouter` on every benchmarked case, and is competitive with (sometimes beats) Sabre's own SWAP count on structured circuits — see `docs/algorithm_notes.md` for the full comparison table.
- `qiskit_qubit_mapping.plugins`: all four passes registered as Qiskit transpiler stage plugins (`qiskit.transpiler.layout` / `qiskit.transpiler.routing` entry points), usable directly via `transpile(circuit, coupling_map=..., layout_method="qqm_isomorphism", routing_method="qqm_lookahead")` without importing this package. Plugin names are `qqm_`-prefixed to avoid colliding with Qiskit's own reserved built-in plugin names (notably `"lookahead"`, which Qiskit already reserves for its own routing method).
- `qiskit_qubit_mapping.metrics`: `evaluate_layout()` and `compare_to_sabre()` for benchmarking against Qiskit's built-in `SabreLayout`/`SabreSwap`, with an optional `router_pass` argument to select between the two routers.
- `qiskit_qubit_mapping.benchmarks.circuits`: small dependency-free circuit generators (line, ring, all-to-all, random-sparse).
- Full test suite (35 tests) covering graph utilities, both layout heuristics, both routers' correctness/semantics (including statevector-fidelity checks on Bell pairs, GHZ states, and denser random circuits), the evaluation harness, and end-to-end `transpile()` integration for all four transpiler stage plugins (43 tests total including plugin coverage).
- Documentation: `README.md`, `docs/usage.md`, `docs/algorithm_notes.md` with real benchmark numbers against Sabre on a 19-qubit heavy-hex topology.
