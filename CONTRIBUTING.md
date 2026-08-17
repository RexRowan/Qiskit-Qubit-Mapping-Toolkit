# Contributing

Thanks for your interest in `qiskit-qubit-mapping-toolkit`.

## Development setup

```bash
git clone https://github.com/RexRowan/qiskit-qubit-mapping-toolkit
cd qiskit-qubit-mapping-toolkit
pip install -e ".[dev]"
pytest tests/ -v
```

## Guidelines

- **Version bound:** all Qiskit dependencies should stay at `qiskit>=2.0,<3`, consistent with the rest of this Ecosystem portfolio.
- **Tests:** any new layout heuristic or routing pass should ship with correctness tests. For routing changes in particular, add a semantics-preservation test (see `tests/test_routing.py` for the pattern: build a small entangled state, route it, and compare marginal measurement probabilities against the unrouted ideal circuit) — a routing pass that "runs" but silently changes circuit semantics is a much worse bug than a crash.
- **Style:** run `ruff check .` and `black .` before submitting (both are in the `dev` extra).
- **Docs:** update `docs/usage.md` for new public API, and `docs/algorithm_notes.md` if you change the reasoning behind an existing heuristic's scoring function.

## Reporting issues

Open a GitHub issue with a minimal reproducing circuit and coupling map where possible — this is especially useful for `IsomorphismLayout`, where behavior depends on the exact interaction-graph structure.

## Code of conduct

This project follows the [Qiskit Code of Conduct](https://github.com/Qiskit/qiskit/blob/main/CODE_OF_CONDUCT.md).
