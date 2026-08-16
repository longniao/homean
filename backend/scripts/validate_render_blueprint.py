"""Validate Render Blueprint paths without contacting Render."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

EXPECTED_DOCKER_SERVICES = {
    "homean-api": {
        "dockerfilePath": "backend/Dockerfile.api",
        "dockerContext": "backend",
        "type": "web",
    },
    "homean-worker": {
        "dockerfilePath": "backend/Dockerfile.worker",
        "dockerContext": "backend",
        "type": "worker",
    },
    "homean-dashboard": {
        "dockerfilePath": "dashboard/Dockerfile",
        "dockerContext": "dashboard",
        "type": "web",
    },
}

EXPECTED_STATIC_SERVICES = {
    "homean-marketing": {
        "buildCommand": "cd marketing && npm ci && npm run build",
        "staticPublishPath": "marketing/out",
        "type": "web",
        "envVars": {
            "NEXT_PUBLIC_SITE_URL": {"sync": False},
            "NEXT_PUBLIC_APP_URL": {
                "fromService": {
                    "type": "web",
                    "name": "homean-dashboard",
                    "envVarKey": "RENDER_EXTERNAL_URL",
                }
            },
            "NEXT_PUBLIC_PILOT_EMAIL": {"sync": False},
            "NEXT_PUBLIC_SITE_INDEXABLE": {"value": "false"},
        },
    }
}


class BlueprintValidationError(ValueError):
    """Raised when the checked-in Blueprint cannot be built from this repository."""


def _repository_relative_path(
    repository_root: Path, raw_path: Any, *, field: str, service_name: str
) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise BlueprintValidationError(
            f"{service_name} must define a non-empty {field}"
        )

    path_text = raw_path.removeprefix("./")
    path = (repository_root / path_text).resolve()
    try:
        path.relative_to(repository_root)
    except ValueError as exc:
        raise BlueprintValidationError(
            f"{service_name} {field} must stay inside the repository: {raw_path}"
        ) from exc
    return path


def _load_blueprint(blueprint_path: Path) -> dict[str, Any]:
    try:
        document = yaml.safe_load(blueprint_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise BlueprintValidationError(
            f"Render Blueprint is not valid YAML: {blueprint_path}"
        ) from exc

    if not isinstance(document, dict):
        raise BlueprintValidationError("Render Blueprint root must be a mapping")
    return document


def _validate_docker_services(
    document: dict[str, Any], repository_root: Path
) -> list[str]:
    services = document.get("services")
    if not isinstance(services, list):
        raise BlueprintValidationError("Render Blueprint services must be a list")

    services_by_name: dict[str, dict[str, Any]] = {}
    for service in services:
        if not isinstance(service, dict):
            raise BlueprintValidationError("Every Render service must be a mapping")
        name = service.get("name")
        if isinstance(name, str):
            services_by_name[name] = service

    missing = sorted(set(EXPECTED_DOCKER_SERVICES) - set(services_by_name))
    if missing:
        raise BlueprintValidationError(
            "Render Blueprint is missing expected services: " + ", ".join(missing)
        )
    docker_service_names = {
        service.get("name")
        for service in services
        if service.get("runtime") == "docker"
    }
    unexpected = sorted(
        str(name)
        for name in docker_service_names
        if name not in EXPECTED_DOCKER_SERVICES
    )
    if unexpected:
        raise BlueprintValidationError(
            "Render Blueprint has unexpected Docker services: "
            + ", ".join(str(name) for name in unexpected)
        )

    validated: list[str] = []
    for service_name, expected in EXPECTED_DOCKER_SERVICES.items():
        service = services_by_name[service_name]
        if service.get("runtime") != "docker":
            raise BlueprintValidationError(f"{service_name} must use runtime: docker")
        if service.get("type") != expected["type"]:
            raise BlueprintValidationError(
                f"{service_name} must use type: {expected['type']}"
            )

        docker_context = _repository_relative_path(
            repository_root,
            service.get("dockerContext"),
            field="dockerContext",
            service_name=service_name,
        )
        if not docker_context.is_dir():
            raise BlueprintValidationError(
                f"{service_name} Docker context does not exist: "
                f"{service.get('dockerContext')}"
            )

        dockerfile = _repository_relative_path(
            repository_root,
            service.get("dockerfilePath"),
            field="dockerfilePath",
            service_name=service_name,
        )
        if not dockerfile.is_file():
            raise BlueprintValidationError(
                f"{service_name} Dockerfile does not exist: "
                f"{service.get('dockerfilePath')}"
            )
        try:
            dockerfile.relative_to(docker_context)
        except ValueError as exc:
            raise BlueprintValidationError(
                f"{service_name} Dockerfile must be inside its Docker context: "
                f"{service.get('dockerfilePath')}"
            ) from exc

        expected_dockerfile = repository_root / expected["dockerfilePath"]
        expected_context = repository_root / expected["dockerContext"]
        if dockerfile != expected_dockerfile.resolve():
            raise BlueprintValidationError(
                f"{service_name} must use {expected['dockerfilePath']}"
            )
        if docker_context != expected_context.resolve():
            raise BlueprintValidationError(
                f"{service_name} must use {expected['dockerContext']} as its "
                "Docker context"
            )
        validated.append(service_name)

    return validated


def _validate_dashboard_dockerignore(repository_root: Path) -> None:
    dockerignore = repository_root / "dashboard" / ".dockerignore"
    if not dockerignore.is_file():
        raise BlueprintValidationError("dashboard/.dockerignore is missing")

    patterns = {
        line.strip()
        for line in dockerignore.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    if not {".env", ".env.*"}.issubset(patterns):
        raise BlueprintValidationError(
            "dashboard/.dockerignore must exclude .env and .env.* files"
        )
    if "!.env.example" not in patterns:
        raise BlueprintValidationError(
            "dashboard/.dockerignore must explicitly retain the safe .env.example"
        )


def _validate_static_services(
    document: dict[str, Any], repository_root: Path
) -> list[str]:
    services = document.get("services")
    if not isinstance(services, list):
        raise BlueprintValidationError("Render Blueprint services must be a list")

    services_by_name = {
        service.get("name"): service
        for service in services
        if isinstance(service, dict) and isinstance(service.get("name"), str)
    }
    missing = sorted(set(EXPECTED_STATIC_SERVICES) - set(services_by_name))
    if missing:
        raise BlueprintValidationError(
            "Render Blueprint is missing expected static services: "
            + ", ".join(missing)
        )

    validated: list[str] = []
    for service_name, expected in EXPECTED_STATIC_SERVICES.items():
        service = services_by_name[service_name]
        if service.get("type") != expected["type"]:
            raise BlueprintValidationError(f"{service_name} must use type: web")
        if service.get("runtime") != "static":
            raise BlueprintValidationError(f"{service_name} must use runtime: static")
        if service.get("buildCommand") != expected["buildCommand"]:
            raise BlueprintValidationError(
                f"{service_name} must use buildCommand: {expected['buildCommand']}"
            )
        env_vars = {
            env_var.get("key"): {
                key: value for key, value in env_var.items() if key != "key"
            }
            for env_var in service.get("envVars", [])
            if isinstance(env_var, dict) and isinstance(env_var.get("key"), str)
        }
        if {key: env_vars.get(key) for key in expected["envVars"]} != expected[
            "envVars"
        ]:
            raise BlueprintValidationError(
                f"{service_name} must define the expected public build-time environment"
            )
        publish_path = _repository_relative_path(
            repository_root,
            service.get("staticPublishPath"),
            field="staticPublishPath",
            service_name=service_name,
        )
        if publish_path.parent != (repository_root / "marketing").resolve():
            raise BlueprintValidationError(
                f"{service_name} staticPublishPath must publish the marketing export"
            )
        if not (repository_root / "marketing" / "package.json").is_file():
            raise BlueprintValidationError("marketing/package.json is missing")
        validated.append(service_name)
    return validated


def validate_blueprint(
    blueprint_path: Path, repository_root: Path | None = None
) -> tuple[str, ...]:
    """Validate the local Docker portions of a Render Blueprint."""

    resolved_blueprint = blueprint_path.resolve()
    root = (repository_root or resolved_blueprint.parent.parent).resolve()
    document = _load_blueprint(resolved_blueprint)
    validated_services = _validate_docker_services(document, root)
    validated_services.extend(_validate_static_services(document, root))
    _validate_dashboard_dockerignore(root)
    return tuple(validated_services)


def main() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    blueprint_path = repository_root / "infra" / "render.yaml"
    try:
        services = validate_blueprint(blueprint_path, repository_root)
    except (OSError, BlueprintValidationError) as exc:
        raise SystemExit(f"Render Blueprint validation failed: {exc}") from exc

    print(
        "Render Blueprint: validated local Docker contexts and Dockerfiles for "
        + ", ".join(services)
    )


if __name__ == "__main__":
    main()
