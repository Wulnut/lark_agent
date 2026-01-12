FROM python:3.11-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
ENV PYTHONPATH=/app

# Install dependencies
COPY pyproject.toml .
# Use --system or create a venv. Here we use uv sync which creates a venv in .venv by default,
# but for docker simplicity we can direct uv to install into system or use virtual env context.
# To keep it simple and standard with local dev, we will let uv manage the environment and use 'uv run'.
# However, to ensure cache usage:
RUN uv venv
RUN uv sync --frozen || uv sync

COPY . .

# Default command
CMD ["uv", "run", "main.py"]
