#  openDox - Garage object storage init helper
#  Copyright (C) 2025 Christopher Abanilla <christopher.abanilla@gmx.de>
#  SPDX-FileCopyrightText: 2025 Christopher Abanilla <christopher.abanilla@gmx.de>
#  SPDX-License-Identifier: AGPL-3.0-or-later
#
# Small helper image that runs a one-shot idempotent Garage setup
# (cluster layout, bucket, S3 access key) against the `garage` service.
# The upstream dxflrs/garage image ships only the static `garage` binary
# with no shell — this stage copies that binary onto a shell-capable Alpine
# base so init.sh can run.
FROM dxflrs/garage:v1.0.1 AS garage-bin

FROM alpine:3.20
RUN apk add --no-cache curl jq
COPY --from=garage-bin /garage /usr/local/bin/garage
COPY init.sh /init.sh
# Unprivileged runtime user (UID/GID 1000) — the init script only reads its
# secrets (Docker/Swarm mount them world-readable at /run/secrets), talks to
# the Garage admin API over HTTP, and needs no local writes, so root is not
# required. Named appuser for parity with the other openDox images.
RUN adduser --no-create-home --uid 1000 -D appuser \
    && chmod +x /init.sh
USER appuser
ENTRYPOINT ["/init.sh"]
