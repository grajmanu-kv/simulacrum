from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient

from simulacrum import Settings
from simulacrum.api import create_app


def test_session_lifecycle(client: TestClient) -> None:
    names = {e["id"] for e in client.get("/api/ecosystems").json()}
    assert {"forest", "junction"} <= names
    r = client.post("/api/sessions", json={"ecosystem": "forest", "seed": 7}).json()
    sid = r["session"]
    assert {c["name"] for c in r["catalog"]} >= {"drought", "terraform"}
    snap = client.post(f"/api/sessions/{sid}/step", json={"n": 25}).json()
    assert snap["tick"] == 25 and snap["agents"] and snap["history"]
    q = client.post(
        f"/api/sessions/{sid}/perturb", json={"name": "plague", "params": {"type": "grazer", "fraction": 0.5}}
    ).json()
    assert q["queued"]["tick"] == 26 and q["snapshot"]["pending"]
    client.post(f"/api/sessions/{sid}/step", json={"n": 10})
    assert client.post(f"/api/sessions/{sid}/verify").json()["ok"] is True
    assert client.get(f"/api/sessions/{sid}/log").json()["ticks"] == 35
    assert "tick 35" in client.get(f"/api/sessions/{sid}/text").text
    assert client.get(f"/api/sessions/{sid}/state").json()["tick"] == 35
    assert client.get(f"/api/sessions/{sid}/spec").json()["name"]


def test_errors_are_clear_and_correctly_coded(client: TestClient) -> None:
    assert client.post("/api/sessions/nope/step", json={"n": 1}).status_code == 404
    assert client.post("/api/sessions", json={"ecosystem": "../../etc/passwd"}).status_code == 404
    assert client.post("/api/sessions", json={}).status_code == 400
    sid = client.post("/api/sessions", json={"ecosystem": "forest"}).json()["session"]
    assert client.post(f"/api/sessions/{sid}/step", json={"n": 0}).status_code == 422
    over = client.post(f"/api/sessions/{sid}/step", json={"n": 10**6})
    assert over.status_code == 400 and "<= 200" in over.json()["detail"]
    bad = client.post(f"/api/sessions/{sid}/perturb", json={"name": "accident", "params": {}})
    assert bad.status_code == 400 and "not enabled" in bad.json()["detail"]
    assert client.get(f"/api/sessions/{sid}/text", params={"field": "nope"}).status_code == 400


def test_anthropic_without_server_key_is_a_clear_400(client: TestClient) -> None:
    r = client.post("/api/sessions", json={"ecosystem": "forest", "llm": "anthropic"})
    assert r.status_code == 400 and "ANTHROPIC_API_KEY" in r.json()["detail"]
    assert client.post("/api/sessions", json={"ecosystem": "forest", "llm": "gpt"}).status_code == 400


def test_gemini_without_server_key_is_a_clear_400(client: TestClient) -> None:
    r = client.post("/api/sessions", json={"ecosystem": "forest", "llm": "gemini"})
    assert r.status_code == 400
    assert "GEMINI_API_KEY" in r.json()["detail"]


def test_gemini_with_a_server_key_creates_a_session(settings: Settings) -> None:
    c = TestClient(create_app(replace(settings, gemini_api_key="k")))
    r = c.post("/api/sessions", json={"ecosystem": "garden", "llm": "gemini"})
    assert r.status_code == 200
    assert r.json()["llm"] == "gemini"
    assert "k" not in str(c.get("/api/version").json())


def test_inline_spec_is_declarative_only(client: TestClient, eco_dir: Path) -> None:
    spec = json.loads((eco_dir / "forest.json").read_text())
    assert client.post("/api/sessions", json={"spec": spec}).status_code == 200
    spec["plugins"] = ["junction_plugin.py"]
    assert client.post("/api/sessions", json={"spec": spec}).status_code == 400
    spec["plugins"] = []
    spec["agent_types"][0]["brain"] = "does_not_exist"
    assert client.post("/api/sessions", json={"spec": spec}).status_code == 400
    spec["agent_types"][0]["max_energy"] = "lots"
    assert client.post("/api/sessions", json={"spec": spec}).status_code == 422


def test_step_limit_and_session_cap_come_from_settings(settings: Settings) -> None:
    c = TestClient(create_app(replace(settings, max_step=5, max_sessions=2)))
    sids = [c.post("/api/sessions", json={"ecosystem": "forest"}).json()["session"] for _ in range(3)]
    assert c.post(f"/api/sessions/{sids[2]}/step", json={"n": 6}).status_code == 400
    assert c.post(f"/api/sessions/{sids[2]}/step", json={"n": 5}).status_code == 200
    assert c.get(f"/api/sessions/{sids[0]}/state").status_code == 404  # oldest evicted
    assert c.get(f"/api/sessions/{sids[1]}/state").status_code == 200


def test_health_readiness_and_version(client: TestClient, settings: Settings, tmp_path: Path) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    ready = client.get("/readyz").json()
    assert ready["status"] == "ready" and ready["max_sessions"] == 12
    assert client.get("/api/version").json()["name"] == "simulacrum"
    broken = TestClient(create_app(replace(settings, ecosystems_dir=tmp_path / "missing")))
    assert broken.get("/readyz").json()["status"] == "degraded"
    assert broken.get("/healthz").status_code == 200  # liveness must not depend on content


def test_request_id_is_echoed_when_safe_and_replaced_when_not(client: TestClient) -> None:
    assert client.get("/healthz", headers={"x-request-id": "abc-123"}).headers["x-request-id"] == "abc-123"
    hostile = client.get("/healthz", headers={"x-request-id": "bad id\twith spaces"})
    assert hostile.headers["x-request-id"] != "bad id\twith spaces" and len(hostile.headers["x-request-id"]) == 12
    assert client.get("/healthz").headers["x-content-type-options"] == "nosniff"


def test_components_catalog_lists_extension_points(client: TestClient) -> None:
    comp = client.get("/api/components").json()
    assert {"grazer", "hunter", "faction"} <= set(comp["brains"])
    assert {"noise_terrain"} <= set(comp["generators"]) and "drought" in comp["perturbations"]


def test_ui_and_static_assets_are_served(client: TestClient) -> None:
    page = client.get("/")
    assert page.status_code == 200 and "Change the world" in page.text and "Simulacrum" in page.text
    assert "/static/app.js" in page.text
    js, css = client.get("/static/app.js"), client.get("/static/app.css")
    assert js.status_code == 200 and "api(" in js.text and css.status_code == 200
    assert client.get("/static/../config.py").status_code in (404, 400)
