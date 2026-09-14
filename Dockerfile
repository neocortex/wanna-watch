FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

ENV WANNA_WATCH_DATA_DIR=/data
ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "exec /app/.venv/bin/wanna-watch --host 0.0.0.0 --port ${PORT:-8000}"]
