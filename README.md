# script-gen

Script-generation agent for short-video pipelines. Given a topic, platform, and target duration, it produces a structured script (scenes + hooks + caption + thumbnail text where applicable) as JSON.

Designed to plug into [director](https://github.com/franciseliang99-dot/director), but also runnable standalone. Hexagonal architecture (`domain` / `ports` / `adapters` / `app` / `bootstrap` / `cli`).

## Install

```bash
uv sync
```

## Usage

```bash
uv run python -m cli.main new "How HTTP/3 actually works" --platform youtube --variant short --duration 60
# → prints session id on stderr
uv run python -m cli.main show <session-id>   # fetch the JSON script
```

Platforms: `tiktok`, `douyin`, `youtube` (with `--variant short|long`), `reels`.

## Health check

```bash
uv run python -m cli.main --version --json
# {"name":"script-gen","version":"0.2.1","healthy":true,...}
```

`extra.optional: true` signals to orchestrators that script-gen is non-blocking — director V0.4.1+ has an in-context fallback when `ANTHROPIC_API_KEY` is unset.

## License

MIT — see [LICENSE](LICENSE).
