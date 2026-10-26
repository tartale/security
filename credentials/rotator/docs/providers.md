# Provider capabilities

Research snapshot from 2026-10-25. Status key: **confirmed** = found in provider docs or
an API reference; **unverified** = inferred, second-hand, or not found. Re-check before
implementing.

## Summary

| Provider | Mode | Create new | Revoke old |
|---|---|---|---|
| Cloudflare | auto | API roll (confirmed) | implicit in roll (confirmed via third-party source) |
| Jira Data Center | auto | REST create (confirmed) | UI/admin confirmed; REST delete unverified |
| GitHub fine-grained PAT | assisted | UI only (no API, per community thread + tooling) | UI |
| GitHub classic PAT | assisted | UI only (unverified beyond docs showing UI flow) | UI |
| GitHub Enterprise Server | assisted | UI flow documented (confirmed); API absence unverified | UI |
| RunPod | assisted | Console only per docs (undocumented GraphQL unverified) | Console |
| Modal | assisted | Dashboard or `modal token new` browser flow (API unverified) | Dashboard |
| Bitwarden | assisted | Rotate button in web app; CLI/API not found | n/a (rotation invalidates old) |

## Cloudflare (auto)

- Roll: `PUT https://api.cloudflare.com/client/v4/user/tokens/{token_id}/value`, body `{}`.
  Returns the new token value in `result`. Same token ID, new secret. Requires the
  "API Tokens Write" permission on the calling token. (confirmed)
- Account-owned tokens have an equivalent roll endpoint under the account. (confirmed,
  via third-party connector docs; check Cloudflare's own reference)
- Verify: `GET /user/tokens/verify` with the new token. (confirmed)
- Open question: bootstrap/rotation of the token that has "API Tokens Write".
- Console fallback: dashboard > profile > API Tokens (URL unverified).

Docs: https://developers.cloudflare.com/api/operations/user-api-tokens-roll-token

## Jira Enterprise = Data Center (auto create)

- Create: `POST {base_url}/rest/pat/latest/tokens`, body `{"name": "...",
  "expirationDuration": 90}` (days). Authenticate as the owning user (basic auth or an
  existing PAT as bearer). You cannot create a PAT on behalf of another user. (confirmed)
- Available from Jira Core/Software 8.14 and Service Management 4.15. PATs are not
  scopeable in Data Center. (confirmed)
- Revoke: Profile > Personal Access Tokens, or admin screen (System > Administering
  personal access tokens). REST delete endpoint probably exists. (unverified)
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
- Console URLs (unverified): `https://github.com/settings/personal-access-tokens/new`,
  `https://github.com/settings/tokens/new`. Query-parameter prefill (name, description,
  expiry) is believed to work but unverified.
- Optional later adapter: browser automation (brittle, needs logged-in Chrome).

## GitHub Enterprise Server (assisted)

- Same PAT UI flow per GitHub's Enterprise Server docs. Use the instance host for console
  URLs. Behavior varies by GHES version; check the version in use. If it is GitHub
  Enterprise Cloud (github.com with enterprise accounts), it behaves like github.com.

## RunPod (assisted)

- API keys: create, edit, disable, delete all documented as console actions at
  `https://console.runpod.io/user/credentials` (API Keys tab). Secret shown once.
  (confirmed)
- S3 API keys and SSH keys are also console-managed. (confirmed)
- A REST v2 API exists for account secrets (e.g. delete), which are injected pod
  secrets, not API keys. (confirmed; separate concept)
- No documented endpoint to mint API keys. An undocumented GraphQL mutation is possible.
  (unverified)

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
- Writing items: `bw` CLI supports item edit; API-key login (`bw login --apikey`,
  `BW_CLIENTID`/`BW_CLIENTSECRET`) works for automation, then `bw unlock`. (confirmed)

Docs: https://bitwarden.com/help/personal-api-key
