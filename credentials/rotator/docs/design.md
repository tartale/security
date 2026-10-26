# Design sketch

Everything here is a proposal to be challenged, not a spec.

## Core flow (per credential)

```
create -> verify -> store (Bitwarden) -> distribute (env/envrc) -> post-verify -> revoke old
```

- The old credential stays valid until every destination has succeeded.
- Any failure before `revoke` leaves the old credential working and reports which step
  failed. Destination adapters keep a backup (`read_current`) so a partial write can be
  rolled back.
- `revoke` is `auto` where the provider supports it, otherwise the tool opens the console
  page for the old credential and asks you to confirm when done.

## Modes

- `auto`: provider adapter implements `create` against an API (Cloudflare roll, Jira Data
  Center PAT create).
- `assisted`: provider adapter implements `console_url` instead. The tool opens it in the
  system browser, you create the credential, and paste it into a masked prompt (or the
  tool reads and then clears the clipboard). `verify` still runs before anything is
  written.

## Adapter interfaces (language-agnostic)

Provider adapter:

| Member | Purpose |
|---|---|
| `capability` | `auto` or `assisted` |
| `create(spec)` | Mint or roll a credential, return the new secret (auto only) |
| `console_url(spec)` | URL to open for creating or revoking (assisted; also revoke fallback) |
| `verify(secret)` | Cheap authenticated call proving the secret works |
| `revoke(spec)` | Revoke the old credential (auto) or prompt the user (assisted) |

Destination adapter:

| Member | Purpose |
|---|---|
| `read_current(target)` | Return current value or a backup handle for rollback |
| `write(target, secret)` | Write the new value |

Destinations in scope: `envfile` (covers `.env` and `.envrc`) and `bitwarden` (via the
`bw` CLI).

## Inventory

A YAML file listing every credential. The real file is gitignored; ship
`inventory.example.yaml`. Sketch:

```yaml
credentials:
  - id: cf-dns-edit
    provider: cloudflare
    mode: auto
    provider_ref: { token_id: "<token id>" }
    store: { type: bitwarden, item: "Cloudflare DNS token", field: password }
    destinations:
      - { type: envfile, path: ~/projects/site/.envrc, var: CLOUDFLARE_API_TOKEN }
    rotate_every_days: 90
    grace_days: 0
```

Per-credential fields to decide: cadence, grace period, who else consumes it, and a
free-text note for manual follow-ups (for example, "also set in CI").

## Safety design

- Secrets are never passed in argv, logged, or echoed. Redaction in all output and in the
  audit log.
- Input only via masked prompt, stdin, or clipboard (cleared after reading).
- `--dry-run` shows the plan (which steps would run, which files would change) without
  creating or writing anything.
- Confirmation required for revoke and overwrite by default.
- Audit log records credential id, provider, timestamp, steps and outcomes, never values.
- Tests use mocked HTTP and throwaway tokens only.

## Bitwarden handling

- Used as the central store and as a provider.
- Automation login uses the personal API key (`bw login --apikey`) then `bw unlock`.
- Rotating Bitwarden's own API key breaks the tool's login, so it is last and manual:
  rotate in the web UI, then update the tool's own configuration.

## Open questions

- How to bootstrap and rotate the credential the tool itself uses per provider (for
  example, the Cloudflare token with "API Tokens Write").
- Whether a Jira REST delete endpoint exists for PATs.
- Whether GitHub gets a browser-automation adapter.
- Where tool-owned bootstrap secrets live (OS keychain vs Bitwarden vs env).
