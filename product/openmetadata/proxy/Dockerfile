# Stock Caddy plus replace-response, which injects static/ into OpenMetadata's HTML.
FROM caddy:2.10.2-builder AS build
ENV CGO_ENABLED=0
RUN xcaddy build v2.10.2 --output /usr/bin/caddy \
    --with github.com/caddyserver/replace-response@v0.0.0-20250618171559-80962887e4c6

FROM caddy:2.10.2
COPY --from=build /usr/bin/caddy /usr/bin/caddy
