---
name: sandbox-and-project-gotchas
description: Non-obvious facts about this repo's sandbox and decisions (no CI, no ensurepip, token scope, venv location, open decisions)
metadata:
  type: project
---

- **No CI, by decision (2026-10-26).** Single-user tool; run `./security lint` and `./security test`
  locally before merging. The gh token also lacks `workflow` scope, so a workflow file cannot be pushed.
- **Sandbox venv:** ensurepip works now (python3 plugin in `.claude/sandbox/plugin.sh`) and a fresh
  venv was verified (2026-10-31). `./security` uses `.venvs/<os>-<arch>-<hash>` per environment; the
  sandbox keeps using `export SECURITY_VENV=/workspace/.tmp/venv`.
- **Docs:** `credentials/rotator/CLAUDE.md` and `README.md` were created mode 444; the user allowed
  edits (`chmod u+w`).
- **Untracked local files** `.envrc`, `.envrc-cs`, `.env` belong to the user; never `git add -A`
  without excluding them.
- **Open decisions (on the issues):** #7 Bitwarden self-rotation / where bootstrap secrets live
  (also answers the Cloudflare manager-token bootstrap), #17 Modal two-part token, #5 Jira version.
- **Unverified against live services** (only mocked HTTP / a fake `bw`): every adapter. The user plans
  one big validation session; issues stay open with `validate` + `needs attention`.
