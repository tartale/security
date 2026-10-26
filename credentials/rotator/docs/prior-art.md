# Prior art

Research snapshot from 2026-10-25. Nothing found covers the full chain (provider rotation
+ password manager + env file distribution) for this provider set.

## Closest match

**keyrotate** (https://github.com/Prompto-Studio/keyrotate) is an alpha MIT CLI. One
command updates 1Password, GitHub, Supabase, Netlify, Fly.io and `.env`, verifying the
new key against the provider before writing anywhere. Fully automatic rotation works for
Resend and PostHog only; other providers need you to paste the new key. Destinations do
not include Bitwarden. Provider adapters are described as roughly 30 lines each.
Options: contribute adapters upstream, or borrow its adapter model.

## Platforms

- **Infisical**: MIT core, self-hostable. Free plan includes the CLI, API, self-hosting
  and integrations (GitHub Actions, Vercel, Ansible, etc.), capped at 5 identities and
  10 integrations. Rotation and dynamic secrets are plan-gated and focus on databases and
  cloud credentials, not arbitrary SaaS keys.
- **OpenBao**: Linux Foundation fork of Vault's last MPL-2.0 code. Free, with dynamic
  secrets, PKI and namespaces ungated. Carries Vault's operational weight (Raft,
  unsealing, HCL policies). Dynamic secrets target systems like AWS and SQL databases.

## Narrower tools and design references

- **rekey-core**: early Rust library modelling which providers allow atomic rotation vs
  manual-only creation (Cloudflare roll, GitLab tokens; Anthropic admin keys and classic
  GitHub PATs are manual). Useful as a capability taxonomy.
- **KeyGate**: uses vendor admin APIs (OpenAI, Anthropic, Azure, Google) to provision
  scoped keys per developer and rotate by revoke + re-provision.
- **Laravel Locksmith**: Laravel-only. Its "key pool" idea suits services with no
  key-creation API.
- **gh-tools fine-grained PAT skill**: browser automation for creating GitHub
  fine-grained PATs, revoking and storing them in one step. Reference for an optional
  GitHub adapter.

## Password manager tooling

- Bitwarden CLI (`bw`) supports API-key login for automation; wrappers such as
  `bitwarden-py` read and update item passwords.
- 1Password CLI has had an edit-item command since v0.10.0 (not needed for this scope).

## Conclusions

- Provider-side rotation is limited by what each provider's API allows, not by tooling.
- A generic "rotate everything" tool does not exist; each provider needs an adapter.
- The assisted mode (open console URL, paste, verify, distribute, prompt to revoke) is the
  realistic path for providers without a create API.
