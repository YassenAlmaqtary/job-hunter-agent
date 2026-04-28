# -----------------------------------------------------------------------------
# Builder: compile wheels / install deps into a virtualenv (no runtime compiler).
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# No apt here: wheels-only install avoids Debian mirror flakiness during docker build.
WORKDIR /build

COPY requirements.txt .

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Runtime: slim image, venv only, non-root user.
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="job-hunter-agent" \
      org.opencontainers.image.description="LangGraph agent (Streamlit)"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH" \
    # Empty = in-memory checkpointer; set to redis://redis:6379/0 when using Redis profile
    REDIS_URL="" \
    # Hint for app code: memory | redis (your graph can read this when wiring checkpointers)
    LANGGRAPH_CHECKPOINTER_BACKEND="memory"

RUN groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --home-dir /app --shell /bin/bash app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv

# Application code (owned by app user)
COPY --chown=1000:1000 . .

USER app

EXPOSE 8501

# Streamlit built-in health (1.28+)
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=5)"

CMD ["streamlit", "run", "streamlit_app.py", \
     "--server.port", "8501", \
     "--server.address", "0.0.0.0", \
     "--server.headless", "true"]
