"""Run offline checks, optionally rebuilding in a disposable paper copy.

Building in a temporary directory protects the byte-identical published PDFs
and source provenance. All subprocesses are checked; a failed command stops
the validation instead of producing an apparently successful report.
"""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(arguments, cwd=ROOT):
    print("Running: " + " ".join(arguments), flush=True)
    subprocess.run(arguments, cwd=cwd, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--latex", action="store_true", help="Also rebuild both PDFs in a temporary copy")
    args = parser.parse_args()
    python = sys.executable
    run([python, "tools/check_repository.py"])
    run([python, "evidence/reanalyse.py"])
    for directory in ("evidence", "tests"):
        run([python, "-m", "unittest", "discover", "-s", directory, "-p", "test_*.py", "-v"])
    run([python, "paper/submission-compact/verify_relocation.py"])
    if args.latex:
        with tempfile.TemporaryDirectory(prefix="rebalance-build-") as temporary:
            paper = Path(temporary) / "paper"
            shutil.copytree(ROOT / "paper", paper, ignore=shutil.ignore_patterns("tmp", "__pycache__"))
            run([python, "build_submission.py"], paper / "submission-compact")
    print("All requested release checks passed.")


if __name__ == "__main__":
    main()
