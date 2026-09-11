# MERCANTE365

Plataforma de intermediación comercial entre proveedores de **Chile** y
empresas compradoras de **Bolivia**. Catálogo público, ficha de producto con
envío de requerimiento, y un panel de gestión a medida para el equipo que
opera la plataforma.

## Stack

- **Django 5.2 LTS** sobre Python 3.12, **PostgreSQL 18**
- Docker Compose para desarrollo y producción con el mismo `Dockerfile`
  (imágenes multiarquitectura: se construye igual en un Mac/PC x86_64 y en el
  servidor de producción, un Ampere A1 de Oracle Cloud, aarch64)
- MinIO en desarrollo como reemplazo local de OCI Object Storage (misma API
  S3, mismo código de subida de imágenes en los dos entornos)
- Sin frontend framework: HTML + CSS a mano, Django templates. Sin JS más
  allá de un par de mejoras puntuales (mostrar/ocultar contraseña, un select
  que se autoenvía)

## Apps

| App | Qué es |
|---|---|
| `catalogo` | Los modelos de dominio: empresas, categorías (con atributos técnicos heredados), productos, imágenes, escalas de precio, requerimientos. |
| `panel` | El admin del cliente (`/panel/`), a medida — CRUD genérico sobre los modelos de `catalogo`, con login propio. `django.contrib.admin` existe pero queda en `/django-admin/` solo para desarrollo. |
| `web` | El sitio público (`/`): landing, catálogo con búsqueda y filtro por rubro (`/market/`), ficha de producto con formulario de requerimiento. |

## Desarrollo local

Requiere Docker. Todo pasa por `docker compose`, nunca se corre contra un
Python del host.

```bash
cp .env.example .env      # ajustá SECRET_KEY y credenciales
make up                   # build + levanta db, minio y web con autoreload
make seed                 # ubicaciones (CL/BO) + datos de demostración
make admin                # crea tu superusuario
```

- Sitio público: <http://localhost:8000/>
- Panel de gestión: <http://localhost:8000/panel/>
- Admin de Django (solo dev): <http://localhost:8000/django-admin/>
- Consola de MinIO: <http://localhost:9001/> (`minioadmin` / `minioadmin`)

Otros atajos (ver `Makefile`): `make logs`, `make bash`, `make psql`,
`make mm` / `make migrate`, `make test`, `make dump`, `make reset` (borra la
base y la recrea desde cero — solo para desarrollo).

## Tests

```bash
make test
# o puntual:
docker compose exec web python manage.py test catalogo panel web
```

## Producción

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

`compose.prod.yaml` agrega nginx (TLS vía certbot, sirviendo `/static/` y
`/media/`) y saca el bind-mount de código y los puertos de la base — el
`Dockerfile` es el mismo que en desarrollo. Ver `docker/nginx.conf` (hay que
reemplazar `DOMINIO` por el dominio real antes de emitir el certificado).

## Estado actual

- Catálogo con categorías jerárquicas, atributos técnicos heredados y
  validados, escalas de precio, imágenes con principal única.
- Panel de gestión con CRUD completo (los 8 modelos editables), descripciones
  de ayuda por campo y por tabla, login con validación clásica.
- Sitio público: landing, Market (búsqueda, filtro por rubro con
  subcategorías, orden, paginación), ficha de producto con insignia
  "Verificado" y formulario de requerimiento.
- Estilo: paleta de marca (negro/blanco/verde/morado + degradado) con
  tratamiento neobrutalista (bordes gruesos, sombra dura).

### Pendiente / próximos pasos

- Login y autorregistro de empresas compradoras en el sitio público (hoy el
  formulario de requerimiento pide los datos de contacto a mano, porque no
  hay sesión de comprador todavía).
- Permisos más finos en el panel (hoy todo el staff ve y edita todo).
- Página "Market" con la ficha de proveedor propia (vitrina por empresa).
