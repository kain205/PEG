#!/bin/bash
# Keep a Colab session alive: liveness follows kernel EXEC activity. A long blocking cell and file downloads do not
# count (2026-11-02, account peg3: both kinds of session were reclaimed ~30 min after launch). So run the job detached
# on the VM (nohup setsid) and exec a tiny status cell every few minutes from here (what LifeMate's tools/colab.py does).
# Start it detached from any shell that may be reaped:
#   setsid nohup bash configs/yolox/keepalive.sh peg > results/yolox_keepalive.log 2>&1 < /dev/null &
# Stops when the session is gone, or when /content/PULLED exists on the VM (outputs pulled, ok to stop).
SESS=${1:-peg}; EVERY=${2:-240}
P=$HOME/Projects/gemma4ever/.local/colab-profiles/${COLAB_PROFILE:-peg3}
C="env HOME=$P SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt $HOME/Projects/gemma4ever/.venv/bin/colab --auth=oauth2"
fails=0
while true; do
  out=$(timeout 150 $C exec -s $SESS --timeout 60 2>&1 <<'EOF' | grep '^KA '
import os, subprocess
log = "/content/yx_run.log"
last = subprocess.run(f"tail -1 {log} 2>/dev/null | cut -c1-140", shell=True, capture_output=True, text=True).stdout.strip()
print("KA", "pulled" if os.path.exists("/content/PULLED") else "live", "|", last)
EOF
)
  if [ -n "$out" ]; then
    fails=0; echo "$(date +%T) $out"
    case "$out" in "KA pulled"*) echo "$(date +%T) PULLED marker found, keepalive exits"; exit 0;; esac
  else
    fails=$((fails + 1)); echo "$(date +%T) exec failed ($fails)"
    if ! timeout 60 $C sessions 2>&1 | grep -q "^\[$SESS\]"; then echo "$(date +%T) SESSION_GONE"; exit 1; fi
    [ $fails -ge 6 ] && { echo "$(date +%T) SESSION_UNREACHABLE"; exit 1; }
  fi
  sleep $EVERY
done
