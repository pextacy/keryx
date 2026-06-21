#!/usr/bin/env bash
# Kitchen-sink smoke: start the agent and curl EVERY primitive end-to-end, printing a
# PASS/FAIL line per capability. A reviewer one-shot that proves each endpoint settles /
# responds — distinct from capabilities-demo.sh (which drives volume via the fleet). Zero
# funds: everything clears the MockRail. The live dashboard for the same surface is /capabilities.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
PORT="${PORT:-8000}"
URL="http://127.0.0.1:${PORT}"

[ -x "$PY" ] || { echo "Create the venv first: python3.11 -m venv .venv && .venv/bin/pip install -e '.[dev]'"; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "jq required (brew install jq)"; exit 1; }

OWN_AGENT=0
if ! curl -fs "${URL}/healthz" >/dev/null 2>&1; then
  echo "[sink] starting agent on ${URL} ..."
  "$ROOT/.venv/bin/uvicorn" agent.main:app --port "$PORT" --log-level warning >/tmp/keryx_sink.log 2>&1 &
  AGENT_PID=$!
  OWN_AGENT=1
  trap 'kill $AGENT_PID 2>/dev/null || true' EXIT
  for _ in $(seq 1 40); do curl -fs "${URL}/healthz" >/dev/null 2>&1 && break; sleep 0.3; done
fi

PASS=0; FAIL=0
A="0x$(printf 'a%.0s' {1..40})"; B="0x$(printf 'b%.0s' {1..40})"; C="0x$(printf 'c%.0s' {1..40})"
J='content-type:application/json'

# check NAME EXPR  — EXPR is a jq filter that must yield "true" against the response in $RESP.
post() { RESP="$(curl -fs "${URL}$1" -H "$J" -d "$2" 2>/dev/null)"; }
get()  { RESP="$(curl -fs "${URL}$1" 2>/dev/null)"; }
check() {
  local name="$1" filter="$2"
  if [ -n "${RESP:-}" ] && [ "$(printf '%s' "$RESP" | jq -r "$filter" 2>/dev/null)" = "true" ]; then
    printf '  \033[32mPASS\033[0m  %s\n' "$name"; PASS=$((PASS + 1))
  else
    printf '  \033[31mFAIL\033[0m  %s\n' "$name"; FAIL=$((FAIL + 1))
  fi
}

echo "[sink] curling every primitive ..."
post /payout    "{\"amount\":\"0.01\",\"contributors\":[{\"wallet\":\"$A\",\"share\":\"60\"},{\"wallet\":\"$B\",\"share\":\"40\"}]}"; check "payout"            '.total_settled=="0.010000"'
post /royalties "{\"budget\":\"0.01\",\"plays\":[{\"wallet\":\"$A\",\"count\":30}],\"min_count\":1}";                                check "royalties"         '.total_settled!=null'
post /qf        "{\"pool\":\"0.01\",\"projects\":[{\"wallet\":\"$A\",\"contributions\":[\"1\",\"1\"]},{\"wallet\":\"$B\",\"contributions\":[\"4\"]}]}"; check "qf" '.total_matched!=null'
post /retro     "{\"pool\":\"0.01\",\"projects\":[{\"wallet\":\"$A\",\"impact\":40},{\"wallet\":\"$B\",\"impact\":10}]}";              check "retro"             '.|type=="object"'
post /send      "{\"to\":\"$A\",\"amount\":\"0.01\",\"kind\":\"citation\",\"memo\":\"g=0.91\"}";                                       check "send (memo)"       '.settled==true'
post /swap/quote "{\"token_in\":\"USDC\",\"token_out\":\"EURC\",\"amount_in\":\"10\"}";                                               check "swap quote"        '.amount_out!=null'
post /swap      "{\"token_in\":\"USDC\",\"token_out\":\"EURC\",\"amount_in\":\"10\",\"to\":\"$B\"}";                                   check "swap"              '.settled==true'
post /request   "{\"payee\":\"$C\",\"payers\":[\"$A\",\"$B\"],\"total\":\"0.10\"}";                                                    check "request"           '.id!=null'
RID="$(printf '%s' "$RESP" | jq -r .id)"; post "/request/$RID/fulfil" "{\"payer\":\"$A\"}";                                            check "request fulfil"    '.settled!=null'
post /credits/topup "{\"wallet\":\"$A\",\"tier\":\"pro\"}";                                                                            check "credits topup"     '.topped_up==true'
post /credits/spend "{\"wallet\":\"$A\",\"amount\":\"0.001\",\"reason\":\"citation\"}";                                                check "credits spend"     '.spent==true'
post /order     "{\"items\":[{\"description\":\"author\",\"to\":\"$A\",\"amount\":\"0.003\"},{\"description\":\"validator\",\"to\":\"$B\",\"amount\":\"0.002\"}]}"; check "order" '.id!=null'
OID="$(printf '%s' "$RESP" | jq -r .id)"; post "/order/$OID/checkout" "{}";                                                            check "order checkout"    '.status=="paid"'
post /escrow    "{\"client\":\"$A\",\"provider\":\"$B\",\"milestones\":[{\"label\":\"draft\",\"amount\":\"0.01\"}]}";                   check "escrow"            '.id!=null'
EID="$(printf '%s' "$RESP" | jq -r .id)"; post "/escrow/$EID/release" "{\"index\":0}";                                                 check "escrow release"    '.released!=null'
post /schedule  "{\"payer\":\"$A\",\"payee\":\"$B\",\"amount\":\"0.002\",\"runs\":3}";                                                 check "schedule"          '.id!=null'
SID="$(printf '%s' "$RESP" | jq -r .id)"; post "/schedule/$SID/run" "{}";                                                              check "schedule run"      '.ran==true'
post /gateway/deposit "{\"wallet\":\"$A\",\"chain\":\"avalancheFuji\",\"amount\":\"0.5\"}";                                            check "gateway deposit"   '.deposited==true'
post /gateway/spend "{\"wallet\":\"$A\",\"to\":\"$B\",\"amount\":\"0.2\"}";                                                            check "gateway spend"     '.spent==true'
post /bond      "{\"provider\":\"$A\",\"claimant\":\"$B\",\"amount\":\"0.01\"}";                                                       check "bond"              '.bond_id!=null'
BID="$(printf '%s' "$RESP" | jq -r .bond_id)"; post "/bond/$BID/resolve" "{\"passed\":false}";                                         check "bond resolve"      '.status=="slashed"'
post /workflow/approve "{\"intents\":[{\"to\":\"$A\",\"amount\":\"0.01\"}]}";                                                          check "workflow approve"  '.wfid!=null'
post /treasury/sweep "{\"to\":\"$B\"}";                                                                                                check "treasury sweep"    '.swept==true or .error=="nothing to sweep"'
get  /treasury;                                                                                                                        check "treasury read"     '.balance!=null'
get  /balance;                                                                                                                         check "balance"           '.settled!=null'
get  /history;                                                                                                                         check "history"           '.settlements!=null'
get  /capabilities;                                                                                                                    check "capabilities"      '.count>=21'
get  /agent/tools;                                                                                                                     check "agent tools"       '.count>=10'
get  /config;                                                                                                                          check "config economics"  '.economics!=null'

echo
echo "[sink] $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
