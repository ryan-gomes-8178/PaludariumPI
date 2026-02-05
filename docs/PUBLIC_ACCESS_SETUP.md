# TerrariumPI Public Access & Security Setup Guide

This guide provides step-by-step instructions to securely expose TerrariumPI to the internet with authentication, 2FA, and SSL/TLS encryption.

## Overview

This setup provides:
- **SSL/TLS Encryption**: All traffic encrypted in transit
- **Strong Authentication**: Bcrypt password hashing + optional 2FA (TOTP)
- **Rate Limiting**: Protection against brute force attacks
- **Security Headers**: XSS, clickjacking, and content sniffing protection
- **Session Management**: Secure session tokens with timeout
- **Reverse Proxy**: Nginx acts as security buffer between internet and application

## Important: HTTP vs HTTPS

**Session cookies are configured to automatically adapt to your connection type:**
- **HTTPS connections**: Session cookies use the `secure` flag for maximum security
- **HTTP connections**: Session cookies work without the `secure` flag for local testing

**Recommendations:**
- ✅ **Production use**: Always use HTTPS with a valid SSL certificate (see setup steps below)
- ⚠️ **Local testing**: HTTP will work but is not secure and should only be used on trusted networks
- 🚫 **Never expose HTTP endpoints to the public internet** - always use HTTPS for public access

## Prerequisites

Before starting, ensure you have:
- A domain name (e.g., terrariumpi.example.com)
- A server/Raspberry Pi with public IP or port forwarding capabilities
- SSH access to your server
- Basic familiarity with Linux commands
- SSL certificate (free option: Let's Encrypt)

## Step 1: Acquire a Domain Name

### Option A: Purchase a Domain
1. Use registrars like:
   - Namecheap.com
   - GoDaddy.com
   - Google Domains
   - Cloudflare.com (also provides free DNS)

2. Choose a domain name (e.g., `terrariumpi.example.com`)

3. Update DNS records to point to your server's public IP address:
   - **DNS Record Type**: A (for IPv4) or AAAA (for IPv6)
   - **Name**: terrariumpi (or subdomain of choice)
   - **Value**: Your server's public IP address
   - **TTL**: 3600 seconds (1 hour)

### Verify DNS Resolution
```bash
# Should resolve to your public IP
nslookup terrariumpi.example.com
# or
dig terrariumpi.example.com
```

## Step 2: Install and Configure Nginx

### Install Nginx
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y nginx

# Start and enable Nginx
sudo systemctl start nginx
sudo systemctl enable nginx
```

### Configure Nginx as Reverse Proxy
1. Copy the provided nginx configuration:
```bash
sudo cp contrib/nginx_terrariumpi.conf /etc/nginx/sites-available/terrariumpi
```

2. Edit the configuration file:
```bash
sudo nano /etc/nginx/sites-available/terrariumpi
```

3. Replace these placeholders:
   - `YOUR_DOMAIN.COM` → your actual domain (e.g., terrariumpi.example.com)
   - `192.168.1.X:8080` → your TerrariumPI server's local IP and port
   - `/path/to/ssl/cert.pem` → path to SSL certificate (we'll create this next)
   - `/path/to/ssl/key.pem` → path to SSL private key

4. Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/terrariumpi /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # Remove default site if needed
```

5. Test nginx configuration:
```bash
sudo nginx -t
```

6. Reload nginx (we'll do final restart after SSL setup):
```bash
sudo systemctl reload nginx
```

## Step 3: Obtain SSL/TLS Certificate

### Option A: Let's Encrypt (FREE and Recommended)

**Install Certbot:**
```bash
sudo apt-get install -y certbot python3-certbot-nginx
```

**Obtain Certificate:**
```bash
sudo certbot certonly --nginx -d terrariumpi.example.com -d www.terrariumpi.example.com
```

**Certificate locations will be:**
- Certificate: `/etc/letsencrypt/live/terrariumpi.example.com/fullchain.pem`
- Private Key: `/etc/letsencrypt/live/terrariumpi.example.com/privkey.pem`

**Update Nginx configuration with certificate paths:**
```bash
ssl_certificate /etc/letsencrypt/live/terrariumpi.example.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/terrariumpi.example.com/privkey.pem;
```

**Setup Auto-Renewal:**
```bash
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

# Verify timer is active
sudo systemctl status certbot.timer
```

### Option B: Self-Signed Certificate (NOT recommended for production)

**Generate self-signed certificate:**
```bash
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/terrariumpi-key.pem \
  -out /etc/ssl/certs/terrariumpi-cert.pem
```

⚠️ **Warning**: Self-signed certificates will show warnings in browsers and should only be used for testing.

## Step 4: Set Up Port Forwarding

If your TerrariumPI is behind a home router:

1. **Log into your router's admin interface** (usually 192.168.1.1 or 192.168.0.1)

2. **Find Port Forwarding settings** (may be under NAT, Port Mapping, or Virtual Server)

3. **Forward these ports to the TerrariumPI host's LAN IP** (the device running Nginx):
   - External Port: 80 → Internal IP: <terrariumpi-lan-ip>, Internal Port: 80
   - External Port: 443 → Internal IP: <terrariumpi-lan-ip>, Internal Port: 443

4. **Find your public IP address:**
   ```bash
   curl https://ipinfo.io/ip
   # or visit https://whatismyipaddress.com
   ```

5. **Update your domain's DNS A record to point to your public IP**

## Step 5: Update Requirements and Enable 2FA

### Update Python Dependencies
```bash
pip install -r requirements.txt
```

### Enable 2FA in TerrariumPI Settings

After the update, access your TerrariumPI web interface and:

1. Go to Settings → Security
2. Enable "Require 2FA Authentication"
3. Scan the QR code with an authenticator app:
   - Google Authenticator
   - Authy
   - Microsoft Authenticator
   - FreeOTP
4. Save and test login with 2FA

## Step 6: Set Up Firewall

### UFW (Ubuntu/Debian)
```bash
# Enable firewall
sudo ufw enable

# Allow SSH (important to not lock yourself out!)
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow TerrariumPI local port (only if needed for debugging)
# sudo ufw allow 8080/tcp

# Check status
sudo ufw status
```

### iptables (if not using UFW)
```bash
# Allow SSH, HTTP, HTTPS
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Save rules (persist after reboot)
sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save
```

## Step 7: Monitor and Maintain

### Check Nginx Status
```bash
sudo systemctl status nginx

# View error logs
sudo tail -f /var/log/nginx/terrariumpi.error.log

# View access logs
sudo tail -f /var/log/nginx/terrariumpi.access.log
```

### Monitor Certificate Expiration
```bash
# Check Let's Encrypt certificate expiration
sudo certbot certificates

# Manual renewal (automatic renewal handles this)
sudo certbot renew --dry-run
```

### Monitor Failed Login Attempts
```bash
# View TerrariumPI logs for authentication errors
tail -f log/terrariumpi.log | grep -i "authentication"
```

### Regularly Update System
```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get autoremove -y
```

## Step 8: Test Your Setup

### Test HTTPS Connection
```bash
curl -v https://terrariumpi.example.com
# Should show certificate details and 200 response
```

### Test in Browser
1. Navigate to `https://terrariumpi.example.com`
2. You should see the TerrariumPI login page
3. Login with username and password
4. If 2FA is enabled, enter the 6-digit code from your authenticator

### Test Rate Limiting (Login Protection)
The system will now rate-limit login attempts:
- Max 5 failed attempts per 15 minutes per IP
- Each failed attempt is logged with IP address and timestamp
- After lockout, retry available after 15 minutes

### Verify Security Headers
```bash
curl -I https://terrariumpi.example.com

# Should include these headers:
# Strict-Transport-Security: max-age=31536000...
# X-Frame-Options: SAMEORIGIN
# X-Content-Type-Options: nosniff
# X-XSS-Protection: 1; mode=block
```

## Security Best Practices

### 1. Change Default Password Regularly
- Log in to TerrariumPI web interface
- Go to Settings → Security
- Change password every 90 days

### 2. Keep System Updated
```bash
# Weekly updates
sudo apt-get update && sudo apt-get upgrade -y
```

### 3. Monitor Access Logs
```bash
# Check for suspicious patterns
sudo tail -n 1000 /var/log/nginx/terrariumpi.access.log | grep "401\|403"
```

### 4. Use Strong Passwords
- Minimum 12 characters
- Mix of uppercase, lowercase, numbers, and symbols
- Unique and not used elsewhere

### 5. Enable 2FA for All Users
- Two-factor authentication significantly increases security
- Store backup codes safely

### 6. Regular Backups
```bash
# Backup database and settings
tar -czf terrariumpi-backup-$(date +%Y%m%d).tar.gz \
  migrations/ \
  data/ \
  *.db

# Store in secure location
```

### 7. Whitelist Known Devices (Coming in Future Update)
- Session tokens are tied to IP addresses
- Suspicious IP changes trigger re-authentication

### 8. VPN Alternative (Advanced)
If public access is not feasible, use a VPN:
- WireGuard
- OpenVPN
- Tailscale

## Troubleshooting

### Certificate Not Found
```bash
# Verify certificate paths
ls -la /etc/letsencrypt/live/terrariumpi.example.com/

# Renew certificate
sudo certbot renew --force-renewal
```

### Nginx Connection Refused
```bash
# Check if TerrariumPI is running on the internal port
curl -v http://localhost:8080
# or your configured port

# Check Nginx upstream server configuration
sudo cat /etc/nginx/sites-enabled/terrariumpi | grep upstream -A 2
```

### SSL Handshake Error
```bash
# Test SSL/TLS configuration
sudo openssl s_client -connect terrariumpi.example.com:443

# Check certificate validity
sudo certbot certificates
```

### Rate Limiting Too Strict
Edit `/etc/nginx/sites-enabled/terrariumpi` and adjust:
```nginx
limit_req_zone $binary_remote_addr zone=login_limit:10m rate=5r/m;
# Increase rate from 5r/m to 10r/m if needed
```

### 2FA Code Not Working
- Ensure device time is synchronized (very important!)
- Authenticator app is open with correct account
- Code hasn't expired (valid for ~30 seconds)
- Try backup authentication codes if configured

## Monitoring Checklist

Use this checklist weekly:

- [ ] Check Nginx is running: `sudo systemctl status nginx`
- [ ] Review error logs: `sudo tail /var/log/nginx/terrariumpi.error.log`
- [ ] Verify SSL certificate: `sudo certbot certificates`
- [ ] Check firewall rules: `sudo ufw status`
- [ ] Review system updates available: `sudo apt list --upgradable`
- [ ] Monitor disk space: `df -h`
- [ ] Check TerrariumPI logs for errors: `tail log/terrariumpi.log`
- [ ] Test login from external network

## Next Steps (Advanced Security)

### Option 1: Cloudflare DDoS Protection
1. Move your domain DNS to Cloudflare
2. Enable Cloudflare proxy (orange cloud)
3. Set security level to "High"
4. Enable bot management

### Option 2: Fail2Ban for Additional Protection
```bash
sudo apt-get install -y fail2ban

# Configure for Nginx
sudo nano /etc/fail2ban/jail.local
# Add:
# [nginx-http-auth]
# enabled = true
```

### Option 3: VPN for Internal Network
- Only expose VPN port (WireGuard: UDP 51820)
- TerrariumPI accessible only via VPN
- Maximum security for home networks

## Support and Questions

If you encounter issues:
1. Check logs: `/var/log/nginx/` and `log/terrariumpi.log`
2. Verify DNS: `nslookup yourdomain.com`
3. Test locally: `curl http://localhost:8080`
4. Check certificate: `sudo certbot certificates`

## Disclaimer

This setup provides industry-standard security practices. However:
- No system is 100% secure
- Regularly update all software
- Monitor logs for suspicious activity
- Keep backups of important data
- Follow principle of least privilege
- Stay informed about security best practices

Remember: Security is an ongoing process, not a one-time setup!
