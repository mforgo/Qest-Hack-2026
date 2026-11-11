#!/usr/bin/env python3
"""Cross-platform environment bootstrapper for Windows, Linux and macOS.

Creates two isolated environments because the current IBM and IQM stacks pin
incompatible versions of qiskit and pydantic:

    qest-ibm : Qiskit + IBM Quantum Runtime + optimization mapper
    qest-iqm : IQM client + Qiskit adapter + IQM QAOA

Backends:
    --conda  use conda (creates named envs "qest-ibm" / "qest-iqm")
    --venv   use Python's stdlib venv (creates ".venv-ibm" / ".venv-iqm")
    default  conda if available, otherwise venv

Examples:
    python setup_env.py              # auto-detect
    python setup_env.py --venv       # portable, no conda needed
    python setup_env.py --conda      # use conda

Requires only the Python standard library.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON_VERSION = os.environ.get("PYTHON_VERSION", "3.13")
ENVIRONMENTS = {
    "qest-ibm": "requirements-ibm.txt",
    "qest-iqm": "requirements-iqm.txt",
}


def run(command: list[str]) -> None:
    print("+ " + " ".join(str(part) for part in command), flush=True)
    subprocess.run(command, check=True)


def find_conda() -> str | None:
    conda_exe = os.environ.get("CONDA_EXE")
    if conda_exe and Path(conda_exe).exists():
        return conda_exe
    return shutil.which("conda")


def conda_env_exists(conda: str, name: str) -> bool:
    result = subprocess.run(
        [conda, "env", "list"], capture_output=True, text=True, check=True
    )
    names = {
        line.split()[0]
        for line in result.stdout.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    return name in names


def setup_with_conda() -> None:
    conda = find_conda()
    if not conda:
        raise SystemExit("conda not found on PATH (and CONDA_EXE is unset).")

    for name, requirements in ENVIRONMENTS.items():
        if conda_env_exists(conda, name):
            print(f"==> conda env '{name}' already exists; updating packages")
        else:
            print(f"==> creating conda env '{name}' (python {PYTHON_VERSION})")
            run(
                [
                    conda,
                    "create",
                    "-y",
                    "-n",
                    name,
                    "-c",
                    "conda-forge",
                    f"python={PYTHON_VERSION}",
                    "pip",
                ]
            )
        run([conda, "run", "-n", name, "python", "-m", "pip", "install", "--upgrade", "pip"])
        run(
            [
                conda,
                "run",
                "-n",
                name,
                "python",
                "-m",
                "pip",
                "install",
                "-r",
                str(ROOT / requirements),
            ]
        )

    print("\nDone. Activate with:")
    print("  conda activate qest-ibm   # IBM Quantum")
    print("  conda activate qest-iqm   # IQM Resonance")


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def setup_with_venv() -> None:
    for name, requirements in ENVIRONMENTS.items():
        suffix = name.split("-", 1)[1]
        venv_dir = ROOT / f".venv-{suffix}"
        python = venv_python(venv_dir)
        if not python.exists():
            print(f"==> creating venv '{venv_dir.name}'")
            run([sys.executable, "-m", "venv", str(venv_dir)])
        run([str(python), "-m", "pip", "install", "--upgrade", "pip"])
        run([str(python), "-m", "pip", "install", "-r", str(ROOT / requirements)])

    print("\nDone. Activate with:")
    if os.name == "nt":
        print(r"  .venv-ibm\Scripts\activate      # IBM Quantum")
        print(r"  .venv-iqm\Scripts\activate      # IQM Resonance")
    else:
        print("  source .venv-ibm/bin/activate   # IBM Quantum")
        print("  source .venv-iqm/bin/activate   # IQM Resonance")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    backend = parser.add_mutually_exclusive_group()
    backend.add_argument("--conda", action="store_true", help="use conda named environments")
    backend.add_argument("--venv", action="store_true", help="use stdlib venv environments")
    args = parser.parse_args()

    if args.conda:
        setup_with_conda()
    elif args.venv:
        setup_with_venv()
    elif find_conda():
        setup_with_conda()
    else:
        setup_with_venv()


if __name__ == "__main__":
    main()
