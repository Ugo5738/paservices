#!/usr/bin/env bash
set -euo pipefail

# Optional positional arg or env SUPER_ID to fetch result only (no trigger)
SUPER_ID_INPUT=${1:-${SUPER_ID:-""}}

# ---- Config (override via env) ----
LANGGRAPH_CLIENT_ID=${LANGGRAPH_CLIENT_ID:-"m2m_103546365241459213"}
LANGGRAPH_CLIENT_SECRET=${LANGGRAPH_CLIENT_SECRET:-"test_DeCQKgoGNnGoq2N12wYL4ThuaTUHkJBMDoORaQ20QUfksV1ekDBtBesKvK81t3HK"}
SCOPE=${SCOPE:-"users:analyze"}
AUDIENCE=${AUDIENCE:-"https://mcp.supersami.com/mcp"}
TOKEN_URL=${TOKEN_URL:-"https://supersoftco.scalekit.dev/oauth/token"}

MCP_URL=${MCP_URL:-"https://mcp.supersami.com/mcp"}
PROPERTY_URL=${PROPERTY_URL:-"https://www.rightmove.co.uk/properties/169034390"} 
WORKFLOW_CB=${WORKFLOW_CB:-"https://mcp.supersami.com/api/analysis/callback"}
EXTERNAL_CB=${EXTERNAL_CB:-"https://mcp.supersami.com/api/analysis/callback"}

if [[ -z "${LANGGRAPH_CLIENT_SECRET}" || "${LANGGRAPH_CLIENT_SECRET}" == "REPLACE_ME" ]]; then
  echo "LANGGRAPH_CLIENT_SECRET is not set. Export it and rerun." >&2
  exit 1
fi

ACCEPT_HEADER='application/json, text/event-stream'

echo "Fetching ACCESS_TOKEN..."
TOKEN_JSON="$(curl -sS -X POST "${TOKEN_URL}" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "grant_type=client_credentials" \
  --data-urlencode "client_id=${LANGGRAPH_CLIENT_ID}" \
  --data-urlencode "client_secret=${LANGGRAPH_CLIENT_SECRET}" \
  --data-urlencode "scope=${SCOPE}" \
  --data-urlencode "audience=${AUDIENCE}")"

ACCESS_TOKEN="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("access_token",""))' "$TOKEN_JSON")"

if [[ -z "${ACCESS_TOKEN}" ]]; then
  echo "Failed to obtain ACCESS_TOKEN. Raw response:" >&2
  echo "$TOKEN_JSON" >&2
  exit 1
fi
echo "ACCESS_TOKEN acquired."

# If SUPER_ID_INPUT provided, fetch result via MCP tool and exit
if [[ -n "${SUPER_ID_INPUT}" ]]; then
  echo "Fetching analysis result via MCP tool for SUPER_ID=${SUPER_ID_INPUT}..."
  # Initialize a short-lived session for the tool call
  SESSION_ID=$(curl -s -D - -o /dev/null "$MCP_URL" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Accept: $ACCEPT_HEADER" \
    -H "Content-Type: application/json" \
    --data '{
      "jsonrpc": "2.0",
      "id": 1,
      "method": "initialize",
      "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": { "name": "curl-tool-call", "version": "0.0.1" }
      }
    }' | awk -F': ' 'tolower($1)=="mcp-session-id" {print $2}' | tr -d "\r")

  if [[ -z "${SESSION_ID}" ]]; then
    echo "Failed to obtain SESSION_ID for tool call." >&2
    exit 1
  fi

  # Send notifications/initialized to complete setup
  curl -sS -X POST "$MCP_URL" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Mcp-Session-Id: $SESSION_ID" \
    -H "Accept: $ACCEPT_HEADER" \
    -H "Content-Type: application/json" \
    --data '{
      "jsonrpc": "2.0",
      "method": "notifications/initialized",
      "params": {}
    }' >/dev/null

  # Call the result tool
  curl -sS -X POST "$MCP_URL" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -H "Mcp-Session-Id: $SESSION_ID" \
    -H "Accept: $ACCEPT_HEADER" \
    -H "Content-Type: application/json" \
    --data '{
      "jsonrpc": "2.0",
      "id": 2,
      "method": "tools/call",
      "params": {
        "name": "get_property_analysis_result_tool",
        "arguments": { "super_id": "'"$SUPER_ID_INPUT"'" },
        "stream": false
      }
    }'
  echo
  exit 0
fi

echo "Initializing MCP session..."
HDRS_FILE="$(mktemp)"
BODY_FILE="$(mktemp)"

HTTP_CODE="$(curl -sS -w "%{http_code}" -D "$HDRS_FILE" -o "$BODY_FILE" -X POST "$MCP_URL" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Accept: $ACCEPT_HEADER" \
  -H "Content-Type: application/json" \
  --data '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-06-18",
      "capabilities": {},
      "clientInfo": { "name": "curl-test", "version": "0.0.1" }
    }
  }')"

SESSION_ID="$(awk -F': ' 'tolower($1)=="mcp-session-id" {print $2}' "$HDRS_FILE" | tr -d "\r")"

echo "HTTP $HTTP_CODE"
echo "SESSION_ID=${SESSION_ID:-<none>}"

if [[ -z "${SESSION_ID:-}" ]]; then
  echo "Failed to obtain SESSION_ID from initialize response headers." >&2
  echo "Headers:" >&2; cat "$HDRS_FILE" >&2
  echo "Body:" >&2; cat "$BODY_FILE" >&2
  exit 1
fi

# Try to validate JSON only if Content-Type looks like JSON and body is non-empty
CONTENT_TYPE="$(awk -F': ' 'tolower($1)=="content-type" {print tolower($2)}' "$HDRS_FILE" | tr -d "\r" | tail -n 1)"
if [[ -s "$BODY_FILE" && "$CONTENT_TYPE" == *"application/json"* ]]; then
  python3 - <<'PY' "$BODY_FILE"
import json,sys
p=sys.argv[1]
d=json.load(open(p))
if "error" in d:
    raise SystemExit(f"Initialize returned error: {d['error']}")
if "result" not in d:
    raise SystemExit(f"Initialize missing result: {d}")
print("Initialize OK")
PY
else
  # Not fatal; some servers may return empty body while still setting session header
  echo "Initialize body not JSON (Content-Type: ${CONTENT_TYPE:-unknown}). Continuing..."
fi

echo "Sending notifications/initialized..."
curl -sS -X POST "$MCP_URL" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -H "Accept: $ACCEPT_HEADER" \
  -H "Content-Type: application/json" \
  --data '{
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
    "params": {}
  }' >/dev/null

echo "Calling trigger_full_property_analysis_tool..."
TRIGGER_RESP="$(curl -sS -X POST "$MCP_URL" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Mcp-Session-Id: $SESSION_ID" \
  -H "Accept: $ACCEPT_HEADER" \
  -H "Content-Type: application/json" \
  --data '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "trigger_full_property_analysis_tool",
      "arguments": {
        "property_url": "'"$PROPERTY_URL"'",
        "callback_urls": {
          "workflow_callback_url": "'"$WORKFLOW_CB"'",
          "external_callback_url": "'"$EXTERNAL_CB"'"
        }
      },
      "stream": false
    }
  }')"

echo "Trigger response:"
echo "$TRIGGER_RESP"

# Extract super_id from trigger response (best-effort)
SUPER_ID="$(python3 - <<'PY'
import json, re, sys
raw = sys.stdin.read()
try:
    obj = json.loads(raw)
except Exception:
    # If event-stream or other format, try to pull JSON after a "data:" prefix
    m = re.search(r'data:\s*({.*})', raw)
    if not m:
        sys.exit(0)
    try:
        obj = json.loads(m.group(1))
    except Exception:
        sys.exit(0)

if not isinstance(obj, dict):
    sys.exit(0)

result = obj.get("result") if isinstance(obj, dict) else None
# try structuredContent.result first
if isinstance(result, dict):
    sc = result.get("structuredContent", {})
    if isinstance(sc, dict):
        res_text = sc.get("result")
        if isinstance(res_text, str):
            m = re.search(r'"super_id"\s*:\s*"([^"]+)"', res_text)
            if m:
                print(m.group(1))
                sys.exit(0)
    # fallback: content text
    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                t = item.get("text", "")
                m = re.search(r'"super_id"\s*:\s*"([^"]+)"', t)
                if m:
                    print(m.group(1))
                    sys.exit(0)
sys.exit(0)
PY
<<< "$TRIGGER_RESP")"

if [[ -n "$SUPER_ID" ]]; then
  echo "Extracted SUPER_ID=$SUPER_ID"
  echo "No result fetch performed. Use this super_id later to fetch the result via the MCP tool."
else
  echo "Could not extract super_id from trigger response. Inspect the response above."
fi

echo "Done."
rm -f "$HDRS_FILE" "$BODY_FILE"


# ./commands_mcp.sh # run trigger mcp tool
# ./commands_mcp.sh f85e20a6-4186-4f66-956b-d0b9d5ead786
# https://www.rightmove.co.uk/properties/170260643#/?channel=RES_LET


# docker compose -f docker-compose.prod.yml logs floorplan_service | grep 8ed74a31-b29e-4d79-b555-752dfc4a038c | grep -E "WEBHOOK_RECEIVED|Inbound request: floorplan webhook"