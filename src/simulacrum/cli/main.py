"""CLI.

    simulacrum run ecosystems/forest.json --ticks 200 --every 50 [--log-out run.json]
    simulacrum serve --ecosystems ./my_worlds --port 8000
    simulacrum validate my_world.json
    simulacrum verify run.json

Exit codes: 0 success, 1 failure (invalid spec, replay divergence, runtime error), 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from simulacrum._version import __version__
from simulacrum.config import Settings, configure_logging
from simulacrum.engine import Engine, discover_entry_point_plugins
from simulacrum.errors import SimulacrumError
from simulacrum.llm import PROVIDERS, make_provider
from simulacrum.repository import load_spec


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="simulacrum", description="Declarative, extensible, replayable world simulator.")
    ap.add_argument("--version", action="version", version=f"simulacrum {__version__}")
    ap.add_argument("--log-level", help="overrides SIMULACRUM_LOG_LEVEL")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run headless and print ASCII frames")
    r.add_argument("spec", type=Path)
    r.add_argument("--ticks", type=int, default=100)
    r.add_argument("--every", type=int, default=50, help="print a frame every N ticks")
    r.add_argument("--seed", type=int)
    r.add_argument("--field", help="render this field as a heat map instead of terrain")
    r.add_argument("--llm", default="stub", choices=PROVIDERS)
    r.add_argument("--log-out", type=Path, help="write the replayable run log (JSON) here")

    s = sub.add_parser("serve", help="start the web UI + API (single process)")
    s.add_argument("--ecosystems", type=Path, help="directory of ecosystem JSON files and plugins")
    s.add_argument("--host")
    s.add_argument("--port", type=int)

    v = sub.add_parser("validate", help="check that a spec loads and all its references resolve")
    v.add_argument("spec", type=Path, nargs="+")

    y = sub.add_parser("verify", help="replay a run log and compare the final state hash")
    y.add_argument("log", type=Path)
    y.add_argument("--ecosystems", type=Path, help="directory used to resolve the log's file plugins")
    return ap


def _run(args: argparse.Namespace, settings: Settings) -> int:
    spec, base = load_spec(args.spec)
    if args.seed is not None:
        spec.seed = args.seed
    eng = Engine(spec, base_dir=base, llm=make_provider(args.llm, settings))
    print(eng.render_ascii(args.field))
    for t in range(1, args.ticks + 1):
        eng.step()
        if t % args.every == 0:
            print(f"\n{eng.render_ascii(args.field)}")
    print("\nrecent events:")
    for e in list(eng.world.events)[-8:]:
        print(f"  t{e['t']:>4} [{e['kind']}] {e['text']}")
    print(f"\nstate hash {eng.world.state_hash()}")
    if args.log_out:
        args.log_out.write_text(json.dumps(eng.export_log()))
        print(f"run log written to {args.log_out}")
    return 0


def _serve(args: argparse.Namespace, settings: Settings) -> int:
    import uvicorn

    from simulacrum.api import create_app

    overrides = {
        k: v
        for k, v in {
            "ecosystems_dir": args.ecosystems.resolve() if args.ecosystems else None,
            "host": args.host,
            "port": args.port,
        }.items()
        if v is not None
    }
    settings = replace(settings, **overrides)
    # One process only: sessions live in memory. See docs/operations.md.
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port, log_level=settings.log_level.lower())
    return 0


def _validate(args: argparse.Namespace, settings: Settings) -> int:
    bad = 0
    for path in args.spec:
        try:
            spec, base = load_spec(path)
            eng = Engine(spec, base_dir=base)
        except Exception as e:  # report every file, then fail
            print(f"FAIL {path}: {type(e).__name__}: {e}", file=sys.stderr)
            bad += 1
            continue
        w = eng.world
        print(
            f"ok   {path}: {spec.name!r} {w.w}x{w.h}, {len(spec.agent_types)} agent types, "
            f"{len(spec.perturbations)} perturbations, {len(w.agents)} initial agents"
        )
    return 1 if bad else 0


def _verify(args: argparse.Namespace, settings: Settings) -> int:
    root = (args.ecosystems or settings.ecosystems_dir).resolve()
    result = Engine.verify(json.loads(args.log.read_text()), base_dir=root, plugin_root=root)
    print(json.dumps(result))
    return 0 if result["ok"] else 1


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        settings = Settings.from_env()
        if args.log_level:
            settings = replace(settings, log_level=args.log_level.upper())
        configure_logging(settings.log_level)
        if args.cmd != "serve":  # create_app() discovers them itself
            discover_entry_point_plugins()
        handler = {"run": _run, "serve": _serve, "validate": _validate, "verify": _verify}[args.cmd]
        return handler(args, settings)
    except (SimulacrumError, ValueError, OSError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except BrokenPipeError:  # e.g. `simulacrum run ... | head`
        return 0


if __name__ == "__main__":
    sys.exit(main())
