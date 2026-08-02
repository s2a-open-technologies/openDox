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
RUN chmod +x /init.sh
ENTRYPOINT ["/init.sh"]
