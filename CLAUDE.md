# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

**Ombre Brain** is an MCP (Model Context Protocol) server that gives Claude a persistent emotional memory system. Memories are stored as Obsidian-compatible Markdown files with YAML frontmatter, retrieved via dual-channel search (fuzzy keyword + vector semantic), and subject to an Ebbinghaus-based forgetting curve weighted by emotional intensity.

## Commands

### Running Locally

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml
# Edit config.yaml, then:
OMBRE_API_KEY="your-key" python server.py
```

### Running via Docker

```bash
echo "OMBRE_API_KEY=your-key" > .env
docker compose up -d
# Dashboard at http://localhost:18001/dashboard
```

### Testing

```bash
pip install pytest pytest-asyncio

# Run core tests (no API key required)
pytest tests/test_scoring.py tests/test_feel_flow.py -v --asyncio-mode=auto

# Run a single test by keyword
pytest tests/ -k "B01" -v --asyncio-mode=auto

# LLM quality tests (requires OMBRE_API_KEY)
OMBRE_API_KEY="your-key" pytest tests/test_llm_quality.py -v --asyncio-mode=auto
```

### Maintenance Utilities

```bash
python backfill_embeddings.py --batch-size 20   # generate embeddings for existing buckets
python check_buckets.py                          # validate bucket file integrity
python check_icloud_conflicts.py                 # detect iCloud sync conflict markers
python reclassify_domains.py                     # keyword-based domain reclassification
python write_memory.py                           # manual memory insertion (bypasses MCP)
```

## Architecture

### Module Dependency Graph

```
server.py (MCP server + HTTP API + Dashboard, ~1954 lines)
├── bucket_manager.py   — CRUD, fuzzy search, file I/O for .md buckets
│   └── embedding_engine.py  — SQLite-backed vector index, cosine similarity
├── dehydrator.py       — LLM calls for compression, tagging, merging, digestion
├── decay_engine.py     — forgetting curve score calculation + archival
├── import_memory.py    — batch import from Claude/ChatGPT/DeepSeek conversation exports
└── utils.py            — config loading, logging, token counting
```

`server.py` instantiates all managers and passes them around. There is no IoC container; dependencies are explicit constructor arguments.

### Storage Layout

```
buckets/
├── dynamic/            — Normal memories (subject to decay); may contain domain subdirs
├── permanent/          — Pinned memories (no decay)
├── feel/               — Model reflections (excluded from regular search)
└── archive/            — Decayed buckets (score fell below threshold)
```

Each bucket is a Markdown file: YAML frontmatter carries all metadata (`bucket_id`, `name`, `domain`, `valence`, `arousal`, `importance`, `tags`, `activation_count`, `created`, `last_active`, `resolved`, `pinned`, `digested`). The body is compressed natural-language content written by the LLM dehydrator.

Embeddings are cached in `embeddings.db` (SQLite, key = `bucket_id`).

### Search & Scoring Pipeline

`breath(query)` triggers a two-channel search then scores results:

1. **Channel 1 (fuzzy):** RapidFuzz Levenshtein on `name + tags + content`
2. **Channel 2 (semantic):** Cosine similarity on stored embeddings (disabled if `embedding.enabled: false`)
3. **Merge & deduplicate** by `bucket_id`
4. **Score formula:**

```
final_score = topic_relevance(×4.0) + emotion_resonance(×2.0)
            + time_proximity(×1.5) + importance(×1.0)
```

Correct weights are `topic_relevance=4.0, emotion_resonance=2.0, time_proximity=1.5, importance=1.0, content_weight=1.0`. The `buggy_config` fixture in `tests/conftest.py` documents the pre-fix values (time_proximity=2.5, content_weight=3.0) — do not restore those.

### Decay Formula

```
score = importance × (activation_count ^ 0.3) × e^(-λ × days_since_active)
      × combined_emotion_weight(arousal, resolved)
```

Default `λ = 0.05`. Buckets with `score < threshold (0.3)` are moved to `archive/`.

### MCP Tools Exposed to Claude

| Tool | Purpose |
|------|---------|
| `breath` | Surface unresolved memories (no query) or search (with query) |
| `hold` | Store a single memory or model reflection (`feel=true`) |
| `grow` | Batch-digest notes → multiple buckets via LLM |
| `trace` | Edit metadata, mark resolved, or delete a bucket |
| `pulse` | System stats + full bucket listing |
| `dream` | Self-reflection: read recent buckets, crystallize feels |

### HTTP API & Dashboard

`server.py` exposes 17 HTTP endpoints under two auth tiers:
- **Public:** `/health`, `/breath-hook`, `/dream-hook`, `/auth/*`
- **Dashboard-protected:** `/api/buckets`, `/api/bucket/{id}`, `/api/search`, `/api/network`, `/api/breath-debug`, `/api/import/*`, `/api/config`, `/api/status`

`dashboard.html` (63 KB, vanilla JS) is served at `/dashboard` and is the primary management UI.

### Configuration

Runtime behavior is controlled by `config.yaml` (copy from `config.example.yaml`). Every key config value can be overridden by an environment variable — see `ENV_VARS.md` for the full list. Key env vars:

| Variable | Purpose |
|----------|---------|
| `OMBRE_API_KEY` | LLM API key (required for dehydration/tagging) |
| `OMBRE_TRANSPORT` | `stdio` (Claude Desktop) or `streamable-http` (Docker/remote) |
| `OMBRE_PORT` | HTTP listen port (default 8000) |
| `OMBRE_BUCKETS_DIR` | Override bucket storage path |
| `OMBRE_DASHBOARD_PASSWORD` | Pre-set dashboard password |

### SessionStart Hook

`.claude/settings.json` configures a `SessionStart` hook (for both `startup` and `resume` matchers) that runs `.claude/hooks/session_breath.py`. This script calls `/breath-hook` and `/dream-hook` on the running server to auto-surface memories when a Claude Code session opens. The hook requires the server to already be running; it silently skips if the server is unreachable.

## Testing Conventions

- All tests use `tmp_path` fixtures — real bucket data is never touched.
- `mock_dehydrator` and `mock_embedding_engine` fixtures (in `conftest.py`) prevent network calls in integration tests.
- Regression tests are labeled `B-01` through `B-10` and include tests for both correct and intentionally broken behaviour (using `buggy_config`) to document fixed bugs.
- `test_llm_quality.py` makes real API calls and is excluded from CI unless `OMBRE_API_KEY` is set.

## Deployment Notes

- The Docker image is single-stage Python 3.12-slim. The `/app/buckets` volume is where all memory data lives — back this up.
- `docker-compose.yml` includes a Cloudflare Tunnel sidecar for remote access; `docker-compose.user.yml` omits it for simple local use.
- `render.yaml` and `zbpack.json` support one-click deploy to Render and Zeabur respectively.
- CI (`tests.yml`) runs `test_scoring.py` and `test_feel_flow.py` only; LLM quality tests are excluded.
