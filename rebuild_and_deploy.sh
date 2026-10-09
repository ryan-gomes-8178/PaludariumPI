#!/bin/bash

# TerrariumPI Rebuild and Deploy Script
# This script rebuilds the frontend and ensures Cloudflare cache is cleared
# Run this script whenever you make changes to the frontend code

set -e  # Exit on any error

LOCAL_URL="http://$(hostname -I | awk '{print $1}'):8090"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================"
echo "TerrariumPI Rebuild & Deploy"
echo "======================================"
echo ""

# Step 1: Build the frontend
echo "📦 Building frontend..."
npm run build

if [ $? -ne 0 ]; then
    echo "❌ Build failed!"
    exit 1
fi

echo "✅ Build completed successfully!"
echo ""

# Step 2: Restore Bluetooth permissions for Bluetooth sensors (SwitchBot, Mi, ...)
# The bluepy helper loses its capabilities when the virtual environment is (re)installed.
# Same command as install.sh
echo "🔵 Setting Bluetooth capabilities on bluepy helper..."
find venv/ -name "bluepy*-helper" -exec sudo setcap 'cap_net_raw,cap_net_admin+eip' {} \;
echo "✅ Bluetooth capabilities set!"
echo ""

# Step 3: Restart the service
echo "🔄 Restarting TerrariumPI service..."
sudo systemctl restart terrariumpi.service

if [ $? -ne 0 ]; then
    echo "❌ Service restart failed!"
    exit 1
fi

echo "✅ Service restarted successfully!"
echo ""

# Step 4: Wait for service to come back up
echo "⏳ Waiting for service to start (10 seconds)..."
sleep 10
echo ""

# Step 5: Cloudflare Cache Handling
echo "🌐 Cloudflare Cache Management"
echo "================================"
echo ""
echo "Your domain (paludariumpi.dev) may still show old content due to Cloudflare caching."
echo ""
echo "Option 1: Manual Cache Purge (Recommended)"
echo "  1. Go to: https://dash.cloudflare.com/"
echo "  2. Select your domain: paludariumpi.dev"
echo "  3. Go to 'Caching' > 'Configuration'"
echo "  4. Click 'Purge Everything'"
echo "  5. Wait 30-60 seconds, then check your domain"
echo ""
echo "Option 2: Automatic Cache Purge (Requires API Token)"
echo "  Set these environment variables:"
echo "    export CLOUDFLARE_API_TOKEN='your-api-token'"
echo "    export CLOUDFLARE_ZONE_ID='your-zone-id'"
echo "  Then run this script again."
echo ""

# Check if Cloudflare credentials are set
if [ -n "$CLOUDFLARE_API_TOKEN" ] && [ -n "$CLOUDFLARE_ZONE_ID" ]; then
    echo "🔑 Cloudflare credentials detected. Purging cache..."
    
    RESPONSE=$(curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$CLOUDFLARE_ZONE_ID/purge_cache" \
         -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
         -H "Content-Type: application/json" \
         --data '{"purge_everything":true}')
    
    if echo "$RESPONSE" | grep -q '"success":true'; then
        echo "✅ Cloudflare cache purged successfully!"
        echo "⏳ Waiting 30 seconds for cache to clear..."
        sleep 30
        echo ""
        echo "🎉 DEPLOYMENT COMPLETE!"
        echo ""
        echo "Check your sites now:"
        echo "  Local:  ${LOCAL_URL}/#/monitoring/"
        echo "  Domain: https://paludariumpi.dev/#/monitoring/"
        echo ""
        echo "Both should show identical content now."
    else
        echo "⚠️  Cloudflare cache purge failed!"
        echo "Response: $RESPONSE"
        echo ""
        echo "Please purge cache manually (see instructions above)."
    fi
else
    echo "⚠️  No Cloudflare credentials found - skipping automatic cache purge."
    echo ""
    echo "📋 NEXT STEPS:"
    echo "  1. Manually purge Cloudflare cache (see instructions above)"
    echo "  2. Wait 30-60 seconds"
    echo "  3. Check https://paludariumpi.dev/#/monitoring/"
    echo ""
fi

echo "======================================"
echo "Local deployment complete!"
echo "  ${LOCAL_URL}/#/monitoring/ - ✅ Updated"
echo ""
echo "Domain update pending cache purge:"
echo "  https://paludariumpi.dev/#/monitoring/ - ⏳ Waiting for cache clear"
echo "======================================"
