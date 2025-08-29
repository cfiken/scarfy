FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files
COPY pyproject.toml .
COPY uv.lock* .

# Install dependencies
RUN uv sync --frozen

# Copy source code
COPY . .

# Set Python path
ENV PYTHONPATH=/app

# Default command
CMD ["uv", "run", "python", "-m", "src.main"]