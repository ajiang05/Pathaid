# syntax=docker/dockerfile:1
FROM python:3.14-slim

# Python should write logs immediately and must not create bytecode in the
# read-only application directory used by production containers.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies before copying source so dependency layers remain
# cached when only application code changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY data ./data

# A fixed unprivileged identity prevents the API or worker from running as root.
RUN addgroup --system pathaid && adduser --system --ingroup pathaid pathaid \
    && chown -R pathaid:pathaid /app
USER pathaid

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
