from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

__version__ = "0.2.0"


def _health_dict() -> dict:
    deps, env, checks, reasons = [], [], [], []
    try:
        import anthropic as _a
        ver = getattr(_a, "__version__", "unknown")
        deps.append({"name": "anthropic", "kind": "python", "ok": True,
                     "found": ver, "required": ">=0.92.0"})
    except ImportError as e:
        deps.append({"name": "anthropic", "kind": "python", "ok": False, "error": str(e)})
        reasons.append("anthropic SDK not installed (critical)")
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    env.append({"name": "ANTHROPIC_API_KEY", "required": True, "set": has_key})
    if not has_key:
        reasons.append("ANTHROPIC_API_KEY not set (critical — script-gen cannot call Claude)")

    crit = [d for d in deps if not d["ok"]] or (not has_key)
    healthy = not crit
    severity = "ok" if healthy else "broken"
    return {
        "name": "script-gen", "version": __version__,
        "healthy": healthy,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "deps": deps, "env": env, "checks": checks, "reasons": reasons,
        "extra": {
            "runtime": f"python{sys.version_info.major}.{sys.version_info.minor}",
            "venv": str(Path(sys.executable).parent.parent),
            "severity": severity,
        },
    }


def _emit_health_or_version() -> None:
    if "--version" not in sys.argv:
        return
    if "--json" in sys.argv:
        h = _health_dict()
        print(json.dumps(h, indent=2, ensure_ascii=False))
        sys.exit(0 if h["healthy"] else (1 if h["extra"]["severity"] == "degraded" else 2))
    print(f"script-gen {__version__}")
    sys.exit(0)


# Heavy imports (anthropic-chain) are deferred to inside main() / cmd_* so that
# `--version --json` health-check works even when anthropic SDK is absent.


def cmd_new(args: argparse.Namespace) -> int:
    from app.script_agent import print_stream
    from bootstrap.container import build_agent
    agent, store = build_agent(model=args.model, max_tokens=args.max_tokens)
    sys.stderr.write(f"[script-gen] new session, model={args.model}, platform={args.platform}, duration={args.duration}s\n")
    session = agent.new_session(args.description, args.platform, args.duration)
    sys.stderr.write(f"[script-gen] session id: {session.id}\n")
    if args.message is not None:
        sys.stderr.write(f"[script-gen] applying revision...\n")
        print_stream(agent.iterate_stream(session.id, args.message))
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    from app.script_agent import print_stream
    from bootstrap.container import build_agent
    agent, store = build_agent(model=args.model, max_tokens=args.max_tokens)
    if not store.exists(args.session_id):
        sys.stderr.write(f"[script-gen] no such session: {args.session_id}\n")
        return 1
    if args.message is None:
        sys.stderr.write("[script-gen] --message required (interactive REPL not yet implemented)\n")
        return 2
    print_stream(agent.iterate_stream(args.session_id, args.message))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    from bootstrap.container import build_store
    store = build_store()
    rows = store.list(limit=args.limit)
    if not rows:
        sys.stderr.write("[script-gen] no sessions yet\n")
        return 0
    for r in rows:
        print(f"{r['created_at']}  {r['id']}  [{r['platform']} {r['duration_sec']}s]  {r['description'][:60]}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    from app.script_agent import latest_script
    from bootstrap.container import build_store
    store = build_store()
    if not store.exists(args.session_id):
        sys.stderr.write(f"[script-gen] no such session: {args.session_id}\n")
        return 1
    session = store.load(args.session_id)
    assistant_turns = [t for t in session.turns if t.role == "assistant"]
    if not assistant_turns:
        sys.stderr.write("[script-gen] session has no assistant turns yet\n")
        return 0

    if args.format == "raw" or args.turn is not None:
        target = assistant_turns[-1] if args.turn is None else assistant_turns[args.turn - 1]
        if args.format == "raw":
            print(target.content)
            return 0

    script = latest_script(session)
    if script is None:
        sys.stderr.write("[script-gen] could not parse latest assistant turn as JSON; raw text follows\n")
        print(assistant_turns[-1].content)
        return 0
    print(json.dumps(dataclasses.asdict(script), ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    _emit_health_or_version()
    # Heavy imports deferred until past health check.
    from bootstrap.container import DEFAULT_MODEL
    p = argparse.ArgumentParser(prog="script-gen", description="短视频脚本生成 agent")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model id (default: {DEFAULT_MODEL})")
    p.add_argument("--max-tokens", type=int, default=4096)
    sub = p.add_subparsers(dest="cmd", required=True)

    pnew = sub.add_parser("new", help="start a new session from a description")
    pnew.add_argument("description", help="题材描述")
    pnew.add_argument("--platform",
                      choices=["tiktok", "douyin", "reels", "youtube"], default="douyin")
    pnew.add_argument("--duration", type=int, default=60, help="目标时长 (秒)")
    pnew.add_argument("--variant",
                      choices=["short", "long", "auto"], default="auto",
                      help="long-form gate (youtube only); auto = duration>60s -> long")
    pnew.add_argument("-m", "--message", default=None, help="生成初稿后立即追加一轮反馈")
    pnew.set_defaults(func=cmd_new)

    pres = sub.add_parser("resume", help="append a revision turn to an existing session")
    pres.add_argument("session_id")
    pres.add_argument("-m", "--message", required=False, default=None)
    pres.set_defaults(func=cmd_resume)

    plst = sub.add_parser("list", help="list recent sessions")
    plst.add_argument("--limit", type=int, default=20)
    plst.set_defaults(func=cmd_list)

    psho = sub.add_parser("show", help="print a session's latest (or N-th) script")
    psho.add_argument("session_id")
    psho.add_argument("--turn", type=int, default=None, help="1-indexed assistant turn (default: latest)")
    psho.add_argument("--format", choices=["raw", "json"], default="json")
    psho.set_defaults(func=cmd_show)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
