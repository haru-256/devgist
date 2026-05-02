#!/usr/bin/env python3
"""Find Terraform roots and publish GitHub Actions matrix outputs.

This script detects two Terraform CI target groups under ``--terraform-dir``:

* ``environment_roots``: directories under ``environments/`` that contain
  ``providers.tf``. These roots run init, validate, optional test, and tflint.
* ``module_test_roots``: module directories under ``modules/`` that contain
  ``*.tftest.hcl`` files. If a test file is in ``tests/``, the parent module
  directory is used as the root. These roots run module tests without validate.

It writes the following key/value pairs to ``$GITHUB_OUTPUT`` when running in
GitHub Actions, and prints the same key/value pairs to stdout for local use:
``environment_roots``, ``environment_roots_count``, ``module_test_roots``, and
``module_test_roots_count``.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def to_json(paths: list[Path]) -> str:
    return json.dumps([path.as_posix() for path in paths])


def find_environment_roots(terraform_dir: Path) -> list[Path]:
    environments_dir = terraform_dir / "environments"
    if not environments_dir.exists():
        return []

    return sorted(
        path.parent
        for path in environments_dir.rglob("providers.tf")
        if ".terraform" not in path.parts
    )


def module_root_for_test(test_file: Path) -> Path:
    test_dir = test_file.parent
    if test_dir.name == "tests":
        return test_dir.parent
    return test_dir


def find_module_test_roots(terraform_dir: Path) -> list[Path]:
    modules_dir = terraform_dir / "modules"
    if not modules_dir.exists():
        return []

    roots = {
        module_root_for_test(path)
        for path in modules_dir.rglob("*.tftest.hcl")
        if ".terraform" not in path.parts
    }
    return sorted(roots)


def write_github_output(values: dict[str, str]) -> None:
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output is None:
        for key, value in values.items():
            print(f"{key}={value}")
        return

    with Path(github_output).open("a", encoding="utf-8") as output:
        for key, value in values.items():
            output.write(f"{key}={value}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--terraform-dir",
        default="infra/terraform",
        type=Path,
        help="Path to the Terraform monorepo directory.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    terraform_dir = args.terraform_dir

    environment_roots = find_environment_roots(terraform_dir)
    module_test_roots = find_module_test_roots(terraform_dir)

    values = {
        "environment_roots": to_json(environment_roots),
        "environment_roots_count": str(len(environment_roots)),
        "module_test_roots": to_json(module_test_roots),
        "module_test_roots_count": str(len(module_test_roots)),
    }
    write_github_output(values)

    print(f"Terraform environment roots: {values['environment_roots']}")
    print(f"Terraform module test roots: {values['module_test_roots']}")

    if not environment_roots and not module_test_roots:
        raise SystemExit("No Terraform environment or module test roots found.")


if __name__ == "__main__":
    main()
