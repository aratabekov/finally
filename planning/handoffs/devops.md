# DevOps handoff — Docker, compose, start/stop scripts

## Files

| File | Purpose |
|---|---|
| `Dockerfile` | Multi-stage: `node:20-slim` builds the Next.js static export, `python:3.12-slim` runs FastAPI |
| `.dockerignore` | Keeps `node_modules`, `.venv`, `.next`, `out`, `__pycache__`, `.git`, `.env`, `db/*.db`, tests and docs out of the build context |
| `docker-compose.yml` | Convenience wrapper: build, `8000:8000`, `finally-data` volume, `--env-file .env`, healthcheck |
| `scripts/start_mac.sh` | Build if missing (`--build` forces), run container, print URL, open browser (`--no-open` skips) |
| `scripts/stop_mac.sh` | Stop + remove container, keep the volume |
| `scripts/start_windows.ps1` | PowerShell equivalent (`-Build`, `-NoOpen`) |
| `scripts/stop_windows.ps1` | PowerShell equivalent |

## Image layout

```
/app/backend/          # backend source (WORKDIR)
/app/backend/static/   # Next.js export, copied from stage 1 (/build/out)
/app/db/               # SQLite lives here — the volume mount target
/opt/venv/             # uv-managed virtualenv, on PATH
```

The venv is at `/opt/venv` (not `backend/.venv`) so `COPY backend/ ./` can never
clobber it. Dependencies install from `backend/uv.lock` via
`uv sync --locked --no-dev --no-install-project` in a layer before the source
copy, so code changes do not re-resolve dependencies.

`backend/db/connection.py` computes `DB_PATH` as `<parents[2]>/db/finally.db`.
With the backend at `/app/backend`, that resolves to `/app/db/finally.db` —
verified in a running container.

## Running

```bash
./scripts/start_mac.sh            # build if needed, run, open browser
./scripts/start_mac.sh --build    # force rebuild
./scripts/stop_mac.sh             # stop, keep data

docker compose up -d --build      # equivalent via compose
docker compose down
```

Both paths use the same named volume `finally-data`, so the database is shared
between them. `start_mac.sh` copies `.env.example` to `.env` if `.env` is
missing. Scripts are idempotent — re-running `start` removes and recreates the
container; re-running `stop` on an absent container is a no-op.

## Validation performed

Full `docker build` and runtime verification against the current tree:

- `docker build -t finally:latest .` — succeeds end to end (frontend export +
  `uv sync` from the lockfile).
- `/app/backend/static/index.html` present, 1.1 MB of export assets copied.
- `GET /api/health` returns `{"status":"ok"}`.
- `GET /api/stream/prices` streams `PriceTick` SSE frames.
- `/app/db/finally.db` created on the volume; survives container removal and
  recreation (verified by re-running `start_mac.sh` and via compose).
- `stop_mac.sh` keeps the volume; running it twice is safe.
- `bash -n` clean on both shell scripts; both are executable.
- `docker compose config` valid.

## Open item for the Backend API Engineer

`GET /` currently returns **404** in the container. The export is present at
`/app/backend/static/`, but `backend/main.py` does not mount it yet. Per
`planning/TEAM.md`, main.py should mount `backend/static/` when the directory
exists (absent during local dev). Once that lands, `/` will serve the SPA — no
Docker change needed.

## Not validated

- PowerShell scripts: no `pwsh` on this machine, so they were reviewed by hand
  rather than executed. They set `$PSNativeCommandUseErrorActionPreference =
  $false` so the `docker inspect` existence probes are not turned into
  terminating errors on PowerShell 7.4+. Needs a run on a Windows host.
- The image runs as root. Fine for a local single-user container and it avoids
  volume-permission friction; revisit if this is ever deployed publicly.
