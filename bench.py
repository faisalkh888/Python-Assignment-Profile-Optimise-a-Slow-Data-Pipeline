from __future__ import annotations

import argparse
import csv
import statistics
import subprocess
import sys
import time
import tracemalloc
import shutil
import site
from pathlib import Path
from typing import Callable

from generate_data import generate
from pipeline.core import run as fast_run
from pipeline_slow import run as slow_run


def measure(fn: Callable[[], None], repeats: int) -> tuple[float, int]:
    times: list[float] = []
    peaks: list[int] = []
    for _ in range(repeats):
        tracemalloc.start()
        started = time.perf_counter()
        fn()
        times.append(time.perf_counter() - started)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        peaks.append(peak)
    return statistics.median(times), int(statistics.median(peaks))


def profile(fn: Callable[[], None], destination: Path) -> None:
    import cProfile
    profiler = cProfile.Profile()
    profiler.runcall(fn)
    profiler.dump_stats(str(destination))
    with destination.with_suffix(".txt").open("w", encoding="utf-8") as handle:
        import pstats
        pstats.Stats(profiler, stream=handle).sort_stats("cumulative").print_stats(40)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark-artifacts"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    source, catalogue = args.output_dir / "events.csv", args.output_dir / "catalogue.json"
    generate(args.rows, source, catalogue)
    base_out, fast_out = args.output_dir / "baseline.csv", args.output_dir / "fast.csv"
    cases = (("baseline", lambda: slow_run(source, catalogue, base_out)),
             ("optimized", lambda: fast_run(source, catalogue, fast_out)))
    for name, fn in cases:
        if args.profile:
            profile(fn, args.output_dir / f"{name}.prof")
        seconds, peak = measure(fn, args.repeats)
        print(f"{name}: median_seconds={seconds:.6f} peak_tracemalloc_bytes={peak}")
    def rows(path: Path) -> list[tuple[str, ...]]:
        with path.open(newline="", encoding="utf-8") as handle:
            return sorted(tuple(row) for row in csv.reader(handle))
    if rows(base_out) != rows(fast_out):
        raise SystemExit("baseline and optimized outputs differ")
    # Optional py-spy flamegraph. It is kept separate from timed runs.
    pyspy = shutil.which("py-spy")
    if not pyspy:
        user_base = Path(site.USER_BASE or ".")
        for candidate in (user_base / "Scripts" / "py-spy.exe",
                          user_base / "Python311" / "Scripts" / "py-spy.exe"):
            if candidate.exists():
                pyspy = str(candidate)
                break
    if pyspy:
        for name, script, outfile in (("baseline", "pipeline_slow.py", base_out),
                                      ("optimized", "-m", fast_out)):
            target = ([sys.executable, script, str(source), str(catalogue), str(outfile)] if name == "baseline"
                      else [sys.executable, script, "pipeline.core", str(source), str(catalogue), str(outfile)])
            subprocess.run([pyspy, "record", "--rate", "500", "-o", str(args.output_dir / f"{name}.svg"),
                            "--", *target], check=False, capture_output=True)
    else:
        print("py-spy unavailable; see REPORT.md for the reproducible command to generate flamegraphs.")


if __name__ == "__main__":
    main()
