# Despliegue en Oracle Cloud (cuenta Pay As You Go)

Guía de una sola pasada, de cuenta vacía a sitio andando. Los comandos que
empiezan con `#` van **en tu máquina**; los que empiezan con `$` van **en la
VM** por SSH.

Variables que vas a repetir: `DOMINIO` (ej. `mercante365.cl`) y la región
(usá **sa-santiago-1**, Santiago de Chile: es la más cercana a Chile/Bolivia y
es la que ya está de ejemplo en `.env.example`).

---

## 1. Cuenta: pasar a Pay As You Go

Consola OCI → menú de perfil → **Upgrade to Paid** (o Billing & Cost
Management → Upgrade). Pide tarjeta; cobra ~1 USD de verificación.

Qué cambia y qué no:

- Lo **Always Free eligible** sigue sin costo aunque la cuenta sea PAYG. Al
  crear cualquier recurso, la consola marca con una etiqueta si entra en esa
  bolsa. Si no dice *Always Free eligible*, **se factura**.
- Lo que te da PAYG y no tenías: consigues capacidad **Ampere A1** sin pelear
  con el "Out of capacity" del tier gratuito, y podés pasarte del límite si
  algún día hace falta.
- Bolsa gratuita relevante acá (confirmá los números en la consola al crear,
  cambian por región): Ampere A1 hasta **4 OCPU / 24 GB** en total, **200 GB**
  de block storage entre todos los volúmenes, **20 GB** de Object Storage,
  **10 TB/mes** de salida de datos. Este proyecto entra entero ahí dentro.

**Hacé esto apenas termine el upgrade** — es el seguro contra la sorpresa de
fin de mes: Billing & Cost Management → **Budgets** → crear presupuesto sobre
el compartment raíz, monto p.ej. 10 USD, alerta al 50 % y al 100 % a tu correo.

## 2. La VM

Compute → Instances → **Create instance**:

| Campo | Valor |
|---|---|
| Image | **Ubuntu 24.04** (aarch64) |
| Shape | **VM.Standard.A1.Flex** → 4 OCPU, 24 GB *(debe decir Always Free eligible)* |
| VCN | la default; subred **pública**, asignar IP pública |
| Boot volume | 50 GB alcanza y sobra (el free tier llega a 200) |
| SSH keys | pegá tu clave pública |

Si no tenés clave todavía:

```bash
# ssh-keygen -t ed25519 -C "mercante365" -f ~/.ssh/oracle_b2b
# cat ~/.ssh/oracle_b2b.pub        # esto es lo que pegás en la consola
```

Anotá la **IP pública** al terminar.

## 3. Abrir 80 y 443 (los dos cortafuegos)

Oracle bloquea en dos capas y olvidar la segunda es el error clásico: el
puerto se ve cerrado y el problema no está en Docker.

1. **Security List del VCN**: Networking → VCN → subred → Security List
   default → Add Ingress Rules: origen `0.0.0.0/0`, TCP destino **80**, y otra
   igual para **443**.
2. **iptables dentro de la VM** (las imágenes Ubuntu de Oracle vienen con
   reglas propias):

```bash
$ sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
$ sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
$ sudo netfilter-persistent save
```

## 4. Software base en la VM

```bash
# ssh -i ~/.ssh/oracle_b2b ubuntu@<IP>

$ sudo apt update && sudo apt install -y git certbot make
$ curl -fsSL https://get.docker.com | sudo sh
$ sudo usermod -aG docker ubuntu      # cerrá y reabrí la sesión SSH después
```

El `Dockerfile` ya es multiarquitectura, así que en el A1 (aarch64) se
construye igual que en tu Arch, sin tocar nada.

## 5. Object Storage (las imágenes de producto)

Es el reemplazo de MinIO. Mismo código, sólo cambian cuatro variables.

1. Storage → Buckets → **Create Bucket**: nombre `b2b-media`, tier Standard.
2. Abrí el bucket → Edit Visibility → **Public** (las fichas de producto
   muestran las imágenes sin firmar la URL; el código usa
   `querystring_auth = False`).
3. Anotá el **Namespace** que aparece en los detalles del bucket.
4. Perfil → **My profile** → Customer Secret Keys → **Generate Secret Key**.
   Te da un Access Key y un Secret Key: son las credenciales S3. El secreto se
   muestra **una sola vez**.

Con eso:

```
AWS_ACCESS_KEY_ID=<access key>
AWS_SECRET_ACCESS_KEY=<secret key>
AWS_STORAGE_BUCKET_NAME=b2b-media
AWS_S3_ENDPOINT_URL=https://<namespace>.compat.objectstorage.sa-santiago-1.oraclecloud.com
```

## 6. DNS

En tu registrador: registro **A** del dominio → IP pública de la VM (y otro
para `www` si lo vas a usar). Esperá a que resuelva antes del paso 8:

```bash
# dig +short mercante365.cl
```

¿Todavía no hay dominio comprado? Usá `<IP-con-guiones>.sslip.io` (ej.
`152-67-1-2.sslip.io`) como `DOMINIO`: resuelve solo y Let's Encrypt emite
certificado igual. Cuando compres el dominio real, cambiás `DOMINIO` en
`.env`, corrés `make prod-cert` y `make prod-up` de nuevo.

## 7. El código y el `.env` de producción

```bash
$ sudo mkdir -p /srv && sudo chown ubuntu:ubuntu /srv
$ git clone https://github.com/Marselo203/MERCANTE365.git /srv/b2b
$ cd /srv/b2b && cp .env.example .env && nano .env
```

Dejalo así (el `.env` **nunca** se commitea, ya está en `.gitignore`):

```
DJANGO_SECRET_KEY=<pegá el generado abajo>
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=mercante365.cl,www.mercante365.cl
DOMINIO=mercante365.cl

POSTGRES_DB=b2b
POSTGRES_USER=b2b
POSTGRES_PASSWORD=<clave larga al azar>

AWS_...          # las cuatro del paso 5
EMAIL_...        # SMTP cuando lo tengas; sin esto los correos fallan al enviar
```

Para las dos claves:

```bash
$ docker run --rm python:3.12-slim python -c "import secrets;print(secrets.token_urlsafe(50))"
```

## 8. Certificado y arranque

```bash
$ cd /srv/b2b
$ make prod-cert     # sólo la primera vez: levanta un nginx temporal en :80
$ make prod-up       # build + db + web + nginx con TLS
$ docker compose -f compose.yaml -f compose.prod.yaml exec web python manage.py seed_ubicaciones
$ docker compose -f compose.yaml -f compose.prod.yaml exec web python manage.py createsuperuser
```

`migrate` y `collectstatic` los corre solo el entrypoint en cada arranque.
**No** corras `seed_demo` en producción: son datos de mentira.

Las renovaciones del certificado las hace el timer de `certbot` del sistema
por webroot (`/srv/certbot`, que nginx sirve) — no hay que tocar nada.

## 9. Respaldos

```bash
$ crontab -e
0 4 * * * /srv/b2b/docker/backup.sh >> /var/log/b2b-backup.log 2>&1
```

Guarda 14 días en `/srv/respaldos`. Restaurar:

```bash
$ gunzip -c /srv/respaldos/b2b-AAAAMMDD-HHMM.sql.gz | \
    docker compose -f compose.yaml -f compose.prod.yaml exec -T db psql -U b2b -d b2b
```

Ese respaldo vive en la misma VM: cubre un borrado accidental, no la pérdida
de la instancia. Cuando los datos valgan de verdad, bajalo a otra parte
(`rsync`/`scp` desde tu máquina, o un segundo bucket privado).

## 10. Verificación

```bash
# curl -I https://mercante365.cl/            # 200 y cabecera HSTS
# curl -I http://mercante365.cl/             # 301 a https
```

Probá en el navegador: `/` (landing), `/market/`, una ficha de producto, y
`/panel/` con el superusuario. Subí una imagen de producto desde el panel: si
la URL que queda apunta a `objectstorage...oraclecloud.com`, el bucket está
bien conectado.

## Actualizar el sitio después

```bash
$ cd /srv/b2b && git pull && make prod-up
```

## Si algo falla

| Síntoma | Dónde mirar |
|---|---|
| nginx no arranca | ¿corriste `make prod-cert` antes? Sin el certificado, el bloque 443 no levanta |
| El sitio no responde desde afuera | Los **dos** cortafuegos del paso 3 |
| CSRF al hacer login | `DOMINIO` mal escrito en `.env`: de ahí sale `CSRF_TRUSTED_ORIGINS` |
| `DisallowedHost` | Falta el dominio en `DJANGO_ALLOWED_HOSTS` |
| Las imágenes no cargan | Bucket sin visibilidad **Public**, o Customer Secret Key mal copiada |
| Logs | `make prod-logs` |
