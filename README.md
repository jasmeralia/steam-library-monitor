# steam-library-monitor

`steam-library-monitor` is a Dockerized Python service that monitors one or more public Steam libraries, stores snapshots in SQLite, and sends Gmail SMTP digests when new games or DLC appear.

The main use case is noticing additions that may be available through Steam Family Sharing. Steam does not expose a reliable public family-sharing eligibility flag, so this service reports newly detected library additions and treats shareability as a best-effort inference.

## Quick Start

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

The app creates `/data/library-cache.db` if it does not already exist. The first poll for each account creates a baseline and does not send a large initial email.

The container runs as a non-root system user. The host directory bound to `/data` must be writable by the container process. If the service fails to create the database, ensure the host directory is owned by or writable by the container's UID, or add a `user: "UID:GID"` line to the Compose service to match the host directory's owner.

## Steam Setup

Get a Steam Web API key from the [Steam Web API key page](https://steamcommunity.com/dev/apikey). If Steam prompts for a domain, follow Steam's instructions; personal deployments often use a placeholder domain.

Find each account's SteamID64 in one of two ways:

- For vanity profile URLs, call `ResolveVanityURL`:

```text
https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?key=YOUR_KEY&vanityurl=steamusername
```

- Or use a lookup site such as SteamID.io.

The target Steam profile must be public, and the account's Game Details privacy setting must be public.

## SMTP Setup

For Gmail, use an app password rather than your account password:

1. Enable 2-Step Verification on the account.
2. Create an app password for mail.
3. Set that app password as `SMTP_PASSWORD`.

## Environment

Required:

```text
STEAM_API_KEY
STEAM_USERS
SMTP_USERNAME
SMTP_PASSWORD
SMTP_TO
```

`STEAM_USERS` uses comma-separated `SteamID64=Display Name` entries:

```text
STEAM_USERS="76561198000000001=Alice,76561198000000002=Bob"
```

Optional:

```text
SLEEP_INTERVAL=86400
LOG_LEVEL=WARNING
DATABASE_PATH=/data/library-cache.db
SMTP_FROM="Steam Library Monitor <sender@gmail.com>"
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
APPDETAILS_DELAY=1.5
```

`APPDETAILS_DELAY` controls the pause in seconds between consecutive Steam Store API calls when classifying new apps. Apps with a definitive non-game type (e.g. `advertising`, `tool`) are cached so they are not re-fetched on subsequent scans. Apps where the Store API returns no data (`app_type` unknown) are not cached and will be retried each scan. The default of 1.5 seconds keeps the service within Steam's undocumented rate limits. Reduce it only if you have confirmed headroom; set it to 0 to disable the delay entirely.

## Development

```bash
make install
make lintfix
make lint
make test
make build
```

For code changes, run:

```bash
make lintfix && make lint && make test
```

For Dockerfile changes or local image verification, run:

```bash
make build
```

`make build` depends on `make lint` and builds `steam-library-monitor:local` by default. Override the image tag with:

```bash
make build IMAGE=ghcr.io/jasmeralia/steam-library-monitor:dev
```

## GHCR Image

The expected image is:

```text
ghcr.io/jasmeralia/steam-library-monitor:latest
```

Tags pushed as `v1.0.0` publish Docker tag `1.0.0`.

## Troubleshooting

- Empty library results usually mean the Steam profile or Game Details privacy setting is private.
- No email after startup is expected when the first run only creates the baseline.
- Gmail authentication failures usually mean 2-Step Verification or the app password is not configured correctly.

## Using a .env file

Rather than embedding credentials in your `docker-compose.yml`, you can store them in a `.env` file and bind-mount it into the container:

```bash
cp .env.example .env
# edit .env with your values
```

```yaml
services:
  app:
    image: ghcr.io/jasmeralia/steam-library-monitor:latest
    volumes:
      - /path/to/your/.env:/app/.env:ro
```

The app loads `/app/.env` automatically on startup. Any value in `.env` can still be overridden by an explicit `environment:` entry in your Compose file.