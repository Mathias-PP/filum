#!/usr/bin/env bash
# Restore database from backup

set -e

BACKUP_FILE=${1}
if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo "Available backups:"
    ls -la backups/filum_backup_*.sql.gz 2>/dev/null || echo "No backups found"
    exit 1
fi

echo "⚠️  WARNING: This will overwrite the current database!"
echo "📁 Backup file: $BACKUP_FILE"
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# Check if postgres is running
if ! docker ps | grep -q filum-postgres; then
    echo "❌ PostgreSQL container not running."
    exit 1
fi

# Stop backend to prevent writes
echo "⏸️  Stopping backend..."
docker-compose stop backend || true

# Drop and recreate database
echo "🗑️  Resetting database..."
docker exec filum-postgres psql -U filum -c "DROP DATABASE IF EXISTS filum_dev;"
docker exec filum-postgres psql -U filum -c "CREATE DATABASE filum_dev;"

# Restore from backup
echo "📥 Restoring from backup..."
gunzip -c "$BACKUP_FILE" | docker exec -i filum-postgres psql -U filum filum_dev

# Run migrations
echo "🔄 Running migrations..."
docker-compose run --rm backend python -m alembic upgrade head || true

# Start backend
echo "▶️  Starting backend..."
docker-compose start backend

echo "✅ Restore complete!"
