#!/bin/sh
# Write Drive credentials file from env var(s) if provided
# Supports: single DRIVE_CREDS_B64 or split DRIVE_CREDS_B64_1 + DRIVE_CREDS_B64_2
if [ -n "$DRIVE_CREDS_B64" ]; then
    echo "$DRIVE_CREDS_B64" | base64 -d > /app/drive-creds.json
    export PT_DRIVE_SERVICE_ACCOUNT_JSON=/app/drive-creds.json
    echo "ENTRYPOINT: wrote credentials from DRIVE_CREDS_B64" >&2
elif [ -n "$DRIVE_CREDS_B64_1" ] && [ -n "$DRIVE_CREDS_B64_2" ]; then
    printf '%s%s' "$DRIVE_CREDS_B64_1" "$DRIVE_CREDS_B64_2" | base64 -d > /app/drive-creds.json
    export PT_DRIVE_SERVICE_ACCOUNT_JSON=/app/drive-creds.json
    echo "ENTRYPOINT: wrote credentials from DRIVE_CREDS_B64_1 + _2" >&2
fi
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
