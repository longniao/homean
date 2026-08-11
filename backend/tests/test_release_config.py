from pathlib import Path

import pytest
import yaml

from scripts.validate_render_blueprint import (
    BlueprintValidationError,
    validate_blueprint,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BLUEPRINT_PATH = REPOSITORY_ROOT / "infra" / "render.yaml"


def test_render_blueprint_uses_existing_release_docker_paths() -> None:
    assert validate_blueprint(BLUEPRINT_PATH, REPOSITORY_ROOT) == (
        "kawu-api",
        "kawu-worker",
        "kawu-dashboard",
    )


def test_compose_uses_the_same_canonical_backend_builds() -> None:
    compose = yaml.safe_load(
        (REPOSITORY_ROOT / "infra" / "docker-compose.yml").read_text(encoding="utf-8")
    )

    assert compose["services"]["api"]["build"] == {
        "context": "../backend",
        "dockerfile": "Dockerfile.api",
    }
    assert compose["services"]["worker"]["build"] == {
        "context": "../backend",
        "dockerfile": "Dockerfile.worker",
    }


def test_redundant_infra_dockerfiles_are_not_present() -> None:
    assert not (REPOSITORY_ROOT / "infra" / "Dockerfile.api").exists()
    assert not (REPOSITORY_ROOT / "infra" / "Dockerfile.worker").exists()


def test_render_blueprint_rejects_a_missing_dockerfile(tmp_path: Path) -> None:
    blueprint = tmp_path / "render.yaml"
    blueprint.write_text(
        """
services:
  - name: kawu-api
    type: web
    runtime: docker
    dockerfilePath: ./missing/Dockerfile
    dockerContext: ./missing
  - name: kawu-worker
    type: worker
    runtime: docker
    dockerfilePath: ./backend/Dockerfile.worker
    dockerContext: ./backend
  - name: kawu-dashboard
    type: web
    runtime: docker
    dockerfilePath: ./dashboard/Dockerfile
    dockerContext: ./dashboard
""",
        encoding="utf-8",
    )

    with pytest.raises(BlueprintValidationError, match="kawu-api"):
        validate_blueprint(blueprint, REPOSITORY_ROOT)


def test_dashboard_dockerignore_excludes_environment_files() -> None:
    dockerignore = (REPOSITORY_ROOT / "dashboard" / ".dockerignore").read_text(
        encoding="utf-8"
    )

    assert ".env" in dockerignore
    assert ".env.*" in dockerignore
    assert "!.env.example" in dockerignore
