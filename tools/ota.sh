#!/usr/bin/env bash
# Flash an app over Wi-Fi:  tools/ota.sh [project] [host]
#   project  folder under firmware/ (default boardtest); it is built first
#   host     name or IP (default: firmware/.ota_host, else "surround")
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJ="${1:-boardtest}"
HOST="${2:-$(cat "$ROOT/firmware/.ota_host" 2>/dev/null || echo surround)}"
TOKEN="$(sed -n 's/^#define OTA_TOKEN *"\(.*\)"/\1/p' "$ROOT/firmware/wifi_secrets.h")"
. "${IDF_PATH:-$HOME/esp/esp-idf}/export.sh" >/dev/null 2>&1
idf.py -C "$ROOT/firmware/$PROJ" build | grep -E "error|Project build complete" || true
BIN="$ROOT/firmware/$PROJ/build/$PROJ.bin"
echo "before: $(curl -s --max-time 5 "http://$HOST/status")"
curl -s --max-time 120 -H "X-OTA-Token: $TOKEN" -H "Content-Type: application/octet-stream" \
     --data-binary "@$BIN" "http://$HOST/update"
for i in $(seq 1 30); do
  sleep 2
  if S="$(curl -s --max-time 2 "http://$HOST/status")"; then echo "after:  $S"; echo "$HOST" > "$ROOT/firmware/.ota_host"; exit 0; fi
done
echo "the board did not come back within 60 s (it rolls back by itself if the new image cannot join Wi-Fi)"; exit 1
