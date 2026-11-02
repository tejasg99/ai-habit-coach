FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first: this layer stays cached until requirements.txt changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Run as an unprivileged user, so a bug in the app can't own the container.
RUN useradd --create-home --uid 1000 appuser
COPY --chown=appuser:appuser alembic.ini ./
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser app ./app
USER appuser

EXPOSE 8000

# Apply migrations, then start the server. `exec` makes uvicorn the main process so it
# receives the stop signal and can shut down cleanly. Hosts inject $PORT.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]