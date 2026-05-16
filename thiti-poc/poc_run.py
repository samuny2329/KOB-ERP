"""POC harness: invoke /src/bin/frepple on a sample XML inside the
thiti-poc container. Measures wall time, peak RSS, exit code.
Verifies expected output XML files exist."""

from __future__ import annotations

import argparse
import os
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path


FREPPLE_BIN = Path("/src/bin/frepple")
DEFAULT_XML = Path("/src/test/constraints_material_1/constraints_material_1.xml")


def run_plan(xml_path: Path, workdir: Path) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    sample = workdir / xml_path.name
    shutil.copy2(xml_path, sample)

    env = os.environ.copy()
    env.setdefault("FREPPLE_HOME", "/src/bin")
    env.setdefault("LD_LIBRARY_PATH", "/src/bin")
    env.setdefault("PYTHONPATH", "/src")

    t0 = time.monotonic()
    proc = subprocess.run(
        [str(FREPPLE_BIN), str(sample)],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.monotonic() - t0

    rusage = resource.getrusage(resource.RUSAGE_CHILDREN)

    outputs = sorted(workdir.glob("output*.xml"))
    return {
        "returncode": proc.returncode,
        "elapsed_sec": round(elapsed, 3),
        "child_rss_kb": rusage.ru_maxrss,
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-20:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-20:]),
        "outputs": [str(p) for p in outputs],
        "output_sizes": {p.name: p.stat().st_size for p in outputs},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml", type=Path, default=DEFAULT_XML)
    parser.add_argument("--workdir", type=Path, default=Path("/tmp/poc_run"))
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()

    print(f"=== POC: {FREPPLE_BIN} on {args.xml} (repeat={args.repeat}) ===")
    runs = []
    for i in range(args.repeat):
        rd = args.workdir / f"run_{i}"
        if rd.exists():
            shutil.rmtree(rd)
        result = run_plan(args.xml, rd)
        runs.append(result)
        status = "OK" if result["returncode"] == 0 and result["outputs"] else "FAIL"
        print(
            f"[{i+1}/{args.repeat}] {status}  "
            f"exit={result['returncode']}  "
            f"elapsed={result['elapsed_sec']}s  "
            f"rss={result['child_rss_kb']/1024:.1f}MB  "
            f"outputs={len(result['outputs'])}"
        )
        if status == "FAIL":
            print("--- stdout tail ---")
            print(result["stdout_tail"])
            print("--- stderr tail ---")
            print(result["stderr_tail"])

    ok = all(r["returncode"] == 0 and r["outputs"] for r in runs)
    print()
    print(f"=== POC verdict: {'PASS' if ok else 'FAIL'} ===")
    if ok and runs:
        first = runs[0]
        print(f"  output files: {first['output_sizes']}")
        print(f"  median elapsed (sec): "
              f"{sorted(r['elapsed_sec'] for r in runs)[len(runs)//2]}")
        print(f"  max rss (MB): {max(r['child_rss_kb'] for r in runs)/1024:.1f}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
