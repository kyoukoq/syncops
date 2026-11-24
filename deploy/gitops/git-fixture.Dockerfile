FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install --no-install-recommends -y git \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /srv/git-http/cgi-bin \
    && ln -s /usr/lib/git-core/git-http-backend /srv/git-http/cgi-bin/git

ENV GIT_PROJECT_ROOT=/repos GIT_HTTP_EXPORT_ALL=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001:10001
CMD ["python", "-m", "http.server", "--cgi", "--bind", "0.0.0.0", "--directory", "/srv/git-http", "8000"]
