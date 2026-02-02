# Nocturnal Eye Security Configuration

The Nocturnal Eye integration provides special endpoints for external gecko motion detection systems to access live camera streams. These endpoints implement multiple security layers to protect against unauthorized access.

## Security Features

### 1. Token-Based Authentication

Protect Nocturnal Eye endpoints with an API token that must be provided with each request.

**Configuration:**
- Setting name: `nocturnal_eye_api_token`
- Value: Any secure string (recommended: 32+ random characters)

**Usage:**
Clients can provide the token in two ways:

1. **Authorization Header (Recommended):**
   ```
   Authorization: Bearer YOUR_TOKEN_HERE
   ```

2. **Query Parameter:**
   ```
   http://your-server:8090/nocturnal-eye/stream.m3u8?token=YOUR_TOKEN_HERE
   ```

### 2. IP Allowlist

Restrict access to Nocturnal Eye endpoints to specific IP addresses only.

**Configuration:**
- Setting name: `nocturnal_eye_allowed_ips`
- Value: Comma-separated list of IP addresses (e.g., `192.168.1.100, 192.168.1.101`)

**Behavior:**
- If empty or not configured: All IPs are allowed (only token auth applies)
- If configured: Only listed IPs can access the endpoints

**Important Security Note:**
The IP address is detected from `X-Real-Ip` header (if present) or `request.remote_addr`. When deploying behind a reverse proxy (e.g., nginx, Apache), ensure the proxy is properly configured to set the `X-Real-Ip` header to prevent header spoofing attacks:

```nginx
# nginx example
proxy_set_header X-Real-IP $remote_addr;
```

If not behind a trusted proxy, the `X-Real-Ip` header could be forged by attackers to bypass IP allowlisting.

### 3. Rate Limiting

Automatic rate limiting prevents abuse and excessive bandwidth consumption.

**Default Settings:**
- Window: 60 seconds (1 minute)
- Max requests: 600 per window (10 requests/second)
- Applied per IP address

**Response when exceeded:**
- HTTP 429 (Too Many Requests)
- Error message: "Rate limit exceeded. Please try again later."

## Configuration Examples

### Example 1: Token Authentication Only
```python
# In your TerrariumPI settings
nocturnal_eye_api_token = "your-secure-token-here-min-32-chars"
# Leave nocturnal_eye_allowed_ips empty
```

### Example 2: IP Allowlist Only
```python
# In your TerrariumPI settings
nocturnal_eye_allowed_ips = "192.168.1.100, 192.168.1.101"
# Leave nocturnal_eye_api_token empty
```

### Example 3: Both Token and IP Allowlist (Maximum Security)
```python
# In your TerrariumPI settings
nocturnal_eye_api_token = "your-secure-token-here-min-32-chars"
nocturnal_eye_allowed_ips = "192.168.1.100"
```

### Example 4: No Security (Not Recommended)
```python
# Leave both settings empty or unset
# This allows anyone on the network to access the camera streams
```

## Security Logging

All security-related events are logged:
- Unauthorized IP access attempts
- Invalid or missing token attempts
- Rate limit violations

Check the TerrariumPI logs for security monitoring.

## Endpoints Protected

Both Nocturnal Eye endpoints are protected:
- `/nocturnal-eye/stream.m3u8` - HLS manifest
- `/nocturnal-eye/chunks/<filename>` - Video chunks

## Recommendations

For production deployments:
1. **Always use token authentication** with a strong, randomly-generated token
2. **Enable IP allowlisting** when the Nocturnal Eye service has a static IP
3. **Monitor logs** regularly for unauthorized access attempts
4. **Rotate tokens** periodically as part of security maintenance

For development/testing:
- You may disable security temporarily, but re-enable before deployment
- Use localhost/127.0.0.1 in IP allowlist for local testing

## Troubleshooting

### Error 401: Access denied: Invalid or missing API token
- Verify the token is correctly configured in TerrariumPI settings
- Ensure the client is sending the token in Authorization header or query parameter
- Check that the token matches exactly (no extra spaces or characters)

### Error 403: Access denied: IP not in allowlist
- Verify the client IP is included in `nocturnal_eye_allowed_ips`
- Check for typos in IP addresses
- Ensure comma separation between multiple IPs

### Error 429: Rate limit exceeded
- The client is making too many requests
- Wait 60 seconds and try again
- Consider optimizing the client to reduce request frequency
- HLS streams typically request the manifest every 2-5 seconds
