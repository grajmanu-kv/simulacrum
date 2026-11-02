# Operations

## Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `SIMULACRUM_ECOSYSTEMS_DIR` | bundled examples | directory with ecosystem `*.json` and file plugins |
| `SIMULACRUM_HOST` / `SIMULACRUM_PORT` | `127.0.0.1` / `8000` | bind address (the container image sets `0.0.0.0`) |
| `SIMULACRUM_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `SIMULACRUM_MAX_SESSIONS` | `12` | in-memory session cap (LRU eviction) |
| `SIMULACRUM_MAX_STEP` | `200` | maximum ticks per `step` request |
| `ANTHROPIC_API_KEY` | unset | enables `llm: "anthropic"`; never logged or echoed |
| `SIMULACRUM_MODEL` | `claude-sonnet-5-5` | model id for the Anthropic provider |
| `GEMINI_API_KEY` | unset | enables `llm: "gemini"`; sent only in the `x-goog-api-key` header, never logged or echoed |
| `SIMULACRUM_GEMINI_MODEL` | `gemini-3.8-flash` | model id for the Gemini provider (letters, digits, `.`, `_`, `-` only) |
| `SIMULACRUM_GEMINI_MAX_OUTPUT_TOKENS` | `2048` | output cap; thinking tokens count against it, so a small value can produce empty replies |
| `SIMULACRUM_GEMINI_THINKING_LEVEL` | unset | optional `generationConfig.thinkingConfig.thinkingLevel`; allowed values depend on the model |
| `SIMULACRUM_LLM_MAX_CALLS` | `400` | per-session call budget for either provider; beyond it the offline stub answers |

Invalid values fail at startup with the variable name in the message. CLI flags override the environment.

## Running

```
simulacrum serve --ecosystems ./my_worlds --port 8000        # local
uvicorn --factory simulacrum.api.app:create_app --port 8000  # explicit ASGI form
docker build -t simulacrum . && docker run -p 8000:8000 -v $PWD/my_worlds:/data/worlds:ro \
    -e SIMULACRUM_ECOSYSTEMS_DIR=/data/worlds simulacrum
```

**Run exactly one worker process.** Sessions live in memory; several workers would give each client a random
subset of sessions.

## Observability

* Logs: standard `logging` under the `simulacrum` logger, one line per request with method, path, status,
  latency and request id; plugin loads, session creation and LLM fallbacks are logged. Set `DEBUG` for engine setup.
* Probes: `/healthz` for liveness, `/readyz` for readiness (ecosystems directory readable).
* No metrics endpoint or tracing yet.

## Security checklist before exposing it beyond a trusted network

1. Put authentication and TLS in front (reverse proxy or API gateway); the app has none.
2. Add per-client rate limits and session ownership; today any caller can use any session id it knows.
3. Treat the ecosystems directory as deployed code (plugins run with server privileges); mount it read-only.
4. Keep `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` in a secret store; cap spend with `SIMULACRUM_LLM_MAX_CALLS` and provider-side limits.
5. Add a Content-Security-Policy at the proxy (the UI uses inline `style` attributes, so `style-src` needs
   `'unsafe-inline'` or a UI change).

## Release checklist

`make check` (ruff, mypy, tests with coverage gate) → bump `version` in `pyproject.toml` → update `CHANGELOG.md` →
`make build` → publish the wheel/image. CI (`.github/workflows/ci.yml`) runs the same gates on Python 3.10–3.13,
checks the wheel contents, and builds the image.
