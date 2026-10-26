# credential-rotator (working title)

A personal tool for rotating API keys and tokens across a fixed set of providers, then
distributing the new values to a password manager and to local env files.

**Status:** scaffolded (Python + typer); adapters not yet implemented.

## Goal

One command per credential (or one for everything due) that:

1. Obtains a new credential from the provider (fully automatic where an API exists,
   *assisted* where it does not).
2. Verifies the new credential works before touching anything else.
3. Saves it to the central store (Bitwarden).
4. Updates every configured destination (`.env` / `.envrc` files).
5. Revokes the old credential (or prompts you to), and writes an audit log entry.

## Why build this

No free tool covers the whole chain for this provider set. Closest prior art:
[keyrotate](https://github.com/Prompto-Studio/keyrotate) (alpha, MIT; handles
1Password/GitHub/Supabase destinations, but auto-rotation only for Resend and PostHog),
Infisical (MIT core; rotation is plan-gated and aimed at DB/cloud credentials), and
OpenBao (free; dynamic secrets for AWS/DBs, heavy to operate). See
[docs/prior-art.md](docs/prior-art.md). Reusing keyrotate's adapter model, or
contributing adapters upstream, is an open option.

## Initial scope

**Providers:** GitHub (fine-grained and classic PATs), GitHub Enterprise, RunPod, Modal,
Cloudflare, Jira Enterprise (Data Center), Bitwarden.

**Destinations:** `.env` / `.envrc` files, Bitwarden.

## Two tiers

| Mode | Meaning | Providers (current understanding) |
|---|---|---|
| `auto` | Provider has an API to mint or roll a credential; tool does everything | Cloudflare, Jira Data Center |
| `assisted` | No create API; tool opens the console page, you paste the new secret, tool does the rest | GitHub (all), RunPod, Modal, Bitwarden |

Details and verification status per provider: [docs/providers.md](docs/providers.md).

## Key design ideas

- **Inventory file** lists every credential: provider, mode, where it is stored, where it
  is distributed. See [docs/design.md](docs/design.md).
- **Adapters**: provider adapters (`create`, `verify`, `revoke`, `console_url`) and
  destination adapters (`write`, `read_current`).
- **Verify before write; store before distribute; revoke last.** The old credential
  stays valid until every destination has succeeded.
- **Pre-opened console URLs** for assisted providers, opened in the system browser so the
  tool never touches your sessions or passwords.
- **Secrets never appear in argv, logs, or shell history.** Masked prompt or clipboard
  input only.

## Roadmap

1. Inventory schema + loader.
2. Destination adapters: envfile/envrc, Bitwarden (via `bw` CLI). (done)
3. Cloudflare adapter (auto, via roll endpoint).
4. Jira Data Center adapter (auto create; revoke path to confirm).
5. Assisted flow engine + GitHub / RunPod / Modal adapters.
6. Bitwarden self-rotation (last, manual step).
7. Audit log, dry-run mode, due-date reporting.

## Development

Run from the repo root (the launcher sets up the venv on first use):

```
./security credentials rotator lint
./security credentials rotator test
./security credentials rotator check --inventory inventory.yaml   # validate the inventory
```

## Open decisions

- Whether GitHub gets a browser-automation adapter later (brittle; needs a logged-in Chrome).
- Rotation cadence and grace periods per credential.
