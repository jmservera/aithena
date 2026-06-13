#!/usr/bin/env bash

aithena_load_dotenv() {
  local root="$1"
  if [[ -f "$root/.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$root/.env"
    set +a
  fi
}

aithena_export_build_metadata() {
  local root="$1"
  local version_file="$root/VERSION"
  local git_tag

  if git_tag="$(git -C "$root" describe --tags --exact-match 2>/dev/null)"; then
    VERSION="${git_tag#v}"
  elif [[ -f "$version_file" ]]; then
    VERSION="$(tr -d '[:space:]' < "$version_file")"
  else
    VERSION="dev"
  fi

  if [[ -z "$VERSION" ]]; then
    VERSION="dev"
  fi

  GIT_COMMIT="$(git -C "$root" rev-parse HEAD 2>/dev/null || printf 'unknown')"
  BUILD_DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  export VERSION GIT_COMMIT BUILD_DATE
}

aithena_safe_log_name() {
  local name="$1"
  printf '%s' "$name" | tr -c '[:alnum:]_.-' '_'
}

aithena_record_failure() {
  local -n failures_ref="$1"
  local label="$2"
  local status="$3"
  local log_file="$4"
  failures_ref+=("${label}|${status}|${log_file}")
}

aithena_print_failure_summary() {
  local -n failures_ref="$1"
  echo "" >&2
  echo "Build failed with ${#failures_ref[@]} failure(s):" >&2

  local failure label status log_file
  for failure in "${failures_ref[@]}"; do
    IFS='|' read -r label status log_file <<< "$failure"
    echo "  - ${label} exited with status ${status}" >&2
    echo "    log: ${log_file}" >&2
  done
}

aithena_run_logged() {
  local artifact_dir="$1"
  local log_timestamp="$2"
  local failures_name="$3"
  local label="$4"
  local log_slug="$5"
  local workdir="$6"
  shift 6

  mkdir -p "$artifact_dir"
  local log_file="${artifact_dir}/buildall-$(aithena_safe_log_name "$log_slug")-${log_timestamp}.log"

  echo "Running ${label}"
  echo "  log: ${log_file}"
  if (
    cd "$workdir"
    "$@"
  ) > "$log_file" 2>&1; then
    echo "  ✅ ${label} succeeded"
    return 0
  else
    local status=$?
    echo "  ❌ ${label} failed (exit ${status})"
    aithena_record_failure "$failures_name" "$label" "$status" "$log_file"
    return 1
  fi
}

aithena_discover_docker_service_dirs() {
  local root="$1"
  (
    cd "$root"
    find src -mindepth 2 -maxdepth 2 -type f -name Dockerfile -exec dirname {} \; \
      | LC_ALL=C sort -u
  )
}

aithena_discover_python_service_dirs() {
  local root="$1"
  local service_dir

  while IFS= read -r service_dir; do
    [[ -f "$root/$service_dir/pyproject.toml" ]] && printf '%s\n' "$service_dir"
  done < <(aithena_discover_docker_service_dirs "$root")
}

aithena_discover_python_service_dirs_for_targets() {
  local root="$1"
  shift

  local -a targets=("$@")
  if [[ ${#targets[@]} -eq 0 ]]; then
    aithena_discover_python_service_dirs "$root"
    return 0
  fi

  local service_dir service_name target
  while IFS= read -r service_dir; do
    service_name="$(basename "$service_dir")"
    for target in "${targets[@]}"; do
      if [[ "$target" == "$service_name" || "$target" == "$service_dir" || "$target" == "$root/$service_dir" ]]; then
        printf '%s\n' "$service_dir"
        break
      fi
    done
  done < <(aithena_discover_python_service_dirs "$root")
}

aithena_prepare_python_services() {
  local root="$1"
  local artifact_dir="$2"
  local log_timestamp="$3"
  local failures_name="$4"
  shift 4

  local service_dir service_name
  for service_dir in "$@"; do
    service_name="$(basename "$service_dir")"
    aithena_run_logged \
      "$artifact_dir" \
      "$log_timestamp" \
      "$failures_name" \
      "uv sync in ${service_dir}" \
      "$service_name" \
      "$root/$service_dir" \
      uv sync || true
  done
}
