# CHANGELOG

## V0.1.0 — 2026-04-27

首版骨架。

**改动**
- 端口适配器架构：`domain` / `ports` / `adapters` / `app` / `bootstrap` / `cli`。
- Anthropic adapter 调用 `claude-opus-4-7`，system prompt 整段 `cache_control: ephemeral`，多轮对话末端滚动 cache 断点（≤4）。
- JSONL per-session 持久化，`data/sessions/<session-id>.jsonl` + `index.jsonl`。
- 固定短视频脚本 JSON 输出 schema (title / platform / duration_sec / hook / scenes / cta / tags)。
- CLI 子命令：`new` / `resume` / `list` / `show`。

**原因**
- 长对话 + Opus 4.7 + 多轮 prompt cache 是项目主轴；hex 布局便于后续替换 LLM/存储不动业务层。
