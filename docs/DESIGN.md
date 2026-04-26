# steam-library-monitor Project Plan

## Goal

Build `steam-library-monitor`, a Dockerized Python service that monitors one or more public Steam libraries, detects newly added games and DLC, stores snapshots in SQLite, and sends Gmail SMTP email digests.

Primary use case: track when a configured Steam account adds games that may be available through Steam Family Sharing.

Important limitation: Steam does not expose a clean public “Family Sharing supported” flag through the Web API. The monitor should report newly detected library additions and treat shareability as a best-effort note, not a guaranteed assertion.

## Repository Name

`steam-library-monitor`

## License

Use the MIT License.

No compelling reason to choose a more restrictive license: the project is a small utility, likely useful to others, and does not require copyleft or special patent language.

## Runtime Model

The service should run continuously in Docker:

1. Start container.
2. Load configuration from environment variables.
3. Ensure the SQLite database exists and migrations are applied.
4. Query all configured Steam users immediately at startup.
5. Compare current library contents to prior database state.
6. Send notification email if new items are detected.
7. Sleep for `SLEEP_INTERVAL` seconds.
8. Repeat forever.

`SLEEP_INTERVAL` defaults to `86400` seconds, i.e. 24 hours.

## Configuration

All production configuration should be supplied via Docker Compose environment variables.

Required:

```yaml
STEAM_API_KEY: "..."
STEAM_USERS: "7656119xxxxxxxxxx=Display Name,7656119yyyyyyyyyyy=Other Name"
SMTP_USERNAME: "sender@gmail.com"
SMTP_PASSWORD: "app-password"
SMTP_TO: "recipient@example.com"
```

Optional:

```yaml
SLEEP_INTERVAL: "86400"
LOG_LEVEL: "WARNING"
DATABASE_PATH: "/data/library-cache.db"
SMTP_FROM: "Steam Library Monitor <sender@gmail.com>"
SMTP_HOST: "smtp.gmail.com"
SMTP_PORT: "587"
```

### Steam users format

Use a simple comma-separated assignment format:

```text
STEAM_USERS="76561198000000001=Alice,76561198000000002=Bob"
```

Rules:

- Left side is SteamID64 and is used for API queries.
- Right side is display name and is used in email output and normal logs.
- Debug logs may include API URLs or SteamID64 values when useful.

Future enhancement: support JSON config for easier escaping and richer account metadata.

## Docker / TrueNAS Deployment

The SQLite database must be host-mounted from:

```text
/mnt/myzmirror/steam/library-cache.db
```

Inside the container, mount the parent directory as `/data`:

```yaml
services:
  steam-library-monitor:
    image: ghcr.io/jasmeralia/steam-library-monitor:latest
    container_name: steam-library-monitor
    restart: unless-stopped
    environment:
      STEAM_API_KEY: "your-steam-api-key"
      STEAM_USERS: "7656119xxxxxxxxxx=Roommate"
      SMTP_USERNAME: "your-gmail@gmail.com"
      SMTP_PASSWORD: "your-gmail-app-password"
      SMTP_TO: "you@example.com"
      SLEEP_INTERVAL: "86400"
      LOG_LEVEL: "WARNING"
      DATABASE_PATH: "/data/library-cache.db"
    volumes:
      - /mnt/myzmirror/steam:/data
```

The app should create `/data/library-cache.db` if it does not already exist.

## Steam API Usage

### Resolve account IDs

README should document two ways to find SteamID64:

1. If the user has a vanity profile URL, use Steam’s `ResolveVanityURL` endpoint:

```text
https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?key=YOUR_KEY&vanityurl=epeternally
```

2. Or use a Steam ID lookup site such as SteamID.io.

### Get owned games

Use:

```text
https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key=KEY&steamid=STEAMID64&include_appinfo=true&include_played_free_games=true
```

This provides app IDs and names for visible owned games.

Requirements:

- The target Steam profile must be public.
- The target account’s Game Details privacy setting must be public.

## DLC / Game Classification

`GetOwnedGames` alone does not reliably identify whether an app is a game or DLC.

For new app IDs, call Steam Store app details:

```text
https://store.steampowered.com/api/appdetails?appids=APPID
```

Use the returned `data.type` when available:

- `game` -> group under Games.
- `dlc` -> group under DLC.
- Other values may be ignored by default or logged at debug level.

For DLC, also capture the base game when available from Store metadata. Possible fields to inspect:

- `fullgame.appid`
- `fullgame.name`

If the base game title cannot be found, output “Base game unknown” rather than failing.

## Email Notification Format

Send one digest per polling cycle if any account has new games or DLC.

Subject example:

```text
Steam Library Monitor: 4 new item(s)
```

Body example:

```text
Steam Library Monitor found new library additions.

## Roommate

Games:
- Baldur's Gate 3
  https://store.steampowered.com/app/1086940/

DLC:
- Example DLC
  https://store.steampowered.com/app/123456/
  Base game: Example Base Game
```

Requirements:

- Include a clear header for each configured account involved.
- Use display names in output.
- Group games and DLC separately under the account header.
- Each bullet must include title and Steam store URL.
- DLC bullets must reference the base game title when available.
- Do not send an email when there are no new tracked additions.

## Logging

Use Python’s standard `logging` module.

Default:

```text
LOG_LEVEL=WARNING
```

Supported levels:

- DEBUG
- INFO
- WARNING
- ERROR
- CRITICAL

Logging expectations:

- WARNING default should stay quiet during normal operation.
- INFO should report startup, configured users count, poll start/end, new item counts, and email-send success.
- DEBUG should include API request URLs, raw app IDs, classification decisions, database change details, and sleep timing.
- ERROR should include exceptions with tracebacks where appropriate.

Avoid logging sensitive values:

- Never log `STEAM_API_KEY`.
- Never log `SMTP_PASSWORD`.
- If logging URLs, redact `key=` values.

## SQLite Schema

Use SQLite directly or SQLAlchemy. For a small service, direct `sqlite3` is acceptable.

Recommended tables:

```sql
CREATE TABLE IF NOT EXISTS accounts (
    steam_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS apps (
    app_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    app_type TEXT,
    store_url TEXT NOT NULL,
    base_app_id INTEGER,
    base_title TEXT,
    raw_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account_apps (
    steam_id TEXT NOT NULL,
    app_id INTEGER NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    PRIMARY KEY (steam_id, app_id),
    FOREIGN KEY (steam_id) REFERENCES accounts(steam_id),
    FOREIGN KEY (app_id) REFERENCES apps(app_id)
);

CREATE TABLE IF NOT EXISTS poll_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    message TEXT
);
```

Behavior:

- On first run, populate the current library as baseline and do not send a huge email unless `NOTIFY_ON_INITIAL_SYNC=true` is later added.
- On subsequent runs, only notify for newly discovered `(steam_id, app_id)` rows.
- Keep `last_seen_at` updated for existing rows.

## Python Package Structure

Suggested layout:

```text
steam-library-monitor/
├── .github/
│   └── workflows/
│       └── docker-publish.yml
├── src/
│   └── steam_library_monitor/
│       ├── __init__.py
│       ├── __main__.py
│       ├── app.py
│       ├── config.py
│       ├── db.py
│       ├── emailer.py
│       ├── logging_config.py
│       ├── models.py
│       └── steam.py
├── tests/
│   ├── test_config.py
│   ├── test_db.py
│   ├── test_emailer.py
│   └── test_steam.py
├── AGENTS.md
├── CLAUDE.md
├── Dockerfile
├── LICENSE
├── Makefile
├── README.md
├── docker-compose.example.yml
├── mypy.ini
├── pyproject.toml
├── pylint.toml
└── requirements.txt
```

## Dependency Plan

Runtime dependencies:

- `requests` for HTTP
- Optional: `pydantic` or `pydantic-settings` for config validation

Dev/test dependencies in `requirements.txt` or split files:

- `pytest`
- `ruff`
- `mypy`
- `pylint`
- `types-requests`

For simplicity, a single `requirements.txt` is acceptable for the initial project.

## Makefile Requirements

Required targets:

```makefile
.PHONY: install lintfix lint test

.venv/bin/python:
	python3 -m venv .venv

install: .venv/bin/python
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -r requirements.txt

lintfix: install
	.venv/bin/ruff check --fix src tests
	.venv/bin/ruff format src tests

lint: install
	.venv/bin/ruff check src tests
	.venv/bin/ruff format --check src tests
	.venv/bin/mypy src tests
	.venv/bin/pylint src tests
	hadolint Dockerfile

test: install
	.venv/bin/pytest
```

Important workflow instruction:

- For code changes, run `make lintfix && make lint && make test` before considering the change complete.
- Agents should not run `ruff`, `mypy`, `pylint`, or `pytest` directly as the first step. Use the Makefile.

## Dockerfile Requirements

Use a slim Python base image, such as:

```dockerfile
FROM python:3.12-slim
```

Requirements:

- Install runtime requirements.
- Copy source code.
- Use a non-root user.
- Set `PYTHONUNBUFFERED=1`.
- Default command should run the module:

```dockerfile
CMD ["python", "-m", "steam_library_monitor"]
```

## GitHub Actions / GHCR Publishing

Workflow file:

```text
.github/workflows/docker-publish.yml
```

Triggers:

```yaml
on:
  push:
    branches:
      - main
    tags:
      - "v*"
  workflow_dispatch:
```

Use Node 24-compatible action versions:

- `actions/checkout@v5`
- `actions/setup-python@v6`
- `docker/login-action@v4`
- `docker/setup-buildx-action@v4`
- `docker/build-push-action@v7`

The repository should build and push to:

```text
ghcr.io/jasmeralia/steam-library-monitor
```

Tagging behavior:

- Push to `main` -> `latest`
- Push tag `v1.0.0` -> Docker tag `1.0.0`
- Manual workflow dispatch -> allow any branch/tag ref, tag output as `manual-<short-sha>` unless the ref is a `v*` tag

Required permissions:

```yaml
permissions:
  contents: read
  packages: write
```

Before Docker build, run:

```bash
make lint
make test
```

The workflow can skip `make lintfix` because CI should verify formatting, not mutate code.

## README.md Requirements

README should include:

1. Project purpose.
2. Family Sharing limitation: Steam does not expose a reliable public family-sharing eligibility flag.
3. How to get a Steam Web API key:
   - Go to the Steam Web API key page.
   - Register a domain value if prompted; for personal use, a placeholder domain is commonly used, but the user should follow Steam’s instructions.
4. How to find SteamID64:
   - Resolve vanity URL using `ResolveVanityURL`.
   - Or use SteamID.io.
5. Docker Compose example for TrueNAS.
6. Required Gmail app password setup:
   - Enable 2-Step Verification.
   - Create an app password for mail.
   - Use that app password as `GMAIL_APP_PASSWORD`.
7. Environment variable reference.
8. Development commands:
   - `make install`
   - `make lintfix`
   - `make lint`
   - `make test`
9. GHCR image usage.
10. Troubleshooting:
   - Empty library likely means private Steam game details.
   - No email likely means no new items after baseline sync.
   - Gmail auth failures usually mean app password or 2FA setup issue.

## AGENTS.md Requirements

AGENTS.md should define project rules for coding agents:

- This is a Dockerized Python service.
- Use `src/steam_library_monitor` for application code.
- Use `tests/` for tests.
- Do not hardcode secrets.
- Do not log Steam API keys or Gmail app passwords.
- Use the Makefile as the single command interface.
- After code changes, run:

```bash
make lintfix && make lint && make test
```

- Do not run individual tools directly as the initial validation path.
- Keep README and Compose examples updated when config changes.
- Preserve SQLite schema compatibility; add migrations carefully.

## CLAUDE.md Requirements

Keep this intentionally short:

```markdown
# Claude Instructions

Read `AGENTS.md` first and follow it as the authoritative project guidance.
```

## Testing Plan

Tests should cover:

### Config parsing

- Valid `STEAM_USERS` with one user.
- Valid `STEAM_USERS` with multiple users.
- Invalid missing `STEAM_API_KEY`.
- Invalid malformed `STEAM_USERS`.
- Default `SLEEP_INTERVAL=86400`.
- Default `LOG_LEVEL=WARNING`.

### Steam client

- Builds correct owned-games request.
- Redacts API key in debug URL logging.
- Parses owned games response.
- Parses appdetails game response.
- Parses appdetails DLC response with base game.
- Handles missing appdetails data gracefully.

### Database

- Creates schema on empty DB.
- First sync inserts baseline without notification.
- Second sync with no changes emits no new items.
- Second sync with new app emits new item.
- Tracks per-account app additions separately.

### Email

- Groups by account display name.
- Groups Games and DLC separately.
- Includes Steam store URLs.
- Includes base game title for DLC.
- Does not send when there are no new items.

## Implementation Milestones

### Milestone 1: Skeleton

- Create repo structure.
- Add MIT license.
- Add README stub.
- Add AGENTS.md and CLAUDE.md.
- Add Makefile.
- Add requirements and lint configs.
- Add Dockerfile.
- Add docker-compose.example.yml.

### Milestone 2: Core config/logging/database

- Implement config parser.
- Implement logging setup.
- Implement SQLite schema initialization.
- Add unit tests.

### Milestone 3: Steam client

- Implement owned-games query.
- Implement appdetails query.
- Implement app classification.
- Add tests using mocked HTTP responses.

### Milestone 4: Diffing and persistence

- Implement poll cycle.
- Implement baseline sync behavior.
- Implement per-account diffing.
- Add tests using temporary SQLite database.

### Milestone 5: Email notifications

- Implement email body rendering.
- Implement Gmail SMTP sending.
- Add tests for message generation.
- Keep SMTP send itself integration-light or mocked.

### Milestone 6: Container and CI

- Finalize Dockerfile.
- Add GitHub Action for lint/test/build/push.
- Confirm image tags:
  - `latest` for main
  - stripped semantic version for `v*` tags

### Milestone 7: Documentation polish

- Expand README with setup steps.
- Add troubleshooting.
- Add privacy/family-sharing caveat.

## Open Questions / Future Enhancements

These should not block the first implementation:

- Add `NOTIFY_ON_INITIAL_SYNC=true|false` option.
- Add HTML email in addition to plain text.
- Add support for multiple recipients.
- Add Discord/webhook notification support.
- Add JSON/YAML config file support instead of only env vars.
- Add heuristic warning for games likely excluded from Family Sharing.
- Add Prometheus metrics or healthcheck endpoint.
- Add database migration helper if schema changes become frequent.
