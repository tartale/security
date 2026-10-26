# Provider capabilities

Research snapshot from 2026-10-25. Status key: **confirmed** = found in provider docs or
an API reference; **unverified** = inferred, second-hand, or not found. Re-check before
implementing.

## Summary

| Provider | Mode | Create new | Revoke old |
|---|---|---|---|
| Cloudflare | auto | API roll (confirmed) | implicit in roll (confirmed) |
| Jira Data Center | auto | REST create (confirmed; response field unverified) | UI/admin confirmed; REST delete unverified |
| GitHub fine-grained PAT | assisted | UI only (no API, per community thread + tooling) | UI |
| GitHub classic PAT | assisted | UI only (unverified beyond docs showing UI flow) | UI |
| GitHub Enterprise Server | assisted | UI flow documented (confirmed); API absence unverified | UI |
| RunPod | assisted | Console only per docs (undocumented GraphQL unverified) | Console |
| Modal | assisted | Dashboard or `modal token new` browser flow (API unverified); two-part token, not implemented yet | Dashboard |
| Bitwarden | assisted | Rotate button in web app; CLI/API not found | n/a (rotation invalidates old) |

## Cloudflare (auto)

- Roll: `PUT https://api.cloudflare.com/client/v4/user/tokens/{token_id}/value`. Returns the
  new token value in `result`. Same token ID, new secret. Requires the "API Tokens Write"
  permission on the calling token. (confirmed, Cloudflare API reference)
- Account-owned tokens: `PUT /accounts/{account_id}/tokens/{token_id}/value`, requires
  "Account API Tokens Write". (confirmed, Cloudflare API reference)
- Rolling invalidates the previous value ("Rolling your API token into a new one will
  invalidate the previous token"); timing and any grace period are not documented. The old
  secret cannot be kept as a fallback, so the new secret must be stored before anything else.
  (confirmed)
- Verify: `GET /user/tokens/verify` or `GET /accounts/{account_id}/tokens/verify` with the new
  token; success is `result.status == "active"`. (confirmed, Cloudflare API reference)
- Adapter: `provider_ref` takes `token_id` (required), `account_id` (selects the account
  endpoints), and `manager_token_env` (env var holding the calling token, default
  `CLOUDFLARE_ROTATOR_TOKEN`). The adapter also checks that `result.id` equals `token_id`.
- Open question: bootstrap/rotation of the token that has "API Tokens Write".
- Console fallback: dashboard > profile > API Tokens (URL unverified, not used by the adapter).

Docs: https://developers.cloudflare.com/api/operations/user-api-tokens-roll-token

## Jira Enterprise = Data Center (auto create)

- Create: `POST {base_url}/rest/pat/latest/tokens`, body `{"name": "...",
  "expirationDuration": 90}` (days). Authenticate as the owning user (basic auth or an
  existing PAT as bearer). You cannot create a PAT on behalf of another user. (confirmed)
- Available from Jira Core/Software 8.14 and Service Management 4.15. PATs are not
  scopeable in Data Center. (confirmed)
- Verify: `GET {base_url}/rest/api/2/myself` with the new PAT as bearer. (confirmed, Jira
  Server REST reference)
- Create response body is not documented; the adapter reads the token from `rawToken`, a
  field name taken from an Atlassian developer-community answer. (unverified; the adapter
  fails with a clear error if it is absent)
- Limits: `atlassian.pats.max.tokens.per.user` (default 10), `atlassian.pats.max.tokens.expiry.days`
  (default 365). (confirmed)
- Revoke: Profile > Personal Access Tokens, or admin screen (System > Administering
  personal access tokens). No REST delete in Atlassian's PAT docs; a feature request
  (JRASERVER-78824) suggests none exists for other users. The adapter does not revoke;
  revoking the old PAT is an assisted console step. (REST delete: unverified)
- Adapter: `provider_ref` takes `base_url` (required), `token_name` (default: credential id),
  `expiration_days` (default: `rotate_every_days + grace_days + 14`; must fit the instance
  maximum), `current_token_env` (env var holding the existing PAT that authenticates the create
  call, default `JIRA_ROTATOR_TOKEN`).
- Admins can set limits/expiry rules via system properties (e.g.
  `atlassian.pats.eternal.tokens.enabled`). (confirmed)
- Confirmed by the user: the instance is self-hosted, so this is Data Center/Server, not
  Jira Cloud (Cloud API tokens work differently and are out of scope).
- Confirmed by the user: login is via SSO. Bootstrap: the first PAT must be created by
  hand in the UI (no local password for the API). Later rotations authenticate with the
  existing PAT as bearer to call the create endpoint (Atlassian docs show this pattern).
  Rotate before expiry; an expired PAT means a manual bootstrap again.
- To confirm: exact Jira version (PATs need 8.14+ or Service Management 4.15+; check
  Help > About Jira or `{base_url}/rest/api/2/serverInfo`), and any admin limits on PAT
  lifetime or non-expiring tokens.

Docs: https://confluence.atlassian.com/display/ENTERPRISE/Using+personal+access+tokens

## GitHub, fine-grained and classic (assisted)

- No API to create fine-grained PATs; web UI only. A community thread (#148626) and an
  open-source browser-automation tool both state this. (confirmed second-hand)
- Limit of 50 fine-grained PATs per user. (confirmed)
- Classic PATs: only UI creation docs found. (unverified that no API exists)
- Fine-grained PATs cannot do everything classic can (outside collaborator access, some
  endpoints). Per-endpoint support is documented in GitHub's REST reference.
- Alternative: GitHub Apps give short-lived installation tokens and avoid rotation for
  CI-style use. Not a drop-in replacement for personal tokens.
- Create URL for fine-grained: `https://github.com/settings/personal-access-tokens/new`, with
  documented prefill parameters `name` (max 40 chars), `description`, `target_name`,
  `expires_in` (1-366 or `none`) and permission levels. (confirmed, GitHub docs) The adapter
  prefills `name` and `expires_in` (`rotate_every_days + grace_days + 14`, capped at 366).
- Classic: GitHub documents no creation URL or prefill, only the UI path. The adapter opens
  `https://github.com/settings/tokens/new` with no parameters. (URL unverified)
- Delete: Settings > Developer settings > Personal access tokens, the adapter opens
  `/settings/personal-access-tokens` (fine-grained) or `/settings/tokens` (classic).
  (UI path confirmed; direct URLs unverified)
- Verify: `GET https://api.github.com/user` with the new token as bearer.
- Adapter: inventory `kind` is required (`fine-grained` or `classic`); `provider_ref` takes
  `host` and `token_name` (default: credential id).

## GitHub Enterprise Server (assisted)

- Same PAT UI flow per GitHub's Enterprise Server docs. Use the instance host for console
  URLs. Behavior varies by GHES version; check the version in use. If it is GitHub
  Enterprise Cloud (github.com with enterprise accounts), it behaves like github.com.
- Verify: `GET https://HOST/api/v3/user`. (GHES REST base path; not re-checked against the
  docs for the specific version in use)
- Adapter: provider `github-enterprise` requires `provider_ref.host`; otherwise as GitHub.

## RunPod (assisted)

- API keys: create, edit, disable, delete all documented as console actions at
  `https://console.runpod.io/user/credentials` (API Keys tab). Secret shown once.
  (confirmed)
- S3 API keys and SSH keys are also console-managed. (confirmed)
- A REST v2 API exists for account secrets (e.g. delete), which are injected pod
  secrets, not API keys. (confirmed; separate concept)
- No documented endpoint to mint API keys. An undocumented GraphQL mutation is possible.
  (unverified)
- REST API: base `https://rest.runpod.io/v1`, bearer API key. (confirmed) It has no
  whoami endpoint, so the adapter verifies with `GET /pods` (an authenticated read; the docs
  do not state its cost). The console URL used for create and delete is
  `https://console.runpod.io/user/credentials`.

Docs: https://docs.runpod.io/get-started/credentials

## Modal (assisted)

- Tokens come from the dashboard or `modal token new` (browser login, writes
  `~/.modal.toml`). Used as `MODAL_TOKEN_ID` (ak-...) and `MODAL_TOKEN_SECRET` (as-...).
  (confirmed, via third-party docs mirror)
- No programmatic create/revoke found. (unverified)
- Dashboard token URL guess: `https://modal.com/settings/tokens`. (unverified)

## Bitwarden (assisted, rotate last)

- Personal API key: View/Rotate in web app (Settings > Security > Keys). Rotating changes
  only `client_secret` and invalidates the old key and active sessions. (confirmed)
- No CLI/API for rotating it found. Secrets Manager access tokens are created in the
  web UI under Machine accounts. (confirmed for UI; API unverified)
- As the central store the tool writes to, Bitwarden's own credential is a
  bootstrapping problem: rotating it breaks the tool's own login. Do it last, manually.
- Writing items: `bw edit item <id>` reads base64 JSON from stdin (documented pipe example
  `bw get item | jq | bw encode | bw edit item <id>`), which keeps the secret out of argv.
  Session via `BW_SESSION`; `bw unlock --passwordenv VAR --raw` unlocks non-interactively and
  prints only the session key; `bw status` returns JSON with `status` of `unlocked`, `locked`
  or `unauthenticated`; global flags `--nointeraction` and `--raw` exist. (confirmed, Bitwarden
  CLI docs)
  API-key login (`bw login --apikey`, `BW_CLIENTID`/`BW_CLIENTSECRET`) works for automation,
  then `bw unlock`. (confirmed)

Docs: https://bitwarden.com/help/personal-api-key
