from pathlib import Path

import pytest

from find_terraform_roots import (
    filter_deploy_roots,
    find_environment_roots,
    find_module_roots,
)


def touch(path: Path) -> None:
    """Create parent directories and write an empty file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")


class TestFindEnvironmentRoots:
    def test_finds_environment_providers(self, tmp_path: Path) -> None:
        # Arrange
        touch(tmp_path / "environments" / "devgist-app" / "dev" / "providers.tf")
        touch(tmp_path / "environments" / "devgist-data" / "dev" / "providers.tf")
        touch(
            tmp_path
            / "environments"
            / "devgist-app"
            / "dev"
            / ".terraform"
            / "providers.tf"
        )

        # Act
        roots = find_environment_roots(tmp_path)

        # Assert
        assert roots == [
            tmp_path / "environments" / "devgist-app" / "dev",
            tmp_path / "environments" / "devgist-data" / "dev",
        ]

    def test_returns_empty_when_environments_missing(self, tmp_path: Path) -> None:
        assert find_environment_roots(tmp_path) == []


class TestFindModuleRoots:
    def test_finds_module(self, tmp_path: Path) -> None:
        # Arrange
        touch(tmp_path / "modules" / "service_accounts" / "providers.tf")
        touch(tmp_path / "modules" / "artifact_registry" / "basic.tftest.hcl")  # providers.tf なし → 対象外
        touch(tmp_path / "modules" / "data_platform" / ".terraform" / "providers.tf")  # .terraform 内 → 対象外

        # Act
        roots = find_module_roots(tmp_path)

        # Assert
        assert roots == [
            tmp_path / "modules" / "service_accounts",
        ]

    def test_returns_sorted_multiple_modules(self, tmp_path: Path) -> None:
        # Arrange
        touch(tmp_path / "modules" / "z_module" / "providers.tf")
        touch(tmp_path / "modules" / "a_module" / "providers.tf")

        # Act
        roots = find_module_roots(tmp_path)

        # Assert
        assert roots == [
            tmp_path / "modules" / "a_module",
            tmp_path / "modules" / "z_module",
        ]

    def test_returns_empty_when_modules_missing(self, tmp_path: Path) -> None:
        assert find_module_roots(tmp_path) == []


class TestFilterDeployRoots:
    def test_excludes_roots_by_relative_path(self, tmp_path: Path) -> None:
        # Arrange
        touch(tmp_path / "environments" / "devgist-app" / "dev" / "providers.tf")
        touch(tmp_path / "environments" / "devgist-data" / "dev" / "providers.tf")
        touch(tmp_path / "environments" / "devgist-ops" / "providers.tf")
        touch(tmp_path / "environments" / "devgist-tf" / "providers.tf")
        touch(tmp_path / "environments" / "github" / "providers.tf")
        roots = find_environment_roots(tmp_path)

        # Act
        deploy_roots = filter_deploy_roots(roots, tmp_path, ["devgist-tf", "github"])

        # Assert
        assert deploy_roots == [
            tmp_path / "environments" / "devgist-app" / "dev",
            tmp_path / "environments" / "devgist-data" / "dev",
            tmp_path / "environments" / "devgist-ops",
        ]

    def test_no_excludes_returns_all_environment_roots(self, tmp_path: Path) -> None:
        # Arrange
        touch(tmp_path / "environments" / "devgist-ops" / "providers.tf")
        roots = find_environment_roots(tmp_path)

        # Act / Assert
        assert filter_deploy_roots(roots, tmp_path, []) == roots

    def test_unknown_exclude_is_ignored(self, tmp_path: Path) -> None:
        # Arrange
        touch(tmp_path / "environments" / "devgist-ops" / "providers.tf")
        roots = find_environment_roots(tmp_path)

        # Act / Assert
        assert filter_deploy_roots(roots, tmp_path, ["no-such-root"]) == roots
