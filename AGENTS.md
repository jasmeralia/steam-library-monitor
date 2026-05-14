# Agent Instructions

This is a Dockerized Python service.

- Use `src/steam_library_monitor` for application code.
- Use `tests/` for tests.
- Do not hardcode secrets.
- Do not log Steam API keys or Gmail app passwords.
- Use the Makefile as the single command interface.
- After code changes, run:

```bash
make lintfix && make lint && make test
```

- If `Dockerfile` is updated, also run:

```bash
make build
```

- Do not run individual tools directly as the initial validation path.
- Keep README and Compose examples updated when config changes.
- Preserve SQLite schema compatibility; add migrations carefully.

## Git Workflow

- Never push commits directly to `master`. Always open a pull request from a feature/fix branch.
- Use squash merge strategy when merging pull requests.
