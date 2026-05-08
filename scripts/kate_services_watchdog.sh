#!/usr/bin/env bash
set -euo pipefail

LOG=/opt/data/logs/kate_services_watchdog.log
mkdir -p /opt/data/logs /opt/data/scripts /opt/data/bin

ts() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

PY=/opt/hermes/.venv/bin/python3
VOICE=/opt/data/voice_interface/server.py
VOICE_LOG=/tmp/kate_voice.log
MEM_BIN=/opt/hermes/.venv/bin/mempalace-mcp
MEM_PALACE=/opt/data/mempalace
CLOUDFLARED=/opt/data/bin/cloudflared
CLOUDFLARED_LOG=/tmp/kate_cloudflared.log
CLOUDFLARED_URL_FILE=/opt/data/voice_interface/cloudflare_url.txt

voice_http_ok() {
  command -v curl >/dev/null 2>&1 && curl -fsS --max-time 4 http://localhost:8765/ >/dev/null 2>&1
}

voice_pids() {
  # Match only real Python server processes, not shell commands containing the path.
  ps -eo pid=,comm=,args= | awk -v voice="$VOICE" '$2 ~ /^python/ && index($0, voice) {print $1}'
}

cloudflared_pids() {
  ps -eo pid=,comm=,args= | awk '$2 ~ /^cloudflared/ && index($0, "tunnel") && index($0, "http://localhost:8765") {print $1}'
}

extract_cf_url() {
  grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$CLOUDFLARED_LOG" 2>/dev/null | tail -1 || true
}

start_voice() {
  log "starting Kate voice interface"
  nohup "$PY" "$VOICE" > "$VOICE_LOG" 2>&1 &
  sleep 4
  if voice_http_ok; then
    log "voice interface started OK"
  else
    log "WARNING voice interface start attempted but HTTP check still failed; see $VOICE_LOG"
  fi
}

ensure_cloudflared_binary() {
  if [ ! -x "$CLOUDFLARED" ]; then
    log "cloudflared missing; downloading persistent binary"
    curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o "$CLOUDFLARED"
    chmod +x "$CLOUDFLARED"
  fi
}

start_cloudflared() {
  ensure_cloudflared_binary
  log "starting Cloudflare quick tunnel for Kate voice interface"
  : > "$CLOUDFLARED_LOG"
  nohup "$CLOUDFLARED" tunnel --url http://localhost:8765 --no-autoupdate > "$CLOUDFLARED_LOG" 2>&1 &
  sleep 8
  URL="$(extract_cf_url)"
  if [ -n "$URL" ]; then
    echo "$URL" > "$CLOUDFLARED_URL_FILE"
    log "cloudflare tunnel started OK: $URL"
  else
    log "WARNING cloudflare tunnel start attempted but no URL found; see $CLOUDFLARED_LOG"
  fi
}

# 1) Kate voice web interface on localhost:8765
if [ -f "$VOICE" ]; then
  if voice_http_ok; then
    log "voice interface OK on :8765"
  else
    PIDS="$(voice_pids || true)"
    if [ -n "$PIDS" ]; then
      log "voice HTTP failed; killing stale voice process(es): $PIDS"
      kill $PIDS >/dev/null 2>&1 || true
      sleep 2
    else
      log "voice HTTP failed and no real voice process found"
    fi
    start_voice
  fi
else
  log "WARNING voice server file missing: $VOICE"
fi

# 2) Cloudflare tunnel for public HTTPS/WSS access
if voice_http_ok; then
  CF_PIDS="$(cloudflared_pids || true)"
  CF_URL="$(extract_cf_url)"
  if [ -n "$CF_PIDS" ] && [ -n "$CF_URL" ]; then
    echo "$CF_URL" > "$CLOUDFLARED_URL_FILE"
    log "cloudflare tunnel OK: $CF_URL"
  else
    if [ -n "$CF_PIDS" ]; then
      log "cloudflare process exists but URL missing; killing stale tunnel(s): $CF_PIDS"
      kill $CF_PIDS >/dev/null 2>&1 || true
      sleep 2
    else
      log "cloudflare tunnel not running"
    fi
    start_cloudflared
  fi
else
  log "WARNING skipping cloudflare tunnel because voice interface is not healthy"
fi

# 3) MemPalace backend sanity check — MCP itself is managed by Hermes, but the binary/db must exist.
if [ -x "$MEM_BIN" ] && [ -f "$MEM_PALACE/chroma.sqlite3" ]; then
  log "mempalace backend OK"
else
  log "WARNING mempalace backend incomplete: bin=$([ -x "$MEM_BIN" ] && echo OK || echo MISSING), db=$([ -f "$MEM_PALACE/chroma.sqlite3" ] && echo OK || echo MISSING)"
fi

# 4) Config sanity checks for model routing and memory limits.
if grep -q 'deepseek/deepseek-v4-pro' /opt/data/config.yaml 2>/dev/null; then
  log "DeepSeek V4 Pro config OK"
else
  log "WARNING DeepSeek V4 Pro not found in config"
fi

exit 0
