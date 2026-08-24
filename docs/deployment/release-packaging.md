# Release packaging

Aithena ships a **source release package**: `aithena-<version>.tar.gz`, whose
archive root is `aithena-<version>/`. Everything needed to install and run the
stack from source is inside it — the Compose files, every build context, every
Dockerfile (explicit and implicit), every Dockerfile `COPY` source, the shared
`src/aithena-common` package, the bind-mounted configuration files, the
installer and the shipped documentation set.

## Building the package

```bash
scripts/build-release-package.sh --output-dir /path/to/artifacts
```

Options:

| Option | Purpose |
| ------ | ------- |
| `--output-dir DIR` | **Required.** Directory that receives the archive. |
| `--version VERSION` | Override the version (defaults to the `VERSION` file). |
| `--require-docker` | Fail unless `docker compose config` can derive the inventory. |
| `--help` | Show usage. |

The builder writes exactly two files into the output directory:
`aithena-<version>.tar.gz` and `aithena-<version>.tar.gz.sha256`. Both are
written to a temporary file inside the same directory and then moved into place,
so a failed run never leaves a half-written archive and never touches unrelated
files.

### Output directory safety

The builder refuses to write into a directory it does not own. It exits with
status `3` for the filesystem root, `$HOME`, this repository, any registered git
worktree (including every ancestor and descendant of each), any other git
working tree, any path that is not a directory, and any directory holding
content other than previous `aithena-*.tar.gz` artifacts or a `.gitignore`.
Symlink and whitespace aliases are canonicalised before the checks run, and a
marker file never authorises deletion — nothing outside the script's own
`mktemp` staging directory is ever removed.

## What ends up in the archive

The file list is derived from the Compose project itself rather than hand
maintained. `scripts/release_inventory.py` runs `docker compose config
--format json` over every supported Compose combination (falling back to a
deterministic YAML parser that understands anchors, indentation, quoted `#` and
the Compose `!override`/`!reset` tags when Docker is unavailable) and collects:

- every build context and its Dockerfile, including implicit `Dockerfile`s that
  are never named in the Compose file;
- every `COPY` source inside those Dockerfiles, including `--chown`/`--from`
  flags, multiple sources, JSON-array form and directories;
- every `env_file`, config, secret and relative bind-mount path.

Absolute paths, `..` traversal and unresolved interpolations are hard failures,
not warnings. The resulting inventory is shipped inside the archive as
`release-inventory.json` and can be re-checked at any time:

```bash
python3 scripts/release_inventory.py validate \
  --root aithena-<version> \
  --inventory aithena-<version>/release-inventory.json
```

### Shipped Compose overlays

All supported overlays are shipped: `docker/compose.prod.yml`,
`compose.ssl.yml`, `compose.gpu-nvidia.yml`, `compose.gpu-intel.yml`,
`compose.single-node.yml`, `compose.solr9.yml`, `compose.solr10.yml`,
`compose.e2e.yml`, `compose.ci-ports.yml` and `compose.dev-ports.yml`. The
inventory generator fails if an overlay exists on disk but is classified neither
as shipped nor as explicitly unshipped, so an overlay can never be silently
dropped.

## Installing from the package

```bash
tar -xzf aithena-<version>.tar.gz
cd aithena-<version>
./install.sh --check     # validate the extracted package
./installer/run.sh       # run the first-run installer
```

`./install.sh --check` re-runs the inventory validation against the extracted
tree, so a truncated or tampered download fails loudly instead of half-working.

## Tests

| Command | Covers |
| ------- | ------ |
| `make test-release-pytest` | Inventory, Dockerfile `COPY` parsing, generated offline installer scripts, `installer/run.sh` interpreter probing |
| `make test-release-safety` | Destructive-safety regressions for the builder |
| `make test-release-smoke` | Build, extract, run the literal documented commands, validate docs and inventory |
| `make test-release` | All of the above |

Add `RELEASE_SMOKE_ARGS=--require-docker` to make a missing Docker CLI a hard
failure instead of skipping only the runtime `docker compose config` checks; CI
always does this.
