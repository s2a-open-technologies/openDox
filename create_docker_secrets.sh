#!/bin/sh
# openDox - Medical transcription platform
# Copyright (C) 2026 S2A Open Technologies gGmbH
#
# Creates all Docker Swarm secrets referenced by docker-swarm.yml. Safe to
# re-run: existing secrets are left untouched (Swarm secrets are immutable —
# to rotate one, remove it with `docker secret rm <name>` and re-run this
# script; removing a secret that's in use by a running stack requires
# updating the stack too, see Docker's docs on secret rotation).
#
# For any secret, set the matching env var before running this script to use
# an existing value instead of generating a new one, e.g.:
#   SQL_PASS=my-existing-db-password ./create_docker_secrets.sh
#
# IMPORTANT: `docker secret inspect` never reveals a secret's value (by
# design) — this script prints freshly generated values ONCE, right after
# creating them. Capture anything you need now; there is no way to retrieve
# it from Docker afterwards short of rotating the secret.
#
# Usage: ./create_docker_secrets.sh
set -e

if [ "$(docker info --format '{{.Swarm.LocalNodeState}}' 2>/dev/null)" != "active" ]; then
    echo "Error: this node is not part of a Docker Swarm. Run 'docker swarm init' first." >&2
    exit 1
fi

CREATED_SUMMARY=""
SKIPPED_SUMMARY=""

# create_secret <docker-secret-name> <value>
create_secret() {
    name="$1"
    value="$2"
    if docker secret inspect "$name" >/dev/null 2>&1; then
        SKIPPED_SUMMARY="${SKIPPED_SUMMARY}  - ${name}\n"
        return
    fi
    printf '%s' "$value" | docker secret create "$name" - >/dev/null
    CREATED_SUMMARY="${CREATED_SUMMARY}  - ${name} = ${value}\n"
}

# Random hex string of <n> bytes — safe for URLs/connection strings/CLI args.
generate_hex() {
    openssl rand -hex "$1"
}

# A Fernet key is urlsafe-base64(32 random bytes) — exactly what
# cryptography.fernet.Fernet.generate_key() produces, replicated here with
# openssl so this script has no Python dependency.
generate_fernet_key() {
    openssl rand -base64 32 | tr '+/' '-_'
}

echo "Creating openDox Docker Swarm secrets..."
echo

create_secret opendox_secret_key       "${SECRET_KEY:-$(generate_hex 32)}"
create_secret opendox_encryption_key   "${ENCRYPTION_KEY:-$(generate_fernet_key)}"
create_secret opendox_sql_pass         "${SQL_PASS:-$(generate_hex 24)}"
create_secret opendox_whisper_api_key  "${WHISPER_API_KEY:-$(generate_hex 24)}"
create_secret opendox_parakeet_api_key "${PARAKEET_API_KEY:-$(generate_hex 24)}"

# S3-compatible object storage (persisted audio downloads). Key ID must match
# Garage's required format: "GK" + 24 hex chars.
create_secret opendox_s3_access_key_id     "${S3_ACCESS_KEY_ID:-GK$(generate_hex 12)}"
create_secret opendox_s3_secret_access_key "${S3_SECRET_ACCESS_KEY:-$(generate_hex 32)}"

# Garage's own RPC secret (exactly 32 bytes hex) and admin API token.
create_secret opendox_garage_rpc_secret   "${GARAGE_RPC_SECRET:-$(generate_hex 32)}"
create_secret opendox_garage_admin_token  "${GARAGE_ADMIN_TOKEN:-$(generate_hex 32)}"

# opendox_encryption_key_previous is NOT created by default — it only makes
# sense as a real prior ENCRYPTION_KEY value during an active key rotation
# (backend/components/security/key_rotation.py), never a random one. Opt in
# by exporting ENCRYPTION_KEY_PREVIOUS before running this script, see
# docker-swarm.rotation.yml for the deploy-time overlay that wires it in.
ROTATION_SECRET_NOTE=""
if [ -n "$ENCRYPTION_KEY_PREVIOUS" ]; then
    create_secret opendox_encryption_key_previous "$ENCRYPTION_KEY_PREVIOUS"
else
    ROTATION_SECRET_NOTE="1"
fi

echo "Done."

if [ -n "$CREATED_SUMMARY" ]; then
    echo
    echo "############################################################"
    echo "# NEWLY CREATED — these values are shown ONE TIME ONLY.    #"
    echo "# Docker cannot show them to you again after this.         #"
    echo "############################################################"
    printf "%b" "$CREATED_SUMMARY"
fi

if [ -n "$SKIPPED_SUMMARY" ]; then
    echo
    echo "Already existed, left untouched (values not shown):"
    printf "%b" "$SKIPPED_SUMMARY"
fi

if [ -n "$ROTATION_SECRET_NOTE" ]; then
    echo
    echo "Note: opendox_encryption_key_previous was not created (no active key"
    echo "rotation). To rotate ENCRYPTION_KEY later, see docker-swarm.rotation.yml."
fi

echo
echo "Next: docker stack deploy -c docker-swarm.yml opendox"
