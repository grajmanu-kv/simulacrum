# Changelog

## Unreleased

* **Gemini provider** (`llm: "gemini"`, CLI `--llm gemini`, UI option): Google `generateContent` over stdlib HTTP; key sent
  in the `x-goog-api-key` header only; blocked, truncated or empty replies fall back to the offline answer. Configured
  with `GEMINI_API_KEY`, `SIMULACRUM_GEMINI_MODEL`, `SIMULACRUM_GEMINI_MAX_OUTPUT_TOKENS`, `SIMULACRUM_GEMINI_THINKING_LEVEL`.
  Not yet exercised against Google's live service (no key was available when it was written).
* Anthropic and Gemini now share `llm/http.py` (budget, fallback, logging). Anthropic behaviour is unchanged. Fallback
  warnings now include the HTTP status for HTTP errors.

* New bundled world **The Garden** (`garden.json` + `garden_plugin.py`): two people and a god. People forage, share
  or snatch food; the god chooses bless / trial / mercy / silence through the LLM provider (recorded, replayable), with
  an offline stand-in. Adds a `manna` perturbation.
* `simulacrum.llm.register_stub_responder(kind)`: plugins can supply the offline answer for their own request kinds.
  Default behaviour for faction decisions is unchanged (bundled forest/junction hashes identical).
* Bundled plugins may import `simulacrum.llm` (layer rule updated).

## 0.1.0

First packaged release (renamed from the `ecoworld` prototype).

* Layered package: `core`, `llm`, `library`, `engine`, `api`, `cli`, with the dependency rule enforced by a test.
* Settings from `SIMULACRUM_*` environment variables; domain error hierarchy; structured request logging with
  request ids; `/healthz`, `/readyz`, `/api/version`.
* Plugins: file plugins (confined to the ecosystems directory) and `simulacrum.plugins` entry points.
* CLI: `run`, `serve`, `validate`, `verify`.
* UI split into `index.html`, `app.css`, `app.js`; chronicle empty state no longer wraps one word per line.
* Tooling: ruff, mypy, pytest with coverage gate, Makefile, Dockerfile, CI workflow.
* Behaviour is unchanged from the prototype: identical state hashes for the bundled worlds (forest `80ac5bcf812c42c8`,
  junction `8925f2619e1c0e74` after 300 ticks, default seeds).
* Changed: `ANTHROPIC` provider failures are now logged as warnings (they were silent); `ECOWORLD_*` variables are
  replaced by `SIMULACRUM_*`; the run-log download is named `simulacrum-run-tick<N>.json`.
