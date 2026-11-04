#!/bin/bash
# Local side of the cache job: wait for colab_cache.sh to finish (or fail), pull /content/dets as a tar to
# results/yolox_dets_cache/, then release the VM hold (upload /content/PULLED). Partial results are pulled on failure.
SESS=${1:-peg}
OUT=${2:-results/yolox_dets_cache}
P=$HOME/Projects/gemma4ever/.local/colab-profiles/${COLAB_PROFILE:-peg3}
C="env HOME=$P SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt $HOME/Projects/gemma4ever/.venv/bin/colab --auth=oauth2"
SSH="ssh -n -i $P/.ssh/id_ed25519 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ProxyCommand=\"$C ssh --proxy-mode -s $SESS\" root@colab"
mkdir -p $OUT
for i in $(seq 1 120); do
  $C download -s $SESS /content/cache_run.log $OUT/cache_run.log >/dev/null 2>&1
  if grep -q CACHE_TAR_DONE $OUT/cache_run.log 2>/dev/null; then
    $C download -s $SESS /content/dets.tar $OUT/dets.tar >/dev/null 2>&1 && tar tf $OUT/dets.tar > /dev/null \
      && { echo done > $OUT/PULLED; $C upload -s $SESS $OUT/PULLED /content/PULLED >/dev/null 2>&1; echo "$(date +%T) pulled dets.tar, VM released"; exit 0; }
  elif grep -q Traceback $OUT/cache_run.log 2>/dev/null; then
    eval "$SSH 'tar cf /content/dets_partial.tar -C /content dets'"
    $C download -s $SESS /content/dets_partial.tar $OUT/dets_partial.tar >/dev/null 2>&1
    echo "$(date +%T) cache job failed; partial dets pulled (VM kept for resume)"; exit 1
  fi
  sleep 300
done
