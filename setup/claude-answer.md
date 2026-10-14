# Explain what make test does

`make test` is a target defined in the repository's `Makefile`:

```make
test:
	pytest -q
```

When you run it, `make` executes `pytest -q` from the repository root:

- **pytest** discovers test files (`test_*.py` / `*_test.py`) under the current directory, such as `tests/test_smoke.py`, and runs every `test_*` function in them.
- **`-q` (quiet)** shortens the output: one character per test (`.` for pass, `F` for fail) and a short summary line, for example `2 passed in 0.10s`.
- The current smoke tests check that `docs/openapi.yaml` can be loaded as an OpenAPI 3.x document with at least one path, and that the required participant files (`.claude/settings.json`, `.devcontainer/devcontainer.json`, `CLAUDE.md`, `Makefile`, `tracker/CR-2.md`, `tracker/README.md`) exist.
- If any test fails, pytest exits with a non-zero code, so `make test` fails too. This is what makes it usable in CI and in `make verify-setup`, which runs the smoke tests as its last step.

`make test` does **not** validate the API contract rules. That is done separately by `make lint-contract`.
