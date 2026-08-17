# Algorithm notes

## `IsomorphismLayout`

The circuit's two-qubit interaction graph and the device's coupling graph are both plain `networkx.Graph` objects (see `_graph_utils.interaction_graph` / `_graph_utils.coupling_graph`). `IsomorphismLayout` runs `networkx.algorithms.isomorphism.GraphMatcher` to search for a **subgraph isomorphism** of the interaction graph into the coupling graph — a placement where every logical two-qubit interaction lands on a physically adjacent pair, needing zero SWAPs.

VF2 subgraph isomorphism is worst-case exponential, so the search is capped at `time_budget` candidates (default 50,000). If no isomorphism is found within budget, the pass falls back to a degree-greedy placement: logical qubits are placed in descending interaction-degree order, each one preferring a free physical qubit adjacent to an already-placed neighbor (breaking ties by hardware distance), falling back to the highest-degree free physical qubit otherwise.

Isolated logical qubits (no two-qubit gates) are excluded from the isomorphism search itself — they can go anywhere — and are assigned to leftover physical qubits afterward.

## `WalkBasedLayout`

This extends the continuous-time quantum walk (CTQW) machinery from [`qiskit-graph-walks`](https://github.com/RexRowan/qiskit-graph-walks) to the placement problem. For a graph with adjacency matrix `A`, the CTQW propagator is `U(t) = exp(-i·A·t)`. Two scalar descriptors are computed per node from `U(t)`:

- **Return probability** `|U(t)[v,v]|²` — how much probability stays localized at `v` after time `t`. Low return probability means `v` sits in a well-connected neighborhood that mixes probability away quickly.
- **Mixing entropy** — the Shannon entropy of the row `|U(t)[v,:]|²`, i.e. how spread out the walker starting at `v` becomes.

These are computed at three time points (`t = 0.5, 1.0, 2.0` by default) to capture short-, medium-, and longer-range mixing behavior, concatenated into a 6-dimensional feature vector per node, and z-scored within each graph. Because the descriptor is a small vector of scalars rather than a full N-length distribution, it can be compared directly between graphs of *different sizes* — the logical interaction graph is almost always smaller than the physical coupling graph.

Logical-to-physical assignment is then solved as a linear assignment problem (Hungarian algorithm, via `scipy.optimize.linear_sum_assignment`) minimizing total Euclidean distance between logical and physical feature vectors: highly-connected logical qubits get matched to highly-connected physical qubits, and so on down the connectivity spectrum.

This produces a *smooth* similarity-based assignment rather than an all-or-nothing structural match, so unlike `IsomorphismLayout`'s greedy fallback it never has to "give up" — but as the benchmarks below show, that smoothness comes at a real cost in solution quality on this baseline router.

## `BaselineSwapRouter`

Deliberately simple: process gates in topological order, and whenever a two-qubit gate's operands aren't hardware-adjacent, walk one operand toward the other one SWAP-hop at a time along the shortest hardware path (`networkx.shortest_path`), then apply the gate. No lookahead, no SWAP-choice search, no attempt to route multiple pending gates jointly. This is intentional: it's a correctness-first reference implementation, verified directly against ideal statevectors in `tests/test_routing.py` (Bell pair and GHZ state marginal-probability checks), so that the *layout* heuristics above can be benchmarked without also debugging a sophisticated router.

## `LookaheadSwapRouter`

A Sabre-style routing pass built directly on top of the baseline's verification approach. At each step:

1. Execute every gate in the DAG's current *front layer* (`DAGCircuit.front_layer()`) that's either single-qubit or already hardware-adjacent.
2. When a pending two-qubit gate isn't adjacent, gather every hardware edge touching a qubit involved in a pending front-layer gate as a candidate SWAP.
3. Score each candidate by the total hardware-distance cost it would leave behind, summed over the pending front-layer gates *plus* a weighted lookahead window of upcoming two-qubit gates (`score = front_cost + lookahead_weight * lookahead_cost`), and apply the lowest-scoring one.

The lookahead window is derived from a single global topological ordering of the circuit's two-qubit gates computed once up front, rather than the DAG's precise "extended set" recomputed at each step — a deliberate simplification that holds up well for circuits with the usual interleaving of single- and two-qubit gates, but is only an approximation for circuits with unusual dependency structure. `lookahead_size` (default 20) controls how many upcoming gates are considered; `lookahead_weight` (default 0.5) controls how strongly they're weighted relative to the immediate front layer.

Like the baseline, correctness is checked directly against ideal statevectors (`tests/test_lookahead_routing.py`), including on a denser random circuit exercising multiple sequential SWAP decisions in one run, and there's a direct regression test (`test_uses_fewer_or_equal_swaps_than_baseline_on_dense_circuit`) asserting it never does worse than the non-lookahead baseline.

## Benchmark: toolkit vs. Sabre

Measured with `qiskit_qubit_mapping.metrics.compare_to_sabre` on a 19-qubit heavy-hex(3) coupling map (`CouplingMap.from_heavy_hex(3)`), across circuits from `qiskit_qubit_mapping.benchmarks.circuits`, using `IsomorphismLayout` paired with each router:

| Circuit | Layout + Router | SWAPs | Depth |
|---|---|--:|--:|
| Line | Isomorphism + Baseline | 10 | 46 |
| Line | Isomorphism + Lookahead | **8** | **42** |
| Line | Sabre | 12 | 45 |
| Ring | Isomorphism + Baseline | 13 | 51 |
| Ring | Isomorphism + Lookahead | **10** | **45** |
| Ring | Sabre | 15 | 50 |
| Random sparse (n edges) | Isomorphism + Baseline | 29 | 33 |
| Random sparse (n edges) | Isomorphism + Lookahead | 14 | 18 |
| Random sparse (n edges) | Sabre | **11** | 18 |
| Random sparse (2n edges) | Isomorphism + Baseline | 75 | 83 |
| Random sparse (2n edges) | Isomorphism + Lookahead | 48 | 43 |
| Random sparse (2n edges) | Sabre | **45** | **33** |

**Takeaways, stated plainly:**

- `LookaheadSwapRouter` is a clear, consistent improvement over `BaselineSwapRouter` — fewer SWAPs and lower depth on every single case measured, sometimes by more than half (75 → 48 SWAPs on the densest case).
- On structured circuits (line, ring) the toolkit's Isomorphism+Lookahead combination actually **beats** Sabre's SWAP count outright, because `IsomorphismLayout` starts from a layout Sabre has to converge toward iteratively.
- On denser, less structured random circuits, Sabre still wins, but the gap that used to be large (29 vs. 11, 75 vs. 45 with the baseline router) is now much smaller (14 vs. 11, 48 vs. 45 with the lookahead router) — the remaining difference is mostly attributable to Sabre's bidirectional/iterative layout refinement, which this toolkit doesn't do (see Roadmap in the README).
- `WalkBasedLayout` was not re-benchmarked with the lookahead router here; it underperformed `IsomorphismLayout` with the baseline router (see the prior version of this table in git history) and remains a starting point for further tuning rather than a recommended default.

Reproduce this table with the snippet in `docs/usage.md`.
