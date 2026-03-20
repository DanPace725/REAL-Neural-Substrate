"""
run_occupancy_tests_parallel.py
-------------------------------
Run the occupancy unittest modules in parallel subprocesses.

This is intentionally coarse-grained: each test module runs in its own Python
process so the REAL harness stays untouched and PyTorch imports stay out of the
occupancy path.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from scripts.occupancy_real_v3 import AUTO_CPU_TARGET_FRACTION, auto_worker_count


DEFAULT_MODULES = (
    "tests.test_occupancy_real",
    "tests.test_occupancy_real_v2",
    "tests.test_occupancy_real_v3",
)


@dataclass(frozen=True)
class ModuleResult:
    module: str
    returncode: int
    elapsed_seconds: float
    stdout: str
    stderr: str


def _run_module(module: str) -> ModuleResult:
    start = time.monotonic()
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", module],
        capture_output=True,
        text=True,
        cwd=str(Path.cwd()),
    )
    elapsed = time.monotonic() - start
    return ModuleResult(
        module=module,
        returncode=int(completed.returncode),
        elapsed_seconds=elapsed,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run occupancy unittest modules in parallel.")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help=(
            f"Parallel module workers. Omit to auto-use about {int(AUTO_CPU_TARGET_FRACTION * 100)}% "
            "of visible CPU capacity, capped by module count."
        ),
    )
    parser.add_argument(
        "--modules",
        nargs="*",
        default=list(DEFAULT_MODULES),
        help="Specific unittest modules to run. Defaults to all occupancy modules.",
    )
    args = parser.parse_args(argv)

    modules = [str(module) for module in args.modules]
    worker_count = auto_worker_count(len(modules)) if args.workers is None else max(1, min(int(args.workers), len(modules)))

    print("Parallel occupancy test runner")
    print(f"  modules: {modules}")
    print(f"  workers: {worker_count}")

    results: list[ModuleResult] = []
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(_run_module, module): module for module in modules}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            status = "OK" if result.returncode == 0 else "FAIL"
            print(f"  {status:<4} {result.module}  {result.elapsed_seconds:.1f}s")

    results.sort(key=lambda item: item.module)
    failed = [result for result in results if result.returncode != 0]

    for result in failed:
        print(f"\n=== {result.module} failed ===")
        if result.stdout.strip():
            print(result.stdout.rstrip())
        if result.stderr.strip():
            print(result.stderr.rstrip())

    total_elapsed = sum(result.elapsed_seconds for result in results)
    longest = max((result.elapsed_seconds for result in results), default=0.0)
    print(f"\nModule CPU-seconds: {total_elapsed:.1f}")
    print(f"Wall-time lower bound from longest module: {longest:.1f}s")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
