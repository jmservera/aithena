#!/usr/bin/env python3
"""
Release package inventory builder: derives complete artifact manifest from
docker compose configuration and shipped documentation, with regression
tracking for every implicit build context Dockerfile.

Usage:
  scripts/release_inventory.py --compose-dir . --format json > inventory.json
  scripts/release_inventory.py --compose-dir . --format json | \
    python3 -m json.tool | grep -E '"Dockerfile|implicit'
"""
import json
import re
import subprocess
import sys
from pathlib import Path


def docker_compose_config(compose_dir: str, format_output: str = "json") -> dict:
    """
    Get authoritative Compose configuration from 'docker compose config'.

    Falls back to manual YAML parsing only if docker is unavailable, and
    only to extract build contexts (no merge tag handling, deterministic).
    """
    try:
        result = subprocess.run(  # noqa: S603, S607
            ["docker", "compose", "config", "--format", format_output],  # noqa: S607
            cwd=compose_dir,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass

    # Docker unavailable: use manual YAML parser for build contexts only
    import yaml
    compose_file = Path(compose_dir) / "docker-compose.yml"
    if not compose_file.exists():
        msg = f"docker-compose.yml not found in {compose_dir}"
        raise FileNotFoundError(msg)

    with open(compose_file) as f:
        data = yaml.safe_load(f)

    return data or {}


def extract_build_contexts(config: dict, base_dir: Path) -> dict[str, dict]:
    """
    Extract all build contexts from Compose config.

    Returns mapping:
      {
        "src/solr": {"implicit": True, "dockerfile": "Dockerfile", ...},
        "src/nginx": {"implicit": True, "dockerfile": "Dockerfile", ...},
        ...
      }
    """
    contexts = {}
    services = config.get("services", {})

    for service_name, service_def in services.items():
        if not isinstance(service_def, dict):
            continue

        build = service_def.get("build")
        if not build:
            continue

        # Normalize build context path
        if isinstance(build, str):
            context = build
            dockerfile = "Dockerfile"
        elif isinstance(build, dict):
            context = build.get("context", ".")
            dockerfile = build.get("dockerfile", "Dockerfile")
        else:
            continue

        # Resolve relative paths
        if not context.startswith("/"):
            context = context.lstrip("./")

        # Handle root context case
        if not context:
            context = "."

        if context not in contexts:
            contexts[context] = {
                "implicit": dockerfile == "Dockerfile",
                "dockerfile": dockerfile,
                "services": [],
            }

        if service_name not in contexts[context]["services"]:
            contexts[context]["services"].append(service_name)

    return contexts


def extract_dockerfile_copy_sources(
    config: dict, base_dir: Path, contexts: dict[str, dict]
) -> dict[str, set[str]]:
    """
    For each build context, extract COPY source paths from Dockerfile.

    Returns:
      {
        "src/solr": {"solr/log4j2.xml", "solr/entrypoint.sh", ...},
        ...
      }
    """
    copy_sources = {}

    for context_path, context_info in contexts.items():
        dockerfile_path = base_dir / context_path / context_info["dockerfile"]
        if not dockerfile_path.exists():
            continue

        copy_sources[context_path] = set()

        with open(dockerfile_path) as f:
            for line in f:
                # Extract COPY source paths (basic regex, non-multiline only)
                match = re.match(r"^\s*COPY\s+([^\s]+)\s+", line, re.IGNORECASE)
                if match:
                    src = match.group(1)
                    if not src.startswith("/"):  # Ignore absolute paths
                        copy_sources[context_path].add(src)

    return copy_sources


def extract_bind_mounts(config: dict) -> dict[str, str]:
    """
    Extract all bind-mount paths from Compose services.

    Returns: {"./src/nginx/ssl.conf.template": "...", ...}
    """
    mounts = {}
    services = config.get("services", {})

    for service_def in services.values():
        if not isinstance(service_def, dict):
            continue

        volumes = service_def.get("volumes", [])
        if not isinstance(volumes, list):
            volumes = [volumes]

        for volume in volumes:
            if isinstance(volume, str) and ":" in volume:
                src = volume.split(":")[0].strip()
                if not src.startswith("/") and src not in mounts:
                    mounts[src] = True

    return mounts


def extract_env_files(config: dict) -> set[str]:
    """Extract all env_file references from services."""
    env_files = set()
    services = config.get("services", {})

    for service_def in services.values():
        if not isinstance(service_def, dict):
            continue

        env_file = service_def.get("env_file")
        if env_file:
            if isinstance(env_file, str):
                env_files.add(env_file)
            elif isinstance(env_file, list):
                env_files.update(env_file)

    return env_files


def generate_inventory(base_dir: str, include_regression_manifest: bool = True) -> dict:
    """
    Generate complete release inventory from Compose config and shipped docs.

    Returns a comprehensive manifest for validation.
    """
    base = Path(base_dir)
    config = docker_compose_config(base_dir)

    build_contexts = extract_build_contexts(config, base)
    copy_sources = extract_dockerfile_copy_sources(config, base, build_contexts)
    bind_mounts = extract_bind_mounts(config)
    env_files = extract_env_files(config)

    inventory = {
        "build_contexts": {
            ctx: {
                "implicit": info["implicit"],
                "dockerfile": info["dockerfile"],
                "services": info["services"],
                "dockerfile_path": f"{ctx}/{info['dockerfile']}",
                "copy_sources": sorted(copy_sources.get(ctx, [])),
            }
            for ctx, info in build_contexts.items()
        },
        "bind_mounts": sorted(bind_mounts.keys()),
        "env_files": sorted(env_files),
        "services": sorted(config.get("services", {}).keys()),
    }

    # Add regression test manifest
    if include_regression_manifest:
        implicit_dockerfiles = [
            f"{ctx}/{info['dockerfile']}"
            for ctx, info in build_contexts.items()
            if info["implicit"]
        ]

        inventory["implicit_dockerfiles_for_regression"] = sorted(
            implicit_dockerfiles
        )
        inventory["regression_test_count"] = len(implicit_dockerfiles)
        if not implicit_dockerfiles:
            print(
                "WARNING: No implicit Dockerfiles found for regression testing",
                file=sys.stderr,
            )

    return inventory


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate release package inventory")
    parser.add_argument("--compose-dir", default=".", help="Compose directory (default: .)")
    parser.add_argument("--format", choices=["json", "text"], default="json")

    args = parser.parse_args()

    try:
        inventory = generate_inventory(args.compose_dir)

        if args.format == "json":
            print(json.dumps(inventory, indent=2))
        else:
            print(f"Build Contexts ({len(inventory['build_contexts'])}):")
            for ctx, info in inventory["build_contexts"].items():
                implicit = "IMPLICIT" if info["implicit"] else "explicit"
                print(f"  {ctx} ({implicit}): {info['dockerfile']}")
                if info["copy_sources"]:
                    for src in info["copy_sources"]:
                        print(f"    COPY {src}")
                print(f"    Services: {', '.join(info['services'])}")

            print(f"\nBind Mounts ({len(inventory['bind_mounts'])}):")
            for mount in inventory["bind_mounts"]:
                print(f"  {mount}")

            print(
                f"\nImplicit Dockerfiles for Regression "
                f"({inventory['regression_test_count']}):"
            )
            for df in inventory["implicit_dockerfiles_for_regression"]:
                print(f"  {df}")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
