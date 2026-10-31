# Design sketch

Everything here is a proposal to be challenged, not a spec.

## Core flow (per credential)

```
create -> verify -> store (Bitwarden) -> distribute (env/envrc) -> post-verify -> revoke old
```

- The old credential stays valid until every destination has succeeded.
- Exception: providers that roll in place (`rolls_in_place`, e.g. Cloudflare) invalidate the
  old secret at `create`, so there is no fallback and no `revoke` step. The flow engine must
  write the store first, retry failed writes, and keep the new secret in memory until every
  destination has it or the user decides.
- Any failure before `revoke` leaves the old credential working and reports which step
  failed. Destination adapters keep a backup (`read_current`) so a partial write can be
  rolled back.
- `revoke` is `auto` where the provider supports it, otherwise the tool opens the console
  page for the old credential and asks you to confirm when done.

## Running a rotation

`credentials rotate ID [--dry-run] [--yes]` (`src/rotator/flow.py`):

1. Confirm the overwrite (`--yes` answers this one question; manual-step acknowledgements are
   never auto-answered).
2. Obtain the secret: `create()` for `auto`, or open `console_url()` and read a hidden prompt
   for `assisted`.
3. `verify`, then read a backup from every target (the store first, then each destination).
4. Write every target. If one fails, restore the ones already written and stop; the old
   credential is never revoked on failure. For providers that roll in place there is nothing
   to restore to, so a failed write is retried (with confirmation) until every target has the
   new value or the user declines, and the error lists what was not written.
5. `verify` again, then open `revoke_url()` and ask the user to confirm the old credential is
   revoked. Exit 0 = done, 1 = failed, 2 = rotated but the old credential is still active.

The inventory `mode` must equal the adapter's capability.

## Modes

- `auto`: provider adapter implements `create` against an API (Cloudflare roll, Jira Data
  Center PAT create).
- `assisted`: provider adapter implements `console_url` instead. The tool opens it in the
  system browser, you create the credential, and paste it into a masked prompt. `verify`
  still runs before anything is written.

## Adapter interfaces (language-agnostic)

Provider adapter:

| Member | Purpose |
|---|---|
| `capability` | `auto` or `assisted` |
| `rolls_in_place` | Creating the new secret invalidates the old one (Cloudflare) |
| `create()` | Mint or roll a credential, return the new secret (auto only) |
| `console_url()` | Page to open so the user creates the credential (assisted only) |
| `verify(secret)` | Cheap authenticated call proving the secret works |
| `revoke_url()` | Console page where the old credential is revoked; none if nothing to revoke |

Revoking is always a console step the user confirms; no adapter calls a revoke API.

Provider adapters live in `src/rotator/providers/`; `for_credential` builds one from an
inventory entry plus the environment (manager tokens come from env vars named in
`provider_ref`, never from the inventory file).

Destination adapter:

| Member | Purpose |
|---|---|
| `read_current()` | Return a backup handle (held in memory, hidden from `repr`) for rollback |
| `write(secret)` | Write the new value |
| `restore(backup)` | Put the backed-up state back |

Adapters live in `src/rotator/destinations/`, built from inventory entries by
`for_destination` / `for_store`.

- `envfile`: replaces every `VAR=` / `export VAR=` line, appends if absent (with `export` only
  for `*.envrc`), keeps other lines and the file mode (new files are `0600`), writes atomically,
  follows symlinks. Values that cannot be quoted safely (empty, or containing a quote or
  newline) are rejected without echoing them.
- `bitwarden`: `bw get item <name>` then `bw edit item <id>` with the base64 JSON on stdin, so
  the secret never reaches argv. Needs `bw` on `PATH` and a session: `BW_SESSION` from the
  environment, or `ensure_session` unlocks with a hidden master-password prompt (`bw status`,
  then `bw unlock --passwordenv ... --raw` with the password only in the child's environment).
  The tool never logs in; run `bw login --apikey` once.
  `password` writes `login.password`; any other `field` is a custom hidden field.

Destinations in scope: `envfile` (covers `.env` and `.envrc`) and `bitwarden` (via the
`bw` CLI).

## Inventory

One YAML file, `credentials/credentials.yaml`, holds the providers and every credential. The real
file is gitignored; ship `inventory.example.yaml`. `./security credentials --init` builds it
interactively (`src/rotator/wizard.py`). Sketch:

```yaml
providers:                # optional; shared settings, referenced by id
  - { id: cloudflare, type: cloudflare, settings: { manager_token_env: CLOUDFLARE_ROTATOR_TOKEN } }
credentials:
  - id: cf-dns-edit
    provider: cloudflare   # a provider id or a provider type
    mode: auto
    provider_ref: { token_id: "<token id>" }
    store: { type: bitwarden, item: "Cloudflare DNS token", field: password }
    destinations:
      - { type: envfile, path: ~/projects/site/.envrc, var: CLOUDFLARE_API_TOKEN }
    rotate_every_days: 90
    grace_days: 0
```

A credential naming a provider id takes the provider's type and merges its `settings` under the
credential's own `provider_ref`. `credentials rotate --check` validates the file (unknown fields are rejected so a stray secret value or typo
fails loudly). Optional per-credential fields: `kind`, `grace_days` (default 0), `notes`;
`store.field` defaults to `password`; `last_rotated` (a date) seeds `rotate --due` for
credentials rotated before the tool existed.

Per-credential fields to decide: cadence, grace period, who else consumes it, and a
free-text note for manual follow-ups (for example, "also set in CI").

## Safety design

- Secrets are never passed in argv, logged, or echoed. Redaction in all output and in the
  audit log.
- Input only via masked prompt or the environment.
- `--dry-run` shows the plan (which steps would run, which files would change) without
  creating or writing anything.
- Confirmation required for revoke and overwrite by default.
- Audit log (`audit.log`, JSON lines, mode `0600`, next to the inventory) records credential id,
  provider, timestamp, steps and outcomes, never values. A `rotated` entry marks a completed
  rotation and drives `rotate --due`.
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
