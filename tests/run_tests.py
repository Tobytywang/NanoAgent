#!/usr/bin/env python
"""
Test runner script for NanoAgent.
"""

import subprocess
import sys


def run_tests(args: list[str] = None):
    """Run pytest with the given arguments."""
    if args is None:
        args = []

    # Default arguments with coverage threshold
    pytest_args = [
        "pytest",
        "tests/",
        "-v",
        "--tb=short",
        "--cov=nano_agent",
        "--cov-fail-under=54",
        *args
    ]

    result = subprocess.run(pytest_args)
    return result.returncode


def run_coverage():
    """Run tests with coverage report."""
    try:
        import pytest_cov  # noqa: F401
    except ImportError:
        print("Installing pytest-cov...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pytest-cov", "-q"])

    result = subprocess.run([
        "pytest",
        "tests/",
        "-v",
        "--cov=nano_agent",
        "--cov-report=term-missing",
        "--cov-report=html",
    ])
    return result.returncode


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run NanoAgent tests")
    parser.add_argument(
        "--coverage", "-c",
        action="store_true",
        help="Run with coverage report"
    )
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="Additional pytest arguments"
    )

    args = parser.parse_args()

    if args.coverage:
        sys.exit(run_coverage())
    else:
        sys.exit(run_tests(args.pytest_args))
