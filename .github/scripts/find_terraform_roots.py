#!/usr/bin/env python3
"""Find Terraform roots and publish GitHub Actions matrix outputs.

This script detects two Terraform CI target groups under ``--terraform-dir``:

* ``environment_roots``: directories under ``environments/`` that contain
  ``providers.tf``. These roots run init, validate, optional test, and tflint.
* ``module_roots``: module directories under ``modules/`` that contain
  ``providers.tf``. These roots run init and tflint without validate, and
  also run ``terraform test`` when ``*.tftest.hcl`` files are present.

It writes the following key/value pairs to ``$GITHUB_OUTPUT`` when running in
GitHub Actions, and prints the same key/value pairs to stdout for local use:
``environment_roots``, ``environment_roots_count``, ``module_roots``, and
``module_roots_count``.

When ``--deploy-exclude`` is given, environment roots whose path relative to
``environments/`` matches one of the excludes (e.g. ``devgist-tf`` or
``devgist-github``) are additionally published as ``deploy_roots`` /
``deploy_roots_count``. Deploy roots are the subset of environment roots that
CI is allowed to plan / apply (INFRA-ADR-019). Without excludes, deploy roots
equal environment roots.
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


def find_module_roots(terraform_dir: Path) -> list[Path]:
    modules_dir = terraform_dir / "modules"
    if not modules_dir.exists():
        return []

    roots = {
        path.parent
        for path in modules_dir.rglob("providers.tf")
        if ".terraform" not in path.parts
    }
    return sorted(roots)


def filter_deploy_roots(
    environment_roots: list[Path],
    terraform_dir: Path,
    excludes: list[str],
) -> list[Path]:
    """Return environment roots minus the given deploy excludes.

    ``excludes`` are matched against the root path relative to
    ``environments/`` (e.g. ``devgist-tf`` or ``devgist-app/dev``).
    """
    environments_dir = terraform_dir / "environments"
    return [
        root
        for root in environment_roots
        if root.relative_to(environments_dir).as_posix() not in excludes
    ]


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
    parser.add_argument(
        "--deploy-exclude",
        nargs="*",
        default=[],
        metavar="ROOT",
        help=(
            "Environment roots (relative to environments/, e.g. 'devgist-tf') "
            "to exclude from deploy_roots."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    terraform_dir = args.terraform_dir

    environment_roots = find_environment_roots(terraform_dir)
    module_roots = find_module_roots(terraform_dir)
    deploy_roots = filter_deploy_roots(environment_roots, terraform_dir, args.deploy_exclude)

    values = {
        "environment_roots": to_json(environment_roots),
        "environment_roots_count": str(len(environment_roots)),
        "module_roots": to_json(module_roots),
        "module_roots_count": str(len(module_roots)),
        "deploy_roots": to_json(deploy_roots),
        "deploy_roots_count": str(len(deploy_roots)),
    }
    write_github_output(values)

    print(f"Terraform environment roots: {values['environment_roots']}")
    print(f"Terraform module roots: {values['module_roots']}")
    print(f"Terraform deploy roots: {values['deploy_roots']}")

    if not environment_roots and not module_roots:
        raise SystemExit("No Terraform environment or module roots found.")


if __name__ == "__main__":
    main()
