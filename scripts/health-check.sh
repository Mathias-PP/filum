#!/usr/bin/env bash
# Health check script for production monitoring

set -e

ENVIRONMENT=${1:-production}
API_URL=${2:-https://api.filum.app/health}

echo "🔍 Running health checks for $ENVIRONMENT..."

# Check backend health
echo -n "Backend health check... "
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL" || echo "000")

if [ "$HTTP_STATUS" = "200" ]; then
    echo "✅ OK (HTTP $HTTP_STATUS)"
    BACKEND_STATUS=0
else
    echo "❌ FAILED (HTTP $HTTP_STATUS)"
    BACKEND_STATUS=1
fi

# Check database connectivity
echo -n "Database check... "
DB_CHECK=$(curl -s "$API_URL/database" || echo '{"status":"error"}')
if echo "$DB_CHECK" | grep -q '"status":"ok"'; then
    echo "✅ OK"
    DB_STATUS=0
else
    echo "❌ FAILED"
    DB_STATUS=1
fi

# Check disk space
echo -n "Disk space check... "
DISK_USAGE=$(df -h . | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 90 ]; then
    echo "✅ OK ($DISK_USAGE% used)"
    DISK_STATUS=0
else
    echo "⚠️  WARNING ($DISK_USAGE% used)"
    DISK_STATUS=0
fi

# Exit with appropriate code
TOTAL_STATUS=$((BACKEND_STATUS + DB_STATUS + DISK_STATUS))
if [ $TOTAL_STATUS -eq 0 ]; then
    echo "🎉 All checks passed!"
    exit 0
else
    echo "💥 Some checks failed!"
    exit 1
fi
