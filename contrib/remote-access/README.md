# Remote access (temporary public access)

This folder contains minimal, **secure-by-default** examples to reach TerrariumPI remotely while keeping your device safe.

> TerrariumPI runs on port 8090 by default. These examples forward traffic to that local service.

## Option A — Cloudflare Tunnel (no open ports)

**Best for temporary access** without router changes.

1. Create a tunnel in the Cloudflare dashboard.
2. Add a public hostname (e.g., `terrarium.example.com`).
3. Set the service to `http://localhost:8090`.
4. Copy the **tunnel token** Cloudflare provides.

Create a `.env` file next to `docker-compose.cloudflare-tunnel.yml`:

```
CLOUDFLARE_TOKEN=your_token_here
```

Start the tunnel:

```
docker compose -f docker-compose.cloudflare-tunnel.yml up -d
```

Optional: Enable Cloudflare Access (SSO) or IP allow-lists for extra security.

## Option B — Caddy reverse proxy with HTTPS

**Best if you control your router** and want a standard HTTPS setup.

### Requirements
- A domain (e.g., `terrarium.example.com`).
- Router port forwarding **80/443 → your Pi**.

### Steps
1. Create a DNS `A` record pointing your domain to your public IP.
2. Create a `.env` file next to `docker-compose.caddy.yml`:

```
TPI_DOMAIN=terrarium.example.com
TPI_UPSTREAM=host.docker.internal:8090
TPI_AUTH_USER=admin
TPI_AUTH_HASH=$2a$14$REPLACE_WITH_CADDY_HASH
```

3. Generate a bcrypt hash for your password:

```
docker run --rm caddy:2 caddy hash-password --plaintext "your-strong-password"
```

4. Start the proxy:

```
docker compose -f docker-compose.caddy.yml up -d
```

Caddy will automatically fetch and renew TLS certificates.

## Security checklist
- Change the default TerrariumPI credentials.
- Use HTTPS only.
- Prefer a tunnel or VPN if you can.
- Keep your Pi and TerrariumPI updated.
