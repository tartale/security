# security

Personal security tooling. One root CLI, `./security`, controls every subproject.

```
./security --help
./security credentials --help   # rotate, test, lint; see credentials/rotator/
./security lint                         # lint every project
./security test                         # test every project
```

The first run creates `.venv` and installs the projects into it (override the location with
`SECURITY_VENV`). New subprojects are mounted in `src/security/cli.py`.

| Path | What |
|---|---|
| `credentials/rotator/` | Rotate API keys and tokens, distribute to Bitwarden and env files |
