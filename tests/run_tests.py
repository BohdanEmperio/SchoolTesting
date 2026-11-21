#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run the same complete, safe-by-default test suite as pytest."""

import os
import subprocess
import sys
from pathlib import Path


def main():
    project_root = Path(__file__).resolve().parent.parent
    environment = os.environ.copy()
    environment.setdefault("PYTHONIOENCODING", "utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=project_root,
        env=environment,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())