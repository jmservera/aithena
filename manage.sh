#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ -n "${NO_COLOR:-}" || ! -t 1 ]]; then
  RED=""
  GREEN=""
  YELLOW=""
  BLUE=""
  BOLD=""
  RESET=""
else
  RED=$'\033[0;31m'
  GREEN=$'\033[0;32m'
  YELLOW=$'\033[1;33m'
  BLUE=$'\033[0;34m'
  BOLD=$'\033[1m'
  RESET=$'\033[0m'
fi

readonly DEFAULT_COMPOSE_FILE="docker-compose.yml"
readonly -a ONE_SHOT_SERVICES=("solr-init")

COMPOSE_FILE_ARGS=()

info() {
  printf "%b==>%b %s\n" "$BLUE" "$RESET" "$*"
}

success() {
  printf "%b✔%b %s\n" "$GREEN" "$RESET" "$*"
}

warn() {
  printf "%b!%b %s\n" "$YELLOW" "$RESET" "$*" >&2
}

error() {
  printf "%b✖%b %s\n" "$RED" "$RESET" "$*" >&2
}

die() {
  error "$*"
  exit 1
}

have_command() {
  command -v "$1" >/dev/null 2>&1
}

join_by() {
  local delimiter="$1"
  shift
  local first=1
  local item
  for item in "$@"; do
    if (( first )); then
      printf "%s" "$item"
      first=0
    else
      printf "%s%s" "$delimiter" "$item"
    fi
  done
}

ensure_docker() {
  have_command docker || die "docker is required but was not found in PATH."
  docker compose version >/dev/null 2>&1 || die "docker compose v2 plugin is required."
}

parse_start_sh_compose_files() {
  local line
  local -a tokens=()
  local index=0

  [[ -f "$ROOT/start.sh" ]] || return 1

  line="$(grep -E '^[[:space:]]*docker compose ' "$ROOT/start.sh" | tail -n 1 || true)"
  [[ -n "$line" ]] || return 1

  read -r -a tokens <<<"$line"
  while (( index < ${#tokens[@]} )); do
    case "${tokens[$index]}" in
      -f)
        (( index + 1 < ${#tokens[@]} )) || die "Invalid start.sh: missing value after -f."
        COMPOSE_FILE_ARGS+=("-f" "${tokens[$((index + 1))]}")
        index=$((index + 2))
        ;;
      up | down | build | logs | ps | exec | config)
        break
        ;;
      *)
        index=$((index + 1))
        ;;
    esac
  done

  (( ${#COMPOSE_FILE_ARGS[@]} > 0 ))
}

resolve_compose_file_args() {
  COMPOSE_FILE_ARGS=()

  if [[ -n "${AITHENA_COMPOSE_FILES:-}" ]]; then
    local -a files=()
    local file
    IFS=':' read -r -a files <<<"${AITHENA_COMPOSE_FILES}"
    for file in "${files[@]}"; do
      [[ -n "$file" ]] || continue
      COMPOSE_FILE_ARGS+=("-f" "$file")
    done
  elif [[ -n "${COMPOSE_FILE:-}" ]]; then
    local -a files=()
    local file
    IFS=':' read -r -a files <<<"${COMPOSE_FILE}"
    for file in "${files[@]}"; do
      [[ -n "$file" ]] || continue
      COMPOSE_FILE_ARGS+=("-f" "$file")
    done
  else
    parse_start_sh_compose_files || COMPOSE_FILE_ARGS=("-f" "$DEFAULT_COMPOSE_FILE")
  fi

  (( ${#COMPOSE_FILE_ARGS[@]} > 0 )) || COMPOSE_FILE_ARGS=("-f" "$DEFAULT_COMPOSE_FILE")
}

compose() {
  ensure_docker
  resolve_compose_file_args
  docker compose "${COMPOSE_FILE_ARGS[@]}" "$@"
}

compose_target_summary() {
  resolve_compose_file_args
  local files=()
  local index=0
  while (( index < ${#COMPOSE_FILE_ARGS[@]} )); do
    files+=("${COMPOSE_FILE_ARGS[$((index + 1))]}")
    index=$((index + 2))
  done
  join_by ", " "${files[@]}"
}

service_is_running() {
  local service="$1"
  compose ps --services --status running | grep -Fxq "$service"
}

require_service_arg() {
  [[ $# -ge 1 ]] || die "A service name is required. Try './manage.sh shell --help'."
}

print_main_help() {
  cat <<EOF
${BOLD}Aithena manage.sh${RESET}

Usage:
  ./manage.sh <command> [options]
  ./manage.sh --help

Core commands:
  up [service...]          Start services in detached mode
  down                     Stop and remove services
  build [service...]       Build all or selected services
  logs [service...]        Stream service logs (use --no-follow for one-shot output)
  health                   Summarize container health
  test                     Run repository test command
  status                   Show container status and health
  shell <service> [cmd]    Open a shell or run a command in a container
  reset                    Remove containers/volumes, then rebuild images

Environment overrides:
  AITHENA_COMPOSE_FILES    Colon-separated compose file list to use instead of start.sh
  COMPOSE_FILE             Standard docker compose override (also colon-separated)
  AITHENA_TEST_COMMAND     Override the command used by 'test'
  COMPOSE_PROJECT_NAME     Standard docker compose project-name override
  NO_COLOR=1               Disable ANSI colors

Detected compose files:
  $(compose_target_summary)

Run './manage.sh <command> --help' for command-specific details.
EOF
}

print_help_up() {
  cat <<EOF
Usage: ./manage.sh up [service...]

Start the configured Aithena stack in detached mode.
Equivalent to:
  docker compose $(join_by ' ' "${COMPOSE_FILE_ARGS[@]}") up -d [service...]
EOF
}

print_help_down() {
  cat <<EOF
Usage: ./manage.sh down

Stop and remove the configured Aithena containers, networks, and default resources.
Equivalent to:
  docker compose $(join_by ' ' "${COMPOSE_FILE_ARGS[@]}") down
EOF
}

print_help_build() {
  cat <<EOF
Usage: ./manage.sh build [service...]

Build all services or only the named services.
Equivalent to:
  docker compose $(join_by ' ' "${COMPOSE_FILE_ARGS[@]}") build [service...]
EOF
}

print_help_logs() {
  cat <<EOF
Usage: ./manage.sh logs [--no-follow] [service...]

Stream container logs for the whole stack or selected services.

Options:
  --no-follow   Print current logs without staying attached
EOF
}

print_help_health() {
  cat <<EOF
Usage: ./manage.sh health

Show a concise health summary based on 'docker compose ps --format json'.
Returns a non-zero exit code when any service is not healthy, running, or completed.
EOF
}

print_help_test() {
  cat <<EOF
Usage: ./manage.sh test

Run repository tests.
Default behavior:
  1. Run 'make test' when a Makefile with a test target is present
  2. Otherwise fall back to '.squad/scripts/verify.sh --all'

Override for automation:
  AITHENA_TEST_COMMAND='your command here' ./manage.sh test
EOF
}

print_help_status() {
  cat <<EOF
Usage: ./manage.sh status

Show container state, health, and published ports for the configured stack.
EOF
}

print_help_shell() {
  cat <<EOF
Usage: ./manage.sh shell <service> [command...]

Open an interactive shell in a running container, or run a one-shot command.

Examples:
  ./manage.sh shell solr sh
  ./manage.sh shell solr-search python -c 'print("ok")'
EOF
}

print_help_reset() {
  cat <<EOF
Usage: ./manage.sh reset

Destroy the configured stack, remove named volumes, and rebuild images.
Equivalent to:
  docker compose $(join_by ' ' "${COMPOSE_FILE_ARGS[@]}") down -v --remove-orphans
  docker compose $(join_by ' ' "${COMPOSE_FILE_ARGS[@]}") build
EOF
}

print_command_help() {
  resolve_compose_file_args
  case "$1" in
    up) print_help_up ;;
    down) print_help_down ;;
    build) print_help_build ;;
    logs) print_help_logs ;;
    health) print_help_health ;;
    test) print_help_test ;;
    status) print_help_status ;;
    shell) print_help_shell ;;
    reset) print_help_reset ;;
    help | --help | -h) print_main_help ;;
    *) die "Unknown command '$1'. Try './manage.sh --help'." ;;
  esac
}

render_compose_status() {
  local mode="$1"
  local one_shot_csv
  local compose_ps_json

  if ! have_command python3; then
    if [[ "$mode" == "status" ]]; then
      warn "python3 not found; falling back to 'docker compose ps' output for status."
      compose ps
      return 0
    fi
    die "python3 is required for './manage.sh health'. Install python3 or use 'docker compose ps' for a basic status view."
  fi

  one_shot_csv="$(join_by ',' "${ONE_SHOT_SERVICES[@]}")"
  compose_ps_json="$(compose ps --format json)"

  COMPOSE_PS_JSON="$compose_ps_json" python3 - "$mode" "$one_shot_csv" <<'PY'
import json
import os
import sys

mode = sys.argv[1]
one_shot = set(filter(None, sys.argv[2].split(",")))
raw = os.environ.get("COMPOSE_PS_JSON", "").strip()

if not raw:
    if mode == "health":
        print("No containers found for the selected compose files.")
        sys.exit(1)
    print("No containers found for the selected compose files.")
    sys.exit(0)

def load_items(payload: str):
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return [json.loads(line) for line in payload.splitlines() if line.strip()]
    if isinstance(data, list):
        return data
    return [data]

items = load_items(raw)

def value(item, *keys):
    for key in keys:
        if item.get(key) not in (None, ""):
            return item.get(key)
    return ""

def classify(item):
    service = value(item, "Service", "service", "Name", "name")
    state = str(value(item, "State", "state", "Status", "status")).lower()
    health = str(value(item, "Health", "health")).lower()
    exit_code = str(value(item, "ExitCode", "exitCode", "exit_code"))

    if service in one_shot and state.startswith("exited") and exit_code in {"0", ""}:
        return "completed"
    if health == "healthy":
        return "healthy"
    if health:
        return health
    if state == "running":
        return "running"
    if state == "created":
        return "created"
    if state.startswith("restarting"):
        return "restarting"
    if state.startswith("exited"):
        return "stopped"
    return state or "unknown"

def publishers_to_text(item):
    publishers = item.get("Publishers") or item.get("publishers") or []
    if not publishers:
        return "-"
    parts = []
    for publisher in publishers:
        url = publisher.get("URL") or publisher.get("url") or "0.0.0.0"
        published = publisher.get("PublishedPort") or publisher.get("published_port")
        target = publisher.get("TargetPort") or publisher.get("target_port")
        protocol = publisher.get("Protocol") or publisher.get("protocol") or "tcp"
        parts.append(f"{url}:{published}->{target}/{protocol}")
    return ", ".join(parts)

rows = []
healthy_like = {"healthy", "running", "completed"}
bad_rows = []

for item in items:
    service = value(item, "Service", "service", "Name", "name")
    name = value(item, "Name", "name", "Service", "service")
    state = value(item, "State", "state", "Status", "status") or "unknown"
    health = classify(item)
    ports = publishers_to_text(item)
    rows.append((service, name, state, health, ports))
    if health not in healthy_like:
        bad_rows.append((service, health))

if mode == "health":
    for service, _, state, health, _ in rows:
        print(f"{service}: {health} ({state})")
    if bad_rows:
        sys.exit(1)
    sys.exit(0)

widths = [7, 9, 5, 6, 5]
headers = ("SERVICE", "CONTAINER", "STATE", "HEALTH", "PORTS")
for row in rows:
    for idx, col in enumerate(row):
        widths[idx] = max(widths[idx], len(str(col)))

def fmt(row):
    return "  ".join(str(col).ljust(widths[idx]) for idx, col in enumerate(row))

print(fmt(headers))
print("  ".join("-" * width for width in widths))
for row in rows:
    print(fmt(row))

PY
}

cmd_up() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    print_command_help up
    return 0
  fi

  info "Starting services with compose files: $(compose_target_summary)"
  compose up -d "$@"
  success "Services started."
}

cmd_down() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    print_command_help down
    return 0
  fi

  info "Stopping services with compose files: $(compose_target_summary)"
  compose down
  success "Services stopped."
}

cmd_build() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    print_command_help build
    return 0
  fi

  info "Building services with compose files: $(compose_target_summary)"
  compose build "$@"
  success "Build completed."
}

cmd_logs() {
  local follow=1

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --help | -h)
        print_command_help logs
        return 0
        ;;
      --no-follow)
        follow=0
        shift
        ;;
      *)
        break
        ;;
    esac
  done

  if (( follow )); then
    compose logs -f "$@"
  else
    compose logs "$@"
  fi
}

cmd_health() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    print_command_help health
    return 0
  fi

  info "Health summary for compose files: $(compose_target_summary)"
  render_compose_status health
}

cmd_test() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    print_command_help test
    return 0
  fi

  if [[ -n "${AITHENA_TEST_COMMAND:-}" ]]; then
    info "Running AITHENA_TEST_COMMAND override."
    bash -lc "${AITHENA_TEST_COMMAND}"
    return 0
  fi

  if have_command make && [[ -f "$ROOT/Makefile" ]] && grep -Eq '^test:' "$ROOT/Makefile"; then
    info "Running make test"
    make test
    return 0
  fi

  if [[ -x "$ROOT/.squad/scripts/verify.sh" ]]; then
    warn "Makefile test target not found; falling back to .squad/scripts/verify.sh --all."
    "$ROOT/.squad/scripts/verify.sh" --all
    return 0
  fi

  die "No test command is available. Expected 'make test' or .squad/scripts/verify.sh."
}

cmd_status() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    print_command_help status
    return 0
  fi

  info "Container status for compose files: $(compose_target_summary)"
  render_compose_status status
}

cmd_shell() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    print_command_help shell
    return 0
  fi

  require_service_arg "$@"
  local service="$1"
  shift

  service_is_running "$service" || die "Service '$service' is not running."

  if [[ $# -gt 0 ]]; then
    compose exec -T "$service" "$@"
    return 0
  fi

  if compose exec -T "$service" sh -lc 'command -v bash >/dev/null 2>&1'; then
    compose exec "$service" bash
  else
    compose exec "$service" sh
  fi
}

cmd_reset() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    print_command_help reset
    return 0
  fi

  info "Resetting stack for compose files: $(compose_target_summary)"
  compose down -v --remove-orphans
  compose build
  success "Stack reset completed. Use './manage.sh up' to start it again."
}

main() {
  local command="${1:-}"

  case "$command" in
    "" | --help | -h | help)
      print_main_help
      ;;
    up)
      shift
      cmd_up "$@"
      ;;
    down)
      shift
      cmd_down "$@"
      ;;
    build)
      shift
      cmd_build "$@"
      ;;
    logs)
      shift
      cmd_logs "$@"
      ;;
    health)
      shift
      cmd_health "$@"
      ;;
    test)
      shift
      cmd_test "$@"
      ;;
    status)
      shift
      cmd_status "$@"
      ;;
    shell)
      shift
      cmd_shell "$@"
      ;;
    reset)
      shift
      cmd_reset "$@"
      ;;
    *)
      die "Unknown command '$command'. Try './manage.sh --help'."
      ;;
  esac
}

main "$@"
