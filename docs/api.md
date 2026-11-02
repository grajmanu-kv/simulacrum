# HTTP API

Interactive reference: `GET /docs` (OpenAPI/Swagger) and `GET /openapi.json` on a running server. JSON bodies unless
noted. Every response carries `x-request-id` (an inbound `x-request-id` is echoed only if it matches
`[A-Za-z0-9._-]{1,64}`, otherwise a new id is generated).

| Method and path | Purpose |
|---|---|
| `GET /healthz` | liveness: process is up |
| `GET /readyz` | readiness: ecosystems directory readable; reports session count |
| `GET /api/version` | package version |
| `GET /api/ecosystems` | worlds available in the ecosystems directory |
| `GET /api/components` | registered brains, actions, systems, environment agents, generators, perturbations |
| `POST /api/sessions` | create a world: `{ecosystem \| spec, seed?, llm?}` (`llm`: `stub`, `anthropic`, `gemini`) → `{session, snapshot, catalog, ...}` |
| `POST /api/sessions/{id}/step` | `{n}` ticks (1..`SIMULACRUM_MAX_STEP`) → snapshot |
| `POST /api/sessions/{id}/perturb` | `{name, params}`; applied at the start of the next tick |
| `GET /api/sessions/{id}/state` | current snapshot |
| `GET /api/sessions/{id}/text?field=` | ASCII frame (terrain, or a field as a heat map) |
| `GET /api/sessions/{id}/spec` | the spec in force |
| `GET /api/sessions/{id}/log` | replayable run log (spec, inputs by tick, recorded LLM responses, final hash) |
| `POST /api/sessions/{id}/verify` | replay the log in a fresh engine; `{ok, expected, got, ticks[, error]}` |

## Status codes

| Code | When |
|---|---|
| 200 | success |
| 400 | invalid request the domain rejects: unknown component, disabled or invalid perturbation, step above the limit, plugin in an inline spec, unknown/unconfigured LLM provider |
| 404 | unknown or evicted session; unknown ecosystem id |
| 422 | request body fails schema validation (e.g. wrong types in an inline spec) |
| 500 | a plugin raised while stepping or replaying (message included) |

## Sessions

Sessions are held in process memory, at most `SIMULACRUM_MAX_SESSIONS`; the least recently used one is evicted.
Create a session, keep its id, and treat a 404 as "recreate from the downloaded run log or the same seed".
