FROM python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
ARG SOURCE_COMMIT
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN groupadd --system appgroup && useradd --system --gid appgroup --uid 1000 appuser
COPY app/requirements.txt requirements.txt
RUN pip install --no-cache-dir --require-hashes -r requirements.txt
COPY app/ ./
RUN python -c 'import json,re,sys; commit=sys.argv[1]; assert re.fullmatch("[0-9a-f]{40}",commit), "SOURCE_COMMIT must be a full Git SHA"; open("build-info.json","w").write(json.dumps({"commit":commit}))' "$SOURCE_COMMIT"
LABEL org.opencontainers.image.revision=$SOURCE_COMMIT
USER 1000:1000
EXPOSE 8080
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--graceful-timeout", "20", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
