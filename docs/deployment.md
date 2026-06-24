# Deployment Options

Serein does not require Docker or Caddy. The current Compose file is a
convenient static-frontend example for development and self-hosting.

## Option 1: Docker Compose + Caddy

From the repository root:

```bash
docker compose up -d web
```

The example binds only to `127.0.0.1:8088`. Open
`http://127.0.0.1:8088` on the host. It serves only `frontend/`; it has no API,
authentication, data volume, or dependency on a server-wide Caddy instance.

## Option 2: Any static server

`frontend/` is plain HTML, CSS, and JavaScript. It can be served by an existing
Nginx, Caddy, Apache, development server, or static hosting provider without
Docker. In the current static phase, no special server rewrite or proxy rule is
required.

## Later application deployment

P3 will add a separate API service and an optional `/api/v1/*` reverse-proxy
rule to the Compose example. This remains a deployment convenience, not a
frontend or backend runtime dependency: operators may use another container
runtime, a process manager, or an existing reverse proxy.
