#!/usr/bin/env bash
# Deployment script for Filum application

set -e

ENVIRONMENT=${1:-staging}
REGION=${2:-eu-west}

echo "🚀 Deploying Filum to $ENVIRONMENT environment"

# Load environment variables
if [ -f ".env.$ENVIRONMENT" ]; then
    export $(cat ".env.$ENVIRONMENT" | grep -v '^#' | xargs)
fi

# Build and tag images
echo "📦 Building Docker images..."
docker build -f apps/backend/Dockerfile -t filum-backend:$ENVIRONMENT apps/backend
docker build -f apps/frontend/Dockerfile -t filum-frontend:$ENVIRONMENT apps/frontend

# Push to registry
echo "⬆️ Pushing images to registry..."
docker tag filum-backend:$ENVIRONMENT $REGISTRY/filum/backend:$ENVIRONMENT
docker tag filum-frontend:$ENVIRONMENT $REGISTRY/filum/frontend:$ENVIRONMENT
docker push $REGISTRY/filum/backend:$ENVIRONMENT
docker push $REGISTRY/filum/frontend:$ENVIRONMENT

# Deploy via docker-compose
echo "🎯 Deploying with docker-compose..."
docker-compose -f infra/postgres/docker-compose.yml up -d

# Wait for database
echo "⏳ Waiting for database..."
until docker exec filum-postgres-$ENVIRONMENT pg_isready -U filum; do
    echo "Database not ready, waiting..."
    sleep 2
done

# Run migrations
echo "🔄 Running migrations..."
docker-compose -f infra/postgres/docker-compose.yml run --rm migrate

echo "✅ Deployment complete!"
echo "🌐 Backend: https://api.$ENVIRONMENT.filum.app"
echo "🌐 Frontend: https://$ENVIRONMENT.filum.app"
