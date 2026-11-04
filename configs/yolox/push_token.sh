#!/bin/bash
# Keep a short-lived Drive access token (rclone remote `gdrive`, drive.readonly) in /content/gdrive_token on the VM,
# so scripts/24 can read the GlareMOT2 zip through the Drive API when the anonymous download quota is used up
# (user's choice, 2026-11-03). Only the access token (valid <= 1 h) leaves this machine; the refresh token stays here
# (~/.config/peg_drive or the rclone config). The token is never printed. Every 2 min: refresh if due, push if changed.
# Run detached:  setsid nohup bash configs/yolox/push_token.sh peg > results/yolox_push_token.log 2>&1 < /dev/null &
# Stops when the session is gone. Remove the token afterwards: ssh ... 'rm -f /content/gdrive_token'.
SESS=${1:-peg}
P=$HOME/Projects/gemma4ever/.local/colab-profiles/${COLAB_PROFILE:-peg3}
SSH=(ssh -i $P/.ssh/id_ed25519 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR
     -o "ProxyCommand=env HOME=$P SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt $HOME/Projects/gemma4ever/.venv/bin/colab --auth=oauth2 ssh --proxy-mode -s $SESS" root@colab)
R=$HOME/.local/bin/rclone
cd "$(dirname "$0")/../.."
last="" fails=0
GPY=$HOME/Projects/gemma4ever/.venv/bin/python
tok() {   # prefer our own OAuth client token (configs/yolox/drive_auth.py); rclone's client shares one rate quota
  if [ -s $HOME/.config/peg_drive/credentials.json ]; then $GPY configs/yolox/drive_auth.py token
  else timeout 60 $R about gdrive: >/dev/null 2>&1
       $R config dump 2>/dev/null | .venv/bin/python -c "import json,sys; print(json.loads(json.load(sys.stdin)['gdrive']['token'])['access_token'])"; fi
}
while true; do
  sig=$(tok 2>/dev/null | sha256sum | cut -c1-12)
  if [ -n "$sig" ] && [ "$sig" != "$last" ]; then
    if tok 2>/dev/null | timeout 90 "${SSH[@]}" 'umask 077; cat > /content/gdrive_token.new && mv /content/gdrive_token.new /content/gdrive_token'; then
      echo "$(date +%T) pushed token ${sig} ($( [ -s $HOME/.config/peg_drive/credentials.json ] && echo own client || echo rclone client))"
      last=$sig; fails=0
    else
      fails=$((fails + 1)); echo "$(date +%T) push failed ($fails)"
      [ $fails -ge 10 ] && { echo "$(date +%T) giving up"; exit 1; }
    fi
  fi
  sleep 120
done
