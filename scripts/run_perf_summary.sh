#!/usr/bin/env bash

set -e

FASTAPI_LOG="${FASTAPI_LOG:-logs/fastapi.log}"
MCP_LOG="${MCP_LOG:-logs/mcp.log}"

echo "========================================"
echo "NUNCHI AI Performance Summary"
echo "========================================"

python scripts/summary_ai_steps.py "$FASTAPI_LOG"
echo
python scripts/summary_mcp_tools.py "$MCP_LOG"