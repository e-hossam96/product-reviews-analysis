#!/bin/sh
set -e

# Make sure the data directory exists (the database lives on a volume)
python startup.py

# Apply any pending migrations
alembic upgrade head

# Start the app. exec makes uvicorn PID 1, so it receives stop signals directly.
#
# --workers 1 is deliberate: running analysis jobs and the "one analysis at a time"
# lock live in this process.
#
# --forwarded-allow-ips "*" lets rate limiting see the real client IP from the
# X-Forwarded-For header. That is only safe because this port is never published:
# nginx is the only client, and it overwrites the header with the address it saw.
exec uvicorn app.main:app --host 0.0.0.0 --port 11696 --workers 1 \
    --proxy-headers --forwarded-allow-ips "*"
