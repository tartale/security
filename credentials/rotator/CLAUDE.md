# CLAUDE.md

Guidance for Claude Code working in this repo.

## What this project is

A personal CLI for rotating API keys/tokens (GitHub, GitHub Enterprise, RunPod, Modal,
Cloudflare, Jira Data Center, Bitwarden) and distributing them to Bitwarden and
`.env`/`.envrc` files. Read `README.md`, `docs/design.md`, and `docs/providers.md` first.

## Current state

Scaffolded: Python 3.11+ with typer, built from scratch (not on keyrotate). Source in
`src/rotator/`, tests in `tests/`. The `rotator` CLI owns dev steps: `rotator lint`,
`rotator test [pytest args]`. Dependencies are pinned by major only. Work is tracked in
GitHub issues; the roadmap in `README.md` maps to them.

## Hard rules (security)

- Never print, log, or echo a secret value. Redact in all output, errors, and audit logs.
- Never pass secrets as command-line arguments (they leak via process lists and shell
  history). Use stdin, masked prompts, or env vars of the child process only.
- Never commit real credentials, real token IDs, or real inventory files. Ship
  `inventory.example.yaml` only; gitignore the real inventory and any `.env*` files.
- Tests must use mocked HTTP and throwaway tokens. Never run tests against live
  production credentials.
- Order of operations is fixed: create -> verify -> write to store -> write to
  destinations -> post-verify -> revoke old. Do not revoke the old credential until
  every destination succeeded.
- Destructive or irreversible actions (revoke, overwrite) require a dry-run path and
  explicit confirmation by default.
- Assisted providers open console URLs in the system browser. Do not drive the user's
  browser or handle their passwords/cookies.

## Architecture conventions

- Provider adapter: `capability` (`auto` | `assisted`), `create`, `verify`, `revoke`,
  `console_url`.
- Destination adapter: `write`, `read_current` (for backup/rollback).
- Adapters are small, independent, and individually testable. One file per provider.
- Every adapter documents its source of truth (API docs URL) and a verification status
  in `docs/providers.md`.

## Working on providers

`docs/providers.md` marks each claim as **confirmed** (documented) or **unverified**.
Before implementing an adapter, check the provider's current docs and update the status.
Do not implement against an endpoint you could not confirm; open a question instead.

## Style

- Prefer small, boring, dependency-light code.
- Keep CLI output short and scannable; errors should say what to do next.
- Update docs in the same change as behavior.
