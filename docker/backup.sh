#!/usr/bin/env bash
# Respaldo nocturno de la base. Se corre desde cron en el servidor:
#   0 4 * * * /srv/b2b/docker/backup.sh >> /var/log/b2b-backup.log 2>&1
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DESTINO="${DESTINO:-/srv/respaldos}"
DIAS="${DIAS:-14}"

cd "$REPO"
set -a; . ./.env; set +a
mkdir -p "$DESTINO"

archivo="$DESTINO/b2b-$(date +%Y%m%d-%H%M).sql.gz"
docker compose -f compose.yaml -f compose.prod.yaml exec -T db \
    pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$archivo"

# Un dump vacío pesa ~20 bytes: si pg_dump falló a medias, no borres lo viejo.
[ "$(stat -c%s "$archivo")" -gt 1000 ] || { echo "respaldo sospechoso: $archivo"; exit 1; }

find "$DESTINO" -name 'b2b-*.sql.gz' -mtime +"$DIAS" -delete
echo "ok $archivo ($(du -h "$archivo" | cut -f1))"

# ponytail: el respaldo queda en el mismo volumen que la VM. Sirve contra un
# 'DELETE' sin WHERE, no contra perder la instancia. Cuando los datos valgan
# de verdad: rsync a otra máquina, o un segundo bucket privado en OCI.
