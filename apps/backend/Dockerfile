FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-install-project

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "uv run alembic upgrade head && uv run python -m app.scripts.seed_demo && uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
