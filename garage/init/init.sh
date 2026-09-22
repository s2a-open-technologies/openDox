#!/bin/sh
# Idempotent one-time setup for a single-node Garage cluster: assigns the
# node its storage layout, creates the audio bucket, imports a fixed dev S3
# key, and grants it access. Safe to run on every `docker compose up`.
set -e

# Same "_FILE suffix wins" convention as backend/components/modules/env.py's
# env_or_file() — lets these be supplied as Docker/Swarm secrets. The _FILE
# vars are unset afterwards: the garage CLI itself also recognizes
# GARAGE_RPC_SECRET_FILE and refuses to start if it's set at the same time
# as an explicit --rpc-secret flag ("only one of rpc_secret and
# rpc_secret_file can be set").
[ -n "$GARAGE_ADMIN_TOKEN_FILE" ] && GARAGE_ADMIN_TOKEN=$(cat "$GARAGE_ADMIN_TOKEN_FILE") && unset GARAGE_ADMIN_TOKEN_FILE
[ -n "$GARAGE_RPC_SECRET_FILE" ] && GARAGE_RPC_SECRET=$(cat "$GARAGE_RPC_SECRET_FILE") && unset GARAGE_RPC_SECRET_FILE
[ -n "$GARAGE_KEY_ID_FILE" ] && GARAGE_KEY_ID=$(cat "$GARAGE_KEY_ID_FILE") && unset GARAGE_KEY_ID_FILE
[ -n "$GARAGE_KEY_SECRET_FILE" ] && GARAGE_KEY_SECRET=$(cat "$GARAGE_KEY_SECRET_FILE") && unset GARAGE_KEY_SECRET_FILE

GARAGE_HOST="${GARAGE_HOST:-garage}"
ADMIN_URL="http://${GARAGE_HOST}:3903"

echo "[garage-init] Waiting for Garage admin API at ${ADMIN_URL}..."
ATTEMPTS=0
MAX_ATTEMPTS="${GARAGE_INIT_MAX_WAIT:-60}"
until curl -sf "${ADMIN_URL}/health" >/dev/null 2>&1; do
  ATTEMPTS=$((ATTEMPTS + 1))
  if [ "$ATTEMPTS" -ge "$MAX_ATTEMPTS" ]; then
    echo "[garage-init] ERROR: Garage admin API not reachable after ${MAX_ATTEMPTS}s, giving up (will be retried by the container's restart policy)." >&2
    exit 1
  fi
  [ $((ATTEMPTS % 5)) -eq 0 ] && echo "[garage-init] still waiting... (${ATTEMPTS}s)"
  sleep 1
done
echo "[garage-init] Garage admin API is up (after ${ATTEMPTS}s)."

NODE_ID=$(curl -s -H "Authorization: Bearer ${GARAGE_ADMIN_TOKEN}" "${ADMIN_URL}/v1/status" | jq -r '.node')
echo "[garage-init] Node ID: $NODE_ID"

garage() {
  /usr/local/bin/garage --rpc-host "${NODE_ID}@${GARAGE_HOST}:3901" --rpc-secret "${GARAGE_RPC_SECRET}" "$@"
}

if garage status 2>&1 | grep -q "NO ROLE ASSIGNED"; then
  echo "[garage-init] Assigning layout..."
  garage layout assign -z dc1 -c "${GARAGE_CAPACITY:-10G}" "$NODE_ID"
  APPLY_CMD=$(garage layout show 2>&1 | grep -oE 'layout apply --version [0-9]+' | tail -1)
  echo "[garage-init] $APPLY_CMD"
  garage $APPLY_CMD
else
  echo "[garage-init] Layout already assigned, skipping."
fi

if ! garage bucket list 2>&1 | awk '{print $1}' | grep -qx "$GARAGE_BUCKET"; then
  echo "[garage-init] Creating bucket $GARAGE_BUCKET..."
  garage bucket create "$GARAGE_BUCKET"
else
  echo "[garage-init] Bucket already exists, skipping."
fi

if ! garage key list 2>&1 | awk '{print $1}' | grep -qx "$GARAGE_KEY_ID"; then
  echo "[garage-init] Importing dev S3 key..."
  garage key import "$GARAGE_KEY_ID" "$GARAGE_KEY_SECRET" --yes -n opendox-app
else
  echo "[garage-init] Key already imported, skipping."
fi

garage bucket allow --read --write --owner "$GARAGE_BUCKET" --key "$GARAGE_KEY_ID"

echo "[garage-init] Garage ready."
