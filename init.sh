#!/usr/bin/env bash
set -euo pipefail

source env.sh

tunnel-client init \
  --profile harness \
  --tunnel-id "$CONTROL_PLANE_TUNNEL_ID" \
  --mcp-server-url "$MCP_SERVER_URL" \
  --force
