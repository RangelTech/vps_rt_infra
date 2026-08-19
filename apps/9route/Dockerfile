# SUPERSEDED (infra-08, 2026-08-19): the `ninerouter` compose service now
# builds directly from the 9router-multitenant fork's own git repo (a git
# build context in compose/docker-compose.yml), using that repo's own
# Dockerfile — not this file. This installs the abandoned npm-package
# flavor of 9router (single-tenant, no multi-tenant schema) and is kept
# only for historical reference; it is not referenced by any compose
# service. Do not build this for the multitenant deploy.
#
# 9route (9router) container image.
#
# 9router is distributed as a global npm package (confirmed: `9router@0.5.40`,
# installed today via `npm i -g 9router` and run locally through 9router.bat).
# It serves a web dashboard/UI (observed on localhost:20128) plus its proxy API.
#
# Build:
#   docker build --build-arg NINEROUTER_PACKAGE=9router@0.5.40 -t vps-rt-infra/9route .
#
# The exact port and any required env vars/config volume should be double
# checked against the package's own README the first time this is built,
# since the CLI may expose extra flags (--port, --config, etc.).

ARG NINEROUTER_PACKAGE=9router@0.5.40
FROM node:20-slim AS runtime

ARG NINEROUTER_PACKAGE
ENV NINEROUTER_PACKAGE=${NINEROUTER_PACKAGE}

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g "${NINEROUTER_PACKAGE}" \
    && npm cache clean --force

# Persistent data (skills, provider configs, sqlite state, logs, etc.)
RUN mkdir -p /data
VOLUME ["/data"]

ENV NINEROUTER_HOME=/data
ENV PORT=20128
EXPOSE 20128

# Non-root execution
RUN useradd -m -u 10001 ninerouter && chown -R ninerouter:ninerouter /data
USER ninerouter

HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/" || exit 1

ENTRYPOINT ["9router"]
