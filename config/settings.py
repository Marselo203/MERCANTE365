"""
config/settings.py

Un solo archivo de settings para los dos entornos. Lo que cambia entre tu Arch y el
Ampere son las VARIABLES, no el código: así lo que pruebas localmente es literalmente
la misma configuración que corre en producción, salvo los interruptores explícitos.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# En Docker las variables vienen del entorno del contenedor; el .env es para cuando
# corres manage.py directamente en el host.
load_dotenv(BASE_DIR / ".env", override=False)


def env_bool(clave, defecto=False):
    return os.environ.get(clave, str(int(defecto))).strip().lower() in {"1", "true", "yes", "on"}


def env_list(clave, defecto=""):
    return [v.strip() for v in os.environ.get(clave, defecto).split(",") if v.strip()]


# ---------------------------------------------------------------------------
# Núcleo
# ---------------------------------------------------------------------------

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# Detrás de nginx hay que declarar los orígenes con esquema, o el admin rechaza
# cualquier POST con error de CSRF.
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "catalogo",
    "panel",
    "web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "web.middleware.CapturarReferidoMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# El "Ingresar" del sitio lleva al admin del cliente (app panel). El admin de
# Django queda en /django-admin/ solo para desarrollo.
LOGIN_URL = "panel:login"
LOGIN_REDIRECT_URL = "panel:dashboard"
LOGOUT_REDIRECT_URL = "panel:login"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "panel.context_processors.nav",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "b2b"),
        "USER": os.environ.get("POSTGRES_USER", "b2b"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        # Conexiones persistentes: gunicorn abre una por worker y la reutiliza.
        # En desarrollo se deja en 0 para no dejar conexiones colgadas al recargar.
        "CONN_MAX_AGE": 0 if DEBUG else 60,
        "CONN_HEALTH_CHECKS": not DEBUG,
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Regionalización
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "es"
# La sociedad que opera y factura reside en Chile, así que los horarios del panel
# se muestran en hora chilena. Todo se guarda en UTC igual, y Bolivia no aplica
# horario de verano mientras Chile sí: si alguna vez muestras horarios a las
# empresas compradoras, conviértelos explícitamente, no asumas que coinciden.
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Archivos estáticos y media
# ---------------------------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "assets"] if (BASE_DIR / "assets").exists() else []

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Si hay bucket configurado se usa almacenamiento de objetos; si no, disco local.
# Mismo código en los dos entornos: solo cambia si la variable está o no.
USAR_OBJECT_STORAGE = bool(os.environ.get("AWS_STORAGE_BUCKET_NAME"))

if USAR_OBJECT_STORAGE:
    almacenamiento_default = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": os.environ["AWS_STORAGE_BUCKET_NAME"],
            "endpoint_url": os.environ["AWS_S3_ENDPOINT_URL"],
            "access_key": os.environ["AWS_ACCESS_KEY_ID"],
            "secret_key": os.environ["AWS_SECRET_ACCESS_KEY"],
            "region_name": os.environ.get("AWS_S3_REGION_NAME", "sa-santiago-1"),
            # OCI y MinIO requieren direccionamiento por ruta, no por subdominio.
            "addressing_style": "path",
            "file_overwrite": False,
            "querystring_auth": False,
            "default_acl": None,
        },
    }
else:
    almacenamiento_default = {"BACKEND": "django.core.files.storage.FileSystemStorage"}

STORAGES = {
    "default": almacenamiento_default,
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
        ),
    },
}

# Límite de carga en memoria antes de pasar a archivo temporal. Sube si vas a
# permitir imágenes de producto grandes.
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# ---------------------------------------------------------------------------
# Seguridad (solo se endurece fuera de DEBUG)
# ---------------------------------------------------------------------------

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

# ---------------------------------------------------------------------------
# Correo
# ---------------------------------------------------------------------------

# En desarrollo los correos de notificación salen por consola: no necesitas SMTP
# para probar el circuito de requerimientos.
EMAIL_BACKEND = os.environ.get(
    "DJANGO_EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-responder@localhost")

# ---------------------------------------------------------------------------
# Logging a stdout: es lo que espera Docker, y así docker compose logs sirve
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "consola": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["consola"], "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO")},
    "loggers": {
        "django.db.backends": {
            # Poner en DEBUG para ver cada consulta SQL mientras desarrollas.
            "level": os.environ.get("DJANGO_SQL_LOG_LEVEL", "WARNING"),
            "handlers": ["consola"],
            "propagate": False,
        },
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
