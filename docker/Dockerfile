# Imagen de la aplicación Django.
#
# python:3.12-slim publica linux/amd64 y linux/arm64, así que el MISMO Dockerfile
# sirve en tu Arch (x86_64) y en el Ampere A1 de Oracle (aarch64).
#
# NO uses la variante alpine: psycopg[binary] y Pillow publican wheels manylinux,
# no musl. En alpine pip intenta compilar desde fuente y necesitas toolchain,
# libpq-dev, zlib, libjpeg y varios minutos de build en cada imagen.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Solo lo necesario en runtime. psycopg[binary] trae su propia libpq embebida,
# así que no hace falta libpq-dev ni build-essential.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Capa de dependencias separada: cambiar código no reinstala paquetes.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Usuario sin privilegios. El uid fijo facilita los permisos del volumen de media
# si algún día montas un directorio del host.
RUN useradd --uid 10001 --create-home --shell /bin/bash app \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R app:app /app
USER app

# gunicorn escucha en 0.0.0.0:$PORT si no se le pasa --bind. Railway inyecta PORT.
ENV PORT=8000
EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", \
     "--workers", "3", \
     "--threads", "2", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
