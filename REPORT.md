# Data pipeline profiling report

## Method

The fixed-seed generator defaults to 1,000,000 rows (`20261114` seed). Measurements below use 2,000 rows because the reference deliberately rescans the cleaned list once per distinct output key; at one million rows, that baseline grows quadratically and is not a useful or safe timed run. The 10,000-row correctness fixture is run separately. Timings are medians of three executions on the same Windows/Python 3.11.9 environment. Peak memory is `tracemalloc` peak Python allocation, not process RSS; NumPy's native allocator may not be fully represented. The benchmark excludes generation and profiles in its timed runs. Output was compared as sorted CSV rows, independent of line endings.

## Results

| Stage | Changes | Median time (s) | Peak traced memory (bytes) | Speed-up vs baseline |
|---|---|---:|---:|---:|
| Baseline | Materialized dict rows, linear catalogue scan, repeated aggregate rescans | 0.3062 | 2,461,202 | 1.00× |
| Algorithm/data structure | Catalogue dictionary and one-pass keyed aggregation | Included in final | Included in final | — |
| Streaming and I/O | `csv.reader`, bounded aggregation batches, no event-row retention | Included in final | Included in final | — |
| Vectorized aggregation | NumPy `unique`/`bincount` per batch | **0.0252** | **573,511** | **12.1×** |

The staged intermediate variants were not separately retained as executable releases, so only baseline and final values are presented as measurements. The final run was about 12.1× faster and used 4.29× less traced memory on this fixture. The 2,000-row input is a microbenchmark and does not establish linear-scale wall time; the baseline's repeated scans make scaling especially unfavorable. For larger realistic runs, use `python generate_data.py --rows 1000000` and benchmark the optimized entry point; avoid invoking the intentionally quadratic baseline at that size.

## Profile evidence

The benchmark produced cProfile binary and readable summaries plus py-spy SVG flame graphs from the same 2,000-row deterministic input:

- Baseline cProfile: [`benchmark-artifacts/baseline.txt`](benchmark-artifacts/baseline.txt), [`benchmark-artifacts/baseline.prof`](benchmark-artifacts/baseline.prof)
- Optimized cProfile: [`benchmark-artifacts/optimized.txt`](benchmark-artifacts/optimized.txt), [`benchmark-artifacts/optimized.prof`](benchmark-artifacts/optimized.prof)
- Before flame graph: [`benchmark-artifacts/baseline.svg`](benchmark-artifacts/baseline.svg)
- After flame graph: [`benchmark-artifacts/optimized.svg`](benchmark-artifacts/optimized.svg)

The baseline profile shows work concentrated in repeated row comparisons and catalogue scans. The optimized profile shifts work to CSV parsing, cached date conversion, NumPy grouping, and output formatting; it no longer retains or repeatedly scans event dictionaries.

Reproduce profiles and the timing table with:

```powershell
python -m pip install -e ".[test]"
python bench.py --rows 2000 --repeats 3 --profile --output-dir benchmark-artifacts
```

## Correctness and typing

`pytest` checks row equality on 10,000 generated records, a Hypothesis cleaning property, empty input, malformed records, and invalid negative prices. `mypy --strict` is configured for the pipeline and supporting scripts. The CSV output is sorted by day, SKU, and category; non-purchase events create a zero-revenue output group to match the reference behavior.

Run from a clean checkout:

```powershell
python -m pip install -e ".[test]"
python -m pytest
python -m mypy --strict
pipeline events.csv catalogue.json report.csv
```

The generator writes local CSV/JSON files when run. Generated input data is intentionally excluded from the repository.
