from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from app.script_agent import latest_script, print_stream
from bootstrap.container import DEFAULT_MODEL, build_agent, build_store


def cmd_new(args: argparse.Namespace) -> int:
    agent, store = build_agent(model=args.model, max_tokens=args.max_tokens)
    sys.stderr.write(f"[script-gen] new session, model={args.model}, platform={args.platform}, duration={args.duration}s\n")
    session = agent.new_session(args.description, args.platform, args.duration)
    sys.stderr.write(f"[script-gen] session id: {session.id}\n")
    if args.message is not None:
        sys.stderr.write(f"[script-gen] applying revision...\n")
        print_stream(agent.iterate_stream(session.id, args.message))
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
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
    store = build_store()
    rows = store.list(limit=args.limit)
    if not rows:
        sys.stderr.write("[script-gen] no sessions yet\n")
        return 0
    for r in rows:
        print(f"{r['created_at']}  {r['id']}  [{r['platform']} {r['duration_sec']}s]  {r['description'][:60]}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
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
    p = argparse.ArgumentParser(prog="script-gen", description="短视频脚本生成 agent")
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model id (default: {DEFAULT_MODEL})")
    p.add_argument("--max-tokens", type=int, default=4096)
    sub = p.add_subparsers(dest="cmd", required=True)

    pnew = sub.add_parser("new", help="start a new session from a description")
    pnew.add_argument("description", help="题材描述")
    pnew.add_argument("--platform", choices=["tiktok", "douyin", "reels"], default="douyin")
    pnew.add_argument("--duration", type=int, default=60, help="目标时长 (秒)")
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
