# Kasa Device Credentials Guide

## Overview

Newer TP-Link Kasa devices (manufactured mid-2023 onwards) use the KLAP (Kasa Local Authentication Protocol) which requires authentication credentials for local control. This update adds support for storing and using these credentials in TerrariumPI.

## Why This Is Needed

If you're seeing authentication errors like:
```
kasa.exceptions.AuthenticationException: Server response doesn't match our challenge on ip X.X.X.X
```

This means your Kasa device requires credentials for local access.

## How to Configure Credentials

### Method 1: Via Web Interface

1. Log into your TerrariumPI web interface
2. Navigate to **Settings** → **Relays**
3. Find your Kasa relay device
4. Click **Edit**
5. In the configuration, add credentials to the **Calibration** field as JSON:
   ```json
   {
     "username": "your-kasa-email@example.com",
     "password": "your-kasa-password"
   }
   ```
6. Save the changes
7. The relay should now connect successfully

### Method 2: Via Database (Advanced)

If you need to update credentials directly in the database:

```bash
sqlite3 /path/to/terrariumpi.db
```

Then update the calibration field:
```sql
UPDATE Relay 
SET calibration = '{"username": "your-kasa-email@example.com", "password": "your-kasa-password"}'
WHERE address LIKE '192.168.1.XXX%';
```

### Method 3: Bulk Update for Multiple Devices

If you have multiple Kasa devices on the same account, you can update them all at once:

```sql
UPDATE Relay 
SET calibration = '{"username": "your-kasa-email@example.com", "password": "your-kasa-password"}'
WHERE hardware = 'tplinkkasa' AND calibration = '{}';
```

## What Credentials to Use

Use your **TP-Link/Kasa account credentials**:
- **Username**: The email address you use to log into the Kasa mobile app
- **Password**: The password for your Kasa account

## Security Notes

- Credentials are stored in the local database
- They are only used for local network communication with your devices
- No credentials are sent to external servers
- Consider using a strong password for your Kasa account
- The database file should have appropriate file permissions (readable only by the TerrariumPI user)

## Troubleshooting

### Still Getting Authentication Errors?

1. **Verify credentials**: Make sure your username and password are correct by logging into the Kasa mobile app
2. **Check JSON format**: Ensure the calibration field is valid JSON with proper quotes
3. **Restart service**: After updating credentials, restart TerrariumPI:
   ```bash
   sudo systemctl restart terrariumpi
   ```
4. **Check logs**: Look for messages like "Using credentials for Kasa device at X.X.X.X" in the logs

### Older Kasa Devices

If you have older Kasa devices that work without credentials, you don't need to configure anything. The code will automatically work with both authenticated and non-authenticated devices.

## Technical Details

- Credentials are stored in the `calibration` JSON field in the database
- The `Credentials` object from the `python-kasa` library is used
- Credentials are passed to `Discover.discover_single()` during device initialization
- If no credentials are provided, the device will attempt connection without authentication (backward compatible)

## Example Configuration

Here's a complete example of what the calibration field should look like:

```json
{
  "username": "john.doe@example.com",
  "password": "MySecurePassword123!"
}
```

**Important**: Make sure to use double quotes (") for JSON, not single quotes (').

## Support

If you continue to experience issues after configuring credentials:
1. Check that your Kasa device firmware is up to date
2. Verify network connectivity to the device
3. Review TerrariumPI logs for detailed error messages
4. Consider opening an issue on the TerrariumPI GitHub repository with relevant log excerpts
