# Repository Guidelines

## Project Structure & Module Organization

This repository is the deployment package for Smart Eval, not the primary application source tree. Root-level files define the container and operator workflow: `docker-compose.yml`, `Dockerfile`, `.env.example`, and the maintenance scripts (`start.sh`, `stop.sh`, `update.sh`, and `backup.sh`). User-facing documentation lives in `README.md`, `QUICKSTART.md`, `CHANGELOG.md`, and `RELEASE_CHECKLIST.md`. Screenshots used by the documentation are stored in `images/`. Runtime state belongs in ignored directories such as `data/`, `logs/`, `tmp/`, and `backups/`; never commit their contents.

## Build, Test, and Development Commands

- `cp .env.example .env` — create a local configuration file; replace placeholders before starting.
- `./start.sh` — validate required settings, pull `zxwei/knowflow-eval:latest`, start Compose, and poll `/health`.
- `docker-compose logs -f` — follow service logs during troubleshooting.
- `./stop.sh` — stop and remove the Compose services without deleting persisted data.
- `./update.sh` — back up local state, pull the latest image, and restart.
- `./backup.sh` — archive `.env`, data, reports, and logs under `backups/`.
- `./check-before-publish.sh` — check required files, executable bits, configuration, and likely secret leakage.

The checked-in `Dockerfile` expects `backend/` and `frontend/` source directories. Build it only from a source-enabled checkout; normal contributors should validate the prebuilt-image workflow.

## Coding Style & Naming Conventions

Follow `.editorconfig`: UTF-8, LF endings, spaces, and four-space indentation. Preserve nearby formatting in YAML and Markdown rather than reformatting unrelated lines. Shell scripts should use Bash, `set -e`, quoted variables, `UPPER_SNAKE_CASE` environment names, and `snake_case` helper functions. Name new scripts descriptively, for example `verify-release.sh`.

## Testing Guidelines

There is no automated unit-test or coverage suite in this deployment repository. Before opening a PR, run:

```bash
bash -n *.sh
docker-compose config
./check-before-publish.sh
```

For runtime changes, also run `./start.sh`, confirm `curl -f http://localhost:5003/health`, inspect logs, and finish with `./stop.sh`. Document any checks you could not run.

## Commit & Pull Request Guidelines

Recent commits use short conventional prefixes such as `chore:`. Prefer imperative subjects such as `docs: clarify RAGFlow setup` or `fix: preserve backup failures`. Keep PRs focused on documentation, deployment configuration, scripts, or examples. Include a concise summary, linked issue when applicable, commands and results used for validation, and screenshots when changing documented UI flows. Never include real API keys, `.env`, private endpoints, or generated runtime data.
