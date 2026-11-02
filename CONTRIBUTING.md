# Contributing

```
make install     # editable install with dev tools
make check       # ruff + format check + mypy + tests with coverage gate (what CI runs)
make format      # apply formatter and safe lint fixes
```

## Ground rules

* **Respect the layers** (`docs/architecture.md`). `tests/unit/test_architecture.py` fails if a module imports
  upwards or uses relative imports. Adding a top-level module means deciding its layer in that test.
* **Determinism is a feature.** Any change to simulation logic should keep `Engine.verify` passing; a behaviour change
  that alters state hashes is a deliberate, documented change (note it in `CHANGELOG.md`).
* **Errors:** raise a `simulacrum.errors` type for conditions callers should handle; they also subclass the closest
  builtin exception so existing handlers keep working.
* **Tests:** unit tests for a single module's contract in `tests/unit`; multi-layer or long-running behaviour in
  `tests/integration` (auto-marked `integration`). New HTTP behaviour needs an API test and a line in `docs/api.md`.
* **Typing:** `mypy` runs on `src/`. Plugin-facing signatures should stay annotated so authors can copy them.
* **Style:** ruff (lint + format), 120 columns.
