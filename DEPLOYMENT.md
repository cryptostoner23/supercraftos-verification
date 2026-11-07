# Deploying SuperCraftOS

The supplied image runs the Python control center as UID/GID `10001`, with durable
state in `/app/data`. It includes the pinned core Python dependencies and the
`o200k_base` tokenizer cache. CAD, a local browser, the Rust worker, iOS builds,
and the separately installed `agent-brain` checkout are optional and are not
included. An empty installation has no provider credentials or prior live evidence.
The app starts its durable worker by default. File and text tools work inside
the core container; command execution requires the native worker deployment below
with access to a Docker daemon. Compose deliberately supplies no Docker socket.

## Prerequisites and first launch

Use a Linux host with Docker Engine and the Compose plugin. Budget at least 2 GB
RAM for building/checking the core image and several GB of disk space; these are
starting allowances, not measured peak guarantees. The Compose service has a
1 GB container memory limit; the runtime also samples its own 512 MB process
budget. Size optional browser/CAD workloads separately. Python packages must be
available from the configured package index; the base image, packages and public
tokenizer file are fetched during the build. No provider keys are needed to build.

From the repository root:

```bash
cp .env.example .env
chmod 600 .env
# Populate only the provider variables needed for your workload.
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail 100 supercraftos
```

Open `http://127.0.0.1:8787` on that host. The application only permits loopback
binds and loopback Host/Origin values; Compose uses **Linux host networking** so
this works without changing that policy. Port 8787 must be unused. This recipe
does not use Docker bridge port publishing and is not a portable Docker Desktop
recipe. To access a remote host privately, forward the port over SSH:

```bash
ssh -N -L 8787:127.0.0.1:8787 user@your-server
```

Then open the same loopback URL on your local machine. For HTTPS access without
SSH, use the optional private gateway below. The dashboard's session token
protects mutations but is available to anyone who can open its loopback page;
public ingress must terminate at the gateway.

The health check only verifies the local status endpoint. It does not establish
provider authentication, model availability, or successful agent work. Docker
restarts an exited process; an unhealthy health check alone does not restart it.
Use one service replica per data volume: this deployment does not establish
multi-instance coordination.

## Credentials and persistent state

Model inference requires a configured model provider. Set
`SUPERCRAFTOS_LLM_BASE_URL` to an HTTPS OpenAI-compatible API base,
`SUPERCRAFTOS_LLM_API_KEY`, and `SUPERCRAFTOS_MODEL` (optionally
`SUPERCRAFTOS_LIGHT_MODEL`), or use the recognized `OPENROUTER_API_KEY` route.
The legacy default uses `NVIDIA_API_KEY` and models in `agent.config.yaml`.
An OpenCode key alone does not select that provider: the supported verified
provider selection must also be configured. Individual integrations need their
corresponding credentials in `.env`. Compose injects this file into the process; it is excluded from the image
and Git. Recreate the service after changing it:

```bash
docker compose up -d --force-recreate
docker compose exec supercraftos python main.py doctor
```

`doctor` checks local configuration and installed packages. `healthcheck`,
`capabilities`, `research`, model tasks and registration/setup can contact live
services, incur provider charges, or create external resources. Run them only for
an intended integration action. App/runtime startup also performs public release
metadata checks. `AUTO_UPGRADE` and `SYNC_CAPABILITIES` are forced off in Compose;
change that explicit configuration to opt into those workflows.

The named `supercraftos-data` volume stores SQLite checkpoints, durable jobs in
`jobs.sqlite3`, job workspaces in `workspaces/`, artifacts,
usage, cached metadata and encrypted credentials. Back up the **entire volume**,
including `vault.key`, `access.key` when using the gateway, and encrypted records,
together. Stop the service before a
filesystem backup so SQLite databases and their WAL files are consistent. Also
back up the host `.env` and record the running image ID. Protect backups as secrets.
Restore to the same path with UID/GID `10001` ownership. Avoid
`docker compose down --volumes` unless intentionally deleting all state.

The container's remaining filesystem is disposable. Integration commands that
write additional values to `/app/.env` do not update the host `.env`; transfer
needed configuration to the host environment before recreating the container.
Do not bind an existing data directory without giving UID `10001` access.

## Release checks and updates

The GitHub workflow builds this image from a clean checkout, validates Compose,
then runs syntax checks, `pip check`, `doctor` and unittest discovery in a
disposable container with **`--network none`**. Loopback HTTP fixtures work;
external access, including from subprocesses, is blocked. No repository secrets
are passed into the container. CAD generation is explicitly skipped in the core
image; the CAD installation-state test runs and checks the actual environment.
Real Docker sandbox tests remain opt-in with `SUPERCRAFTOS_TEST_DOCKER=1` and
are skipped by default. All other discovered core tests must pass.

Run the same checks locally without starting the service or mounting real state:

```bash
docker build -t supercraftos:check .
docker run --rm --init --network none --memory 2g \
  --entrypoint python supercraftos:check .github/ci/offline_checks.py
```

To run the separate real Docker sandbox checks, use a native test checkout with
a working Docker CLI/daemon and the sandbox image already pulled. These checks
exercise isolation, failure, timeout, cancellation and crash cleanup. Enable
them explicitly for the test command; keep the core CI container free of Docker
socket mounts:

```bash
SUPERCRAFTOS_TEST_DOCKER=1 .venv/bin/python -m unittest -v test_sandbox_integration
```

`requirements.lock` pins package versions; it has no artifact hashes. The default
Python image tag and package indexes are mutable, so this is not a byte-identical
or hermetic build guarantee. For a release, set `PYTHON_IMAGE` to an approved
Python 3.12 image digest, record the Git commit and built image digest, and retain
that image. Use a unique `SUPERCRAFTOS_IMAGE` tag for each release. Deploy the
already checked image with `docker compose up -d --no-build`.

Before an update, stop the service and back up state. To roll back, use the prior
image with `--no-build`; restore the matching state backup if a newer version
changed its schema. Image rollback alone does not promise database compatibility.
CI builds and tests only; it does not push images or deploy services.

## Native installation

A native installation can live in any writable checkout; `/root/SuperCraftOS` is
not required. Use Python 3.12 and run from the repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip check
cp .env.example .env
chmod 600 .env
export TIKTOKEN_CACHE_DIR="$PWD/data/tiktoken-cache"
.venv/bin/python -c "import tiktoken; tiktoken.get_encoding('o200k_base')"
.venv/bin/python main.py doctor
.venv/bin/python main.py app
```

The tokenizer command downloads public vocabulary data once. Run automated checks
in a disposable checkout with no real `.env` or `data`, and isolate its network;
the CI script by itself is not a network sandbox. A native long-lived deployment
can use the supplied systemd units described below.

## Full native worker deployment with systemd

Use the same tested checkout and Python 3.12 environment at `/root/SuperCraftOS` on
a Linux systemd host. The two units in `deploy/systemd` run the loopback dashboard
and a separate durable worker under the same dedicated account. The app unit
forces `SUPERCRAFTOS_EMBEDDED_WORKER=0` so it does not start a second job worker.
Do not run Compose alongside these units against the same data.

Install Docker Engine and its CLI first, then prepare the service account and
directories (administrative commands; adjust paths if installing elsewhere):

```bash
sudo useradd --system --create-home --home-dir /var/lib/supercraftos supercraftos
sudo install -d -o supercraftos -g supercraftos -m 0750 /root/SuperCraftOS
# Place the tested checkout in /root/SuperCraftOS, owned by this account.
sudo chown -R supercraftos:supercraftos /root/SuperCraftOS
sudo -u supercraftos python3.12 -m venv /root/SuperCraftOS/.venv
sudo -u supercraftos /root/SuperCraftOS/.venv/bin/python -m pip install \
  -r /root/SuperCraftOS/requirements.lock
sudo -u supercraftos install -d -m 0700 /root/SuperCraftOS/data/tiktoken-cache
sudo -u supercraftos env TIKTOKEN_CACHE_DIR=/root/SuperCraftOS/data/tiktoken-cache \
  /root/SuperCraftOS/.venv/bin/python -c \
  "import tiktoken; tiktoken.get_encoding('o200k_base')"
sudo install -o root -g supercraftos -m 0640 \
  /root/SuperCraftOS/.env.example /etc/supercraftos.env
sudoedit /etc/supercraftos.env
sudo docker pull python:3.12-slim
sudo install -m 0644 /root/SuperCraftOS/deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now supercraftos-worker.service supercraftos-app.service
sudo systemctl status supercraftos-worker.service supercraftos-app.service
```

Use literal values in `/etc/supercraftos.env`; systemd does not perform shell
variable expansion there. If that file already exists, preserve it instead of
overwriting it with the example. Likewise, reuse an existing service account.
For a custom `SUPERCRAFTOS_SANDBOX_IMAGE`, pull that exact image before starting;
job execution uses `--pull=never`. Pin a reviewed sandbox image digest for a
release. The core sandbox does not include arbitrary project dependencies.

The worker's `SupplementaryGroups=docker` assumes the standard Docker group and
system service. Docker group access grants control of the host daemon: the worker
is trusted infrastructure and belongs on a dedicated machine. Generated commands
run only in bounded job containers, with their workspace mounted, no external
network, and no Docker socket or provider credentials. The app service is not
added to the Docker group. For a nonstandard/rootless daemon, adapt the unit and
its connection environment explicitly.

Inspect service logs with `journalctl -u supercraftos-worker -u supercraftos-app`.
After changing credentials, restart both units. Before backing up the native
installation, stop both units and copy `/root/SuperCraftOS/data` together with
`/etc/supercraftos.env`. The systemd memory limit covers each service's processes;
Docker job containers have their own execution limits, so account for those
separately when sizing the host. The same SSH forwarding and update/rollback
procedures above apply.

## Optional private HTTPS gateway

The native `supercraftos-gateway.service` runs `private_gateway.py` on
`127.0.0.1:8790`, forwarding authenticated requests to `127.0.0.1:8787`.
This is a single-operator access key, not a multi-user account system. The service
does not provide TLS, register a domain, or configure public ingress. Use an
existing HTTPS endpoint or a TLS reverse proxy with a valid certificate.

Set these values in `/etc/supercraftos.env`, replacing the example origin with
your actual public origin:

```dotenv
SUPERCRAFTOS_PUBLIC_ORIGIN=https://agents.example.com
SUPERCRAFTOS_GATEWAY_PORT=8790
SUPERCRAFTOS_BACKEND_PORT=8787
```

The origin must be exact, including a nondefault public port if used, and have
no path, query, fragment or credentials. Keep the app unit's port and
`SUPERCRAFTOS_BACKEND_PORT` aligned. Configure your HTTPS ingress as follows:

| Setting | Required value |
| --- | --- |
| Upstream for every path | `http://127.0.0.1:8790` on this host |
| Forwarded `Host` | The original public host, including any explicit port |
| Forwarded `Origin` | Preserve the browser's value; do not rewrite it |
| Other request headers | Preserve `Cookie`, `Authorization`, `Content-Type`, `X-SuperCraftOS-Token`, `Idempotency-Key` |
| Response headers | Preserve `Set-Cookie`, `Cache-Control`, download headers |
| Request body limit | 64 KiB |
| Upstream read timeout | At least 195 seconds for existing synchronous operations |
| Shared caching | Disabled for all gateway responses |
| WebSocket | Unsupported; the gateway rejects upgrades |

Keep both loopback ports unreachable directly from the public network. The
gateway validates the public Host and browser Origin before rewriting the
backend's Host/Origin to its exact loopback address. A proxy that sends the
upstream IP as Host will receive `403 invalid_host`.

The native installation command above installs the gateway unit but does not
enable it. After configuring HTTPS ingress and the origin:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now supercraftos-gateway.service
sudo systemctl status supercraftos-gateway.service
sudo journalctl -u supercraftos-gateway.service --no-pager -n 30
```

On first start, the gateway creates `/root/SuperCraftOS/data/access.key` with mode
`0600`. Retrieve it through your private administrative session, then open
`https://agents.example.com/#<access-key>` or enter the key on the sign-in page.
Keep the key in the **fragment** after `#`, never in a query parameter, command
argument, application log or public bookmark. The sign-in page clears the
fragment and exchanges the key for a seven-day `Secure`, `HttpOnly`,
`SameSite=Strict` cookie. The original link remains reusable after cookie expiry
and service restarts. Anyone holding it has operator access.

Preserve `data/access.key` across updates and backups; the gateway holds its
value in memory until restarted. To deliberately revoke all links and sessions,
stop the gateway, replace that file with a fresh random key of at least 32
characters with the same owner/mode, and start it again. Clearing one browser's
cookie signs out only that browser. Native clients can use
`Authorization: Bearer <access-key>`; backend mutations also require the current
`X-SuperCraftOS-Token` obtained from authenticated `GET /api/session`.

Verify the public URL before sharing: anonymous `GET /api/status` must return
401; invalid keys and WebSocket upgrades must fail; cross-origin browser POSTs
must return 403. Use a fresh browser session to check login, authenticated task
views, repeated use of the full fragment link, and access after restarting the
gateway. These public TLS/browser checks are deployment prerequisites; local
Python tests do not establish that an external proxy is configured correctly.

## Optional components

- **CAD:** install `requirements-cad.lock` into `.cad-venv` using Python 3.12.
  Compatible native OpenCascade/VTK wheels and their OS shared libraries are
  required. The core image has neither those libraries nor the CAD environment.
  Run `.venv/bin/python .github/ci/offline_checks.py --with-cad` in an isolated test
  checkout after installation; this enables real STEP/STL/DXF generation. The
  installation-state contract also runs without CAD installed.
- **Local browser:** install `requirements-browser.txt` and the Camoufox browser
  binaries and OS dependencies separately. These optional requirements use ranges
  and are not a pinned browser release. Cloud SDKs do not install a local browser.
- **Rust worker:** install a Rust toolchain and run
  `cargo build --release --manifest-path agent-core/Cargo.toml` before using
  `main.py run --rust-core`. Rust builds are outside the Python-only CI job.
- **Agent brain:** the optional checkout is Git-ignored. Missing local skills must
  not be interpreted as installed; core behavior uses the bundled application.
- **iOS:** Swift sources require a separate Apple build/signing environment;
  Python CI does not compile or validate an iOS application.

### Verified model fallback routes

The primary route uses the explicit model environment settings or `data/llm_provider.json`. Optional `data/llm_fallbacks.json` is a JSON array of provider records with `status: "active"`, `model`, `key_env`, and `base_url`. Add a record only after a real completion succeeds. Supported verified pairs are NVIDIA_API_KEY with `https://integrate.api.nvidia.com/v1`, OPENCODE_GO_API_KEY with `https://opencode.ai/zen/go/v1`, and LLMGRID_API_KEY with `https://api.llmgrid.ai/v1`. Keys remain in the server environment, never these JSON files. Up to three available routes are tried for transport, authentication, rate-limit, and service errors. Invalid request errors do not silently change routes. A model catalog alone is not evidence of working inference.

NVIDIA agent actions and acceptance reviews request JSON output, which is also parsed and validated by the application. See [NVIDIA structured generation documentation](https://docs.nvidia.com/nim/large-language-models/1.14.0/structured-generation.html). Reusable playbooks and completed-task lessons are retrieval memory; the application does not train model weights. Action notes are concise public explanations, not private reasoning traces. `/api/agent/memory` exposes provenance and `/api/agent/memory/forget` removes a learned lesson with the normal mutation authentication.

### Daily backups and restore

Install `deploy/systemd/supercraftos-backup.{service,timer}` and enable the timer to create seven daily private archives under `/var/backups/supercraftos`. The service includes the server environment and uses SQLite's backup API for committed WAL data. Archives are mode 0600 in a 0700 directory and skip symlinks. Keep a separately protected off-host copy if disaster recovery is required; these local archives do not survive losing the host.

To restore, stop the app, worker and gateway, extract a selected trusted archive into an empty temporary directory, restore its `data/` to the configured state directory and its `supercraftos.env` to `/etc/supercraftos.env`, restore ownership to the service account and environment mode 0600, then start the services and verify a stored task and artifact. Retain the previous data directory until that verification succeeds. Preserve `data/access.key` to keep existing private links valid. Never publish these archives as application downloads.


## Consolidated VPS layout

The existing VPS uses one source checkout at `/root/SuperCraftOS`. Its `data`
symlink points to `/var/lib/supercraftos`, retaining the durable jobs, workspaces,
keys and iOS signing state. The systemd app, gateway and worker services run as
`supercraftos`, with `ProtectHome=tmpfs` and a read-only bind of the source
checkout. Their writable state remains outside the source tree. Keep `.env`
private to root; the service environment is `/etc/supercraftos.env`.

Only `127.0.0.1:8790` is used for public agent API and dashboard ingress. Set
`SUPERCRAFTOS_PUBLIC_ORIGIN=https://agent.commetai.ca` to match the gateway's
exact Host/Origin validation. Public iOS downloads are separate from private
agent routes. Do not expose backend port 8787 or rewrite public Host headers
to loopback at the external proxy.

The pre-consolidation source/configuration and WAL-aware data backups are
private under `/var/backups/supercraftos-consolidation`. They are rollback
archives, not alternate running checkouts. The deployed Git commit and the
Bitrise artifact's source commit are recorded separately; a server update does
not imply an iOS rebuild or a verified device installation.
