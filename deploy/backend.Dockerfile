FROM python:3.12-slim-bookworm AS dependencies

WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

FROM python:3.12-slim-bookworm

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=dependencies /opt/venv /opt/venv
COPY alembic.ini .
COPY migrations ./migrations
COPY syncops ./syncops
USER 10001:10001
CMD ["python", "-m", "uvicorn", "syncops.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
