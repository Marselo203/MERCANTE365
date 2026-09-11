#!/usr/bin/env bash
set -euo pipefail

# La espera real la resuelve el healthcheck de compose (depends_on: service_healthy).
# Esto es un seguro por si el contenedor se reinicia solo o lo corres fuera de compose.
python - <<'PY'
import os, socket, sys, time

host = os.environ.get("POSTGRES_HOST", "db")
port = int(os.environ.get("POSTGRES_PORT", "5432"))
plazo = time.monotonic() + 60

while time.monotonic() < plazo:
    try:
        with socket.create_connection((host, port), timeout=3):
            print(f"PostgreSQL disponible en {host}:{port}")
            sys.exit(0)
    except OSError:
        time.sleep(1)

print(f"PostgreSQL no respondió en {host}:{port} tras 60s", file=sys.stderr)
sys.exit(1)
PY

python manage.py migrate --noinput

# En desarrollo los estáticos los sirve runserver; recolectarlos solo estorba.
if [ "${DJANGO_COLLECTSTATIC:-1}" = "1" ]; then
    python manage.py collectstatic --noinput --clear
fi

exec "$@"
