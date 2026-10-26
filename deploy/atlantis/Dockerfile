# Prepared configuration; build and scan before deploying. No server is deployed by CI.
FROM ghcr.io/runatlantis/atlantis:v0.48.2 AS upstream
FROM python:3.11.17-slim-trixie@sha256:b7a9e5f6a93d6d4a31f129bbd4bdee69efccb6ded0fb230d78aafaf37af98377
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir awscli==1.42.51 \
    && useradd --uid 1000 --create-home atlantis \
    && mkdir -p /atlantis-data /opt/atlantis && chown atlantis:atlantis /atlantis-data
COPY --from=upstream /usr/local/bin/atlantis /usr/local/bin/atlantis
COPY deploy/atlantis/server.yaml deploy/atlantis/repos.yaml deploy/atlantis/plan-summary.sh /opt/atlantis/
COPY scripts/ci-trigger.py scripts/ci_common.py /opt/atlantis/
USER 1000
EXPOSE 4141
ENTRYPOINT ["atlantis"]
CMD ["server", "--config=/opt/atlantis/server.yaml"]
