#!/usr/bin/env bash
# Database backup script for Filum

set -e

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="filum_backup_${TIMESTAMP}"

mkdir -p "$BACKUP_DIR"

echo "📦 Starting database backup..."

# Check if postgres container is running
if ! docker ps | grep -q filum-postgres; then
    echo "❌ PostgreSQL container not running. Starting docker-compose..."
    docker-compose -f docker-compose.yml up -d postgres
    sleep 5
fi

# Create backup
docker exec filum-postgres pg_dump -U filum filum_dev > "$BACKUP_DIR/${BACKUP_NAME}.sql"

# Compress backup
gzip "$BACKUP_DIR/${BACKUP_NAME}.sql"

# Create metadata
cat > "$BACKUP_DIR/${BACKUP_NAME}.meta" <<EOF
{
    "timestamp": "$TIMESTAMP",
    "filename": "${BACKUP_NAME}.sql.gz",
    "size": $(stat -f%z "$BACKUP_DIR/${BACKUP_NAME}.sql.gz" 2>/dev/null || stat -c%s "$BACKUP_DIR/${BACKUP_NAME}.sql.gz"),
    "environment": "${ENVIRONMENT:-development}"
}
EOF

# Cleanup old backups (keep last 30)
cd "$BACKUP_DIR"
ls -t filum_backup_*.sql.gz | tail -n +31 | xargs rm -f 2>/dev/null || true

echo "✅ Backup complete: ${BACKUP_NAME}.sql.gz"
echo "📁 Location: $BACKUP_DIR"
