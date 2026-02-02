---
title: Remote access over the internet
---

If you need to reach TerrariumPI from outside your home network (for example while traveling), use one of the safe patterns below. These options keep your Pi and data protected while still letting you log in from overseas.

## Recommended architecture (temporary access)

### Option A — Private network (recommended)
- **VPN overlay** (Tailscale/ZeroTier) connects your phone/laptop to your home network.
- TerrariumPI stays private (no open ports on your router).
- Lowest cost and easiest to shut down after your vacation.

### Option B — Cloudflare Tunnel (no open ports)
- A lightweight tunnel connects your Pi to Cloudflare.
- You get a public HTTPS URL with Cloudflare Access controls.
- No inbound ports on your router.

### Option C — Reverse proxy with TLS
- Expose ports 80/443 on your router to a reverse proxy (Caddy/Nginx).
- The proxy terminates TLS and forwards to TerrariumPI on port 8090.
- Use strong authentication and rate limiting.

## Security checklist
- Change the default `admin/password` credentials immediately.
- Use a **strong, unique password** and a password manager.
- Use HTTPS only (never expose plain HTTP to the internet).
- Prefer a VPN or a tunnel to avoid direct exposure.
- Keep the OS and TerrariumPI updated.

## Implementation examples
See [contrib/remote-access/README.md](../../contrib/remote-access/README.md) for ready-to-use examples with Cloudflare Tunnel and Caddy.
