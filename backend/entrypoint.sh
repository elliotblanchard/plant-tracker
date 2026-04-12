#!/bin/sh
# Write Drive credentials file from env var if provided
if [ -n "$DRIVE_CREDS_B64" ]; then
    echo "$DRIVE_CREDS_B64" | base64 -d > /app/drive-creds.json
    export PT_DRIVE_SERVICE_ACCOUNT_JSON=/app/drive-creds.json
fi
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
