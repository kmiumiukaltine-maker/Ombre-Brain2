#!/usr/bin/env python3
# ============================================================
# SessionStart Hook: auto-breath on session start
# 对话开始钩子：自动浮现最高权重的未解决记忆
#
# On SessionStart, this script calls the Ombre Brain MCP server's
# breath tool (empty query = surfacing mode) via HTTP and prints
# the result to stdout so Claude sees it as session context.
#
# This works for OMBRE_TRANSPORT=streamable-http deployments.
# For local stdio deployments, the script falls back gracefully.
#
# Config:
#   OMBRE_HOOK_URL  — override the server URL (default: http://localhost:8000)
#   OMBRE_HOOK_SKIP — set to "1" to disable the hook temporarily
# ============================================================

import json
import os
import sys
import urllib.request
import urllib.error

def main():
    # Allow disabling the hook via env var
    if os.environ.get("OMBRE_HOOK_SKIP") == "1":
        sys.exit(0)

    base_url = os.environ.get("OMBRE_HOOK_URL", "http://localhost:8000").rstrip("/")

    # Build MCP call via HTTP POST to the streamable-http endpoint
    # The breath tool with no query triggers surfacing mode.
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "breath",
            "arguments": {"query": "", "max_results": 2}
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/mcp",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            raw = response.read().decode("utf-8")
            data = json.loads(raw)
            # Extract text from MCP tool result
            result_content = data.get("result", {}).get("content", [])
            text_parts = [c.get("text", "") for c in result_content if c.get("type") == "text"]
            output = "\n".join(text_parts).strip()
            if output and output != "权重池平静，没有需要处理的记忆。":
                print(f"[Ombre Brain - 记忆浮现]\n{output}")
    except (urllib.error.URLError, OSError):
        # Server not available (local stdio mode or not running) — silent fail
        pass
    except Exception:
        # Any other error — silent fail, never block session start
        pass

    sys.exit(0)

if __name__ == "__main__":
    main()
