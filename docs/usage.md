# Usage guide

## 1. Building a coupling map

Use any `qiskit.transpiler.CouplingMap`, whether hand-built, from a backend, or from one of Qiskit's topology constructors:

```python
from qiskit.transpiler import CouplingMap

line = CouplingMap([[0, 1], [1, 2], [2, 3]])
heavy_hex = CouplingMap.from_heavy_hex(3)

# From a real backend (if you have provider access):
# coupling_map = backend.coupling_map
```

## 2. Choosing a layout heuristic

### `IsomorphismLayout` — when your circuit might embed exactly

Good for circuits with sparse, structured interaction graphs: linear entanglers, ring/cyclic entanglers, tree-shaped ansätze, or any circuit whose two-qubit gate pattern resembles the target hardware's connectivity.

```python
from qiskit_qubit_mapping.layout import IsomorphismLayout
from qiskit.converters import circuit_to_dag

layout_pass = IsomorphismLayout(coupling_map, time_budget=50_000)
result = layout_pass.compute_layout(circuit_to_dag(my_circuit))

print(result.mapping)                          # {logical_qubit: physical_qubit, ...}
print(result.metadata["exact_isomorphism"])     # True if a zero-SWAP embedding was found
print(result.score)                             # 0 if exact; expected extra SWAPs otherwise
```

Raise `time_budget` for a more thorough search on circuits you suspect are embeddable but where the default budget gives up too early; lower it if you know most circuits you're feeding it won't embed, to fail fast into the greedy fallback.

### `WalkBasedLayout` — a smooth fallback for less structured circuits

```python
from qiskit_qubit_mapping.layout import WalkBasedLayout

layout_pass = WalkBasedLayout(coupling_map, times=(0.5, 1.0, 2.0))
result = layout_pass.compute_layout(circuit_to_dag(my_circuit))
```

`times` controls the CTQW evolution times sampled to build each qubit's mixing signature. Denser circuits/graphs may saturate entropy quickly at the default times; try smaller values (e.g. `(0.1, 0.3, 0.6)`) if scores look uninformative (e.g. many nodes with near-identical signatures).

As shown in [`docs/algorithm_notes.md`](algorithm_notes.md), `IsomorphismLayout` currently outperforms `WalkBasedLayout` in most measured cases — reach for the walk-based heuristic when you specifically want to experiment with or extend the CTQW scoring approach, not as a default first choice.

## 3. Routing

Two routers are available: `BaselineSwapRouter` (simple, correctness-first, shortest-path SWAP insertion) and `LookaheadSwapRouter` (Sabre-style front-layer + lookahead-window SWAP scoring, meaningfully fewer SWAPs — see [`docs/algorithm_notes.md`](algorithm_notes.md) for measured numbers). Prefer `LookaheadSwapRouter` by default; reach for `BaselineSwapRouter` when you want the simplest possible reference behavior, e.g. to sanity-check a new layout heuristic without the router's own choices affecting the comparison.

Either use the functional API directly:

```python
from qiskit_qubit_mapping.routing.baseline import route_circuit
from qiskit_qubit_mapping.routing.lookahead import route_circuit_lookahead

routed_circuit, final_mapping = route_circuit(
    my_circuit,
    coupling_map,
    initial_layout=result.mapping,   # from a layout heuristic above, or your own dict
)

# or, with lookahead:
routed_circuit, final_mapping = route_circuit_lookahead(
    my_circuit,
    coupling_map,
    initial_layout=result.mapping,
    lookahead_size=20,      # how many upcoming two-qubit gates to consider
    lookahead_weight=0.5,   # relative weight of the lookahead window vs. the front layer
)
```

or compose the layout pass and router in a `PassManager` (recommended — this is what `evaluate_layout` / `compare_to_sabre` do internally):

```python
from qiskit.transpiler import PassManager
from qiskit_qubit_mapping import IsomorphismLayout, LookaheadSwapRouter

pm = PassManager([IsomorphismLayout(coupling_map), LookaheadSwapRouter(coupling_map)])
routed_circuit = pm.run(my_circuit)

final_layout = pm.property_set["final_layout"]        # qiskit.transpiler.Layout
mapping_result = pm.property_set["qubit_mapping_result"]  # this package's LayoutResult
```

`final_mapping` (or `property_set["final_layout"]`) is needed if you want to interpret measurement results or chain further transpiler passes — SWAPs move logical qubits around physical qubits over the course of the circuit, so the mapping at the end generally differs from the initial layout.

## 4. Evaluating and comparing

```python
from qiskit_qubit_mapping.metrics import evaluate_layout, compare_to_sabre
from qiskit_qubit_mapping.routing import LookaheadSwapRouter

# Just this toolkit's pipeline (defaults to BaselineSwapRouter):
result = evaluate_layout(my_circuit, coupling_map, IsomorphismLayout(coupling_map))
print(result.swap_count, result.depth, result.layout_score)

# With the lookahead router instead:
result = evaluate_layout(
    my_circuit, coupling_map, IsomorphismLayout(coupling_map),
    router_pass=LookaheadSwapRouter(coupling_map),
)

# Side-by-side against Qiskit's SabreLayout + SabreSwap:
results = compare_to_sabre(
    my_circuit, coupling_map, IsomorphismLayout(coupling_map),
    router_pass=LookaheadSwapRouter(coupling_map), seed=0,
)
print(results["toolkit"])
print(results["sabre"])
```

## 5. Benchmark circuits

`qiskit_qubit_mapping.benchmarks.circuits` provides small, dependency-free generators for exercising the toolkit without pulling in an external benchmark suite:

```python
from qiskit_qubit_mapping.benchmarks.circuits import (
    linear_entangling_circuit,   # path interaction graph -- good IsomorphismLayout case
    ring_entangling_circuit,     # cycle interaction graph
    all_to_all_circuit,          # complete interaction graph -- worst case, exercises fallbacks
    random_sparse_circuit,       # n_qubits, n_two_qubit_gates, seed
)
```

For larger-scale or standardized comparisons, point `compare_to_sabre` at circuits loaded from an external suite such as QASMBench or MQT Bench instead — anything that produces a `qiskit.circuit.QuantumCircuit` works.

## 7. Using the toolkit through `transpile()` (no imports needed)

All four passes are registered as Qiskit transpiler stage plugins via setuptools entry points, so once the package is installed they're usable straight from `transpile()`:

```python
from qiskit import transpile
from qiskit.transpiler import CouplingMap

cmap = CouplingMap([[0, 1], [1, 2], [2, 3]])
transpiled = transpile(
    my_circuit,
    coupling_map=cmap,
    layout_method="qqm_isomorphism",
    routing_method="qqm_lookahead",
    optimization_level=1,
)
```

Mix and match: `layout_method` accepts `"qqm_isomorphism"` or `"qqm_walk_based"`; `routing_method` accepts `"qqm_baseline"` or `"qqm_lookahead"`. Omit either argument to fall back to Qiskit's own default for that stage while still using the toolkit for the other.

A coupling map is required — the plugins raise a clear `TranspilerError` if `transpile()` is called without one (no coupling map means there's nothing to lay out or route onto).

To recover the final logical-to-physical mapping (needed to interpret measurement results, since routing SWAPs move qubits around), use the `TranspileLayout` object Qiskit attaches to the result:

```python
result = transpile(my_circuit, coupling_map=cmap, layout_method="qqm_isomorphism", routing_method="qqm_lookahead")
final_physical_qubits = result.layout.final_index_layout()  # physical qubit holding logical qubit i, indexed by i
```

Check what's registered at any time:

```python
from qiskit.transpiler.preset_passmanagers.plugin import list_stage_plugins

print(list_stage_plugins("layout"))
print(list_stage_plugins("routing"))
```

See `qiskit_qubit_mapping/plugins.py` for the plugin implementations themselves — each is a thin wrapper: layout plugins run the heuristic pass and then Qiskit's standard `generate_embed_passmanager` to expand the circuit to full physical width; routing plugins just run the router directly, since the circuit is already at full width by that stage.

## 8. Reproducing the benchmark table in `docs/algorithm_notes.md`

```python
from qiskit.transpiler import CouplingMap
from qiskit_qubit_mapping.benchmarks.circuits import (
    linear_entangling_circuit, ring_entangling_circuit, random_sparse_circuit,
)
from qiskit_qubit_mapping.layout import IsomorphismLayout
from qiskit_qubit_mapping.routing import BaselineSwapRouter, LookaheadSwapRouter
from qiskit_qubit_mapping.metrics import compare_to_sabre

cmap = CouplingMap.from_heavy_hex(3)
n = cmap.size()

for name, qc in [
    ("line", linear_entangling_circuit(n)),
    ("ring", ring_entangling_circuit(n)),
    ("random sparse (n edges)", random_sparse_circuit(n, n, seed=7)),
    ("random sparse (2n edges)", random_sparse_circuit(n, 2 * n, seed=7)),
]:
    for router_label, router_cls in [("Baseline", BaselineSwapRouter), ("Lookahead", LookaheadSwapRouter)]:
        res = compare_to_sabre(qc, cmap, IsomorphismLayout(cmap), router_pass=router_cls(cmap))
        print(name, router_label, res["toolkit"].swap_count, res["toolkit"].depth)
    res = compare_to_sabre(qc, cmap, IsomorphismLayout(cmap))
    print(name, "Sabre", res["sabre"].swap_count, res["sabre"].depth)
```
