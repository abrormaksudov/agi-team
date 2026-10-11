# The catalog agent: FastAPI on :8000, dependencies from uv.lock.
FROM python:3.13.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.10.3 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev
ENV PATH=/app/.venv/bin:$PATH AGENT_JOURNAL=/data/journal.jsonl
CMD ["uvicorn", "agi_agent.app:app", "--host", "0.0.0.0", "--port", "8000"]
