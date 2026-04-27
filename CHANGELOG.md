# CHANGELOG

## V0.2.1 — 2026-04-27

**Optional 化** — script-gen 标记为可选 agent(director V0.4.1+ 有 in-context script 生成 fallback,无需 ANTHROPIC_API_KEY)。

**改动**
- `_health_dict()` 加 `extra.optional: True` 标志,告诉 director "我挂了不阻塞 pipeline"。
- `ANTHROPIC_API_KEY` 从 `required: True` 改 `required: False`(注释说明 since V0.2.1)。
- severity 计算:**SDK 缺失 → broken**(无 env 能修);**仅 key 缺失 → degraded**(原来是 broken,现在主 Claude in-context fallback 路径已落,降级);**全有 → ok**。退出码相应调整(degraded → exit 1,原 V0.2.0 是 exit 2)。
- `reasons[]` 改写为信息性(不再说 "critical","cannot call Claude"),改说 "director will use in-context fallback"。

**为什么** — director (V0.4.1) 加了"主 Claude 直接出 director-schema script.json"路径(`director/prompts/script-system.md`),script-gen 不再是 pipeline 必要前置。`bin/check-health.sh` 也加了 `optional` 字段豁免逻辑(optional=true 的 agent broken 不再升级 overall 状态),整体 director 在没有 ANTHROPIC_API_KEY 时仍可 `overall=ok` 全程出片。

**何时仍需要 script-gen**(下次 reactive 触发):长对话迭代打磨剧本(>3 轮反馈) / SEO 关键词矩阵研究(20 个变体批量) / 离线场景(无 director context 可用)。这些场景出现前不动 script-gen 真调 anthropic 的代码路径。

**回归** — `--version` plain 仍 0.2.1 / `--version --json` 出新 schema(含 optional=true)。无 API 行为变化,所有 cmd_*(new/resume/list/show)与 V0.2.0 一致;只在 health-check 报告层面改语义。

## V0.2.0 — 2026-04-27

**新增** — `youtube` 平台 + YouTube 长视频独立 system prompt(对应 director backlog Q2-B)。

**改动**
- `domain.models.Platform` Literal 加 `"youtube"`(原 3 个仍保留)。新 `Variant = Literal["short", "long", "auto"]` + 新 `Chapter` dataclass(`start_sec / title`)。`Script` 加 3 个 optional 字段:`chapters / seo_title / thumbnail_text`(短视频不传,默认空)。
- `app.prompts` 重构成三层:`ROLE_COMMON` / `OUTPUT_FORMAT_BASE` / `STYLE_SHORT | STYLE_LONG_YT`,前两层字节稳定保 prompt-cache 命中。
- 新 `_is_long_form(platform, duration_sec, variant)`:youtube + (variant==long OR (variant==auto AND duration>60s)) → 长视频 prompt;其它平台一律走 short。
- `app.script_agent.ScriptAgent.__init__` 不再 build 静态 system prompt;`_iterate` 每次按 `session.platform / session.duration_sec` build(同 session 内字节相同,cache 仍命中;resume 时也用对的 prompt)。
- `app.parser.parse_script` 解析新 optional 字段(`.get` 兜底,旧 session 不破)。
- `cli.main` `pnew` 加 `--platform youtube` 选项 + 新 `--variant {short,long,auto}` 标志(默认 auto)。

**长视频 system prompt 关键差异**(STYLE_LONG_YT):15 秒价值承诺 / 3-7 chapter 60-180s/段 / 章节间承上启下钩子句 / 完整书面长句口播 / subtitle 字段在长视频里承载章节标题 / BGM 一段一首不切碎 / SEO title ≤70 字符含 1-2 关键词 / thumbnail_text ≤6 字 / 中段+末段双 CTA。schema 追加字段 `chapters: [{start_sec, title}]` / `seo_title` / `thumbnail_text`。

**回归测试**(代码层面):`_is_long_form` 在 5 个 case 全对(`tiktok 30→F / youtube 60→F (boundary) / youtube 90→T / youtube 30 force long→T / youtube 90 force short→F`)。`--version` plain / `--version --json` 都仍正常。

**为什么** — director (V0.3.x) 加 `yt_landscape` / `yt_short` platform 预设,需要 script-gen 支持 YouTube 平台;长视频与短视频节奏 / SEO / chapter 结构差异大,不能共享 prompt(plan agent + general-purpose subagent 三方一致认定)。

## V0.1.1 — 2026-04-27

**新增** — `--version --json` 健康自检接口(对齐 director maintainer 协议)。

**改动**
- `cli/main.py` 顶部加 `__version__`、`_health_dict()`、`_emit_health_or_version()`。
- 探测 `anthropic` SDK import + `ANTHROPIC_API_KEY` env(都是 critical)。任一缺失 → `healthy=false / severity=broken / exit 2`。
- **关键改动**:`from app.script_agent ...` 和 `from bootstrap.container ...` 从模块顶层下沉到 main() / cmd_* 函数内部。让 `--version --json` 在 anthropic SDK 缺失时仍能输出 broken JSON 报告(否则 anthropic 缺时 import 链直接挂,健康自检永远跑不到)。
- 退出码语义:plain `--version` 仍是 0,`--version --json` 按 `0=healthy / 1=degraded / 2=broken`(对齐 director 协议)。

**为什么** — director (V0.3.0+) 引入统一健康自检。本 patch 是该协议在 script-gen 的实现。**回归风险**:cmd_* 内部 import 增加 ~微秒 cold start,Python module cache 让重复 import 实质零开销;无 API 行为变化。

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
