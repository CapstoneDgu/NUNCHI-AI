#!/usr/bin/env bash

set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"
COUNT="${COUNT:-3}"

echo "BASE_URL=$BASE_URL"
echo "COUNT=$COUNT"
echo

echo "[START] POST /ai/order/start"

START_BODY=$(python - <<'PY'
import json

print(json.dumps({
    "mode": "NORMAL",
    "language": "ko",
    "order_type": "DINE_IN"
}, ensure_ascii=True))
PY
)

START_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/ai/order/start" \
  -H "Content-Type: application/json; charset=utf-8" \
  --data-binary "$START_BODY")

START_RESPONSE_BODY=$(echo "$START_RESPONSE" | sed '$d')
START_STATUS=$(echo "$START_RESPONSE" | tail -n 1)

echo "HTTP_STATUS=$START_STATUS"
echo "$START_RESPONSE_BODY"
echo

if [ "$START_STATUS" != "201" ] && [ "$START_STATUS" != "200" ]; then
  echo "Failed to start order session."
  echo "Check logs/fastapi.log for the root cause."
  exit 1
fi

SESSION_ID=$(python -c "import sys, json; print(json.load(sys.stdin)['session_id'])" <<< "$START_RESPONSE_BODY")

echo "SESSION_ID=$SESSION_ID"
echo

for i in $(seq 1 "$COUNT"); do
  echo "[$i/$COUNT] POST /ai/order/chat"

  CHAT_BODY=$(python - "$SESSION_ID" <<'PY'
import json
import sys

session_id = int(sys.argv[1])

print(json.dumps({
    "session_id": session_id,
    "text": "recommend popular menu",
    "nunchi_signal": None,
    "mode": "NORMAL"
}, ensure_ascii=True))
PY
)

  echo "REQUEST_BODY=$CHAT_BODY"

  CHAT_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/ai/order/chat" \
    -H "Content-Type: application/json; charset=utf-8" \
    --data-binary "$CHAT_BODY")

  CHAT_RESPONSE_BODY=$(echo "$CHAT_RESPONSE" | sed '$d')
  CHAT_STATUS=$(echo "$CHAT_RESPONSE" | tail -n 1)

  echo "HTTP_STATUS=$CHAT_STATUS"
  echo "$CHAT_RESPONSE_BODY"
  echo

  if [ "$CHAT_STATUS" != "200" ]; then
    echo "Chat request failed."
    echo "Check logs/fastapi.log for the root cause."
    exit 1
  fi

  echo "done"
  echo
done