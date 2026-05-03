from pathlib import Path

import pytest

from find_terraform_roots import find_environment_roots, find_module_roots


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
        touch(tmp_path / "modules" / "artifact_registry" / "basic.tftest.hcl")
        touch(
            tmp_path / "modules" / "data_platform" / ".terraform" / "ignored.tftest.hcl"
        )

        # Act
        roots = find_module_roots(tmp_path)

        # Assert
        assert roots == [
            tmp_path / "modules" / "service_accounts",
        ]

    def test_returns_empty_when_modules_missing(self, tmp_path: Path) -> None:
        assert find_module_roots(tmp_path) == []
