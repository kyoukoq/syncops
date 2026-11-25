ARG PYTHON_IMAGE=python:3.12.16-alpine3.24@sha256:c5ba3deef00c7758561a0f03c26f44f10589263d40e732b8748e0d1f38f6dd89
FROM ${PYTHON_IMAGE} AS dependencies

WORKDIR /build
COPY requirements.txt .
RUN python -m venv --without-pip /opt/venv \
    && python -m pip --python /opt/venv install --no-cache-dir --disable-pip-version-check -r requirements.txt

FROM ${PYTHON_IMAGE}

RUN apk upgrade --no-cache && python -m pip uninstall --yes pip

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
