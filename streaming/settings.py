import os
from pathlib import Path
from dotenv import load_dotenv

# =========================
# ENV
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env.local")

# =========================
# SEGURIDAD
# =========================
SECRET_KEY = os.getenv("SECRET_KEY", "insecure-dev-key")

DEBUG = os.getenv("DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = os.getenv(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost"
).split(",")

# 🔧 Fix: filtramos valores vacíos
raw_origins = os.getenv("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [o for o in raw_origins.split(",") if o]

# =========================
# APLICACIONES
# =========================
INSTALLED_APPS = [
    "daphne",

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "channels",
    "django_otp",
    "django_otp.plugins.otp_totp",

    "core",
]

# =========================
# MIDDLEWARE
# =========================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# =========================
# URLS / ASGI / WSGI
# =========================
ROOT_URLCONF = "streaming.urls"

WSGI_APPLICATION = "streaming.wsgi.application"
ASGI_APPLICATION = "streaming.asgi.application"

# =========================
# TEMPLATES
# =========================
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# =========================
# DATABASE
# =========================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

# =========================
# CHANNELS + REDIS
# =========================
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(
                os.getenv("REDIS_HOST", "127.0.0.1"),
                int(os.getenv("REDIS_PORT", "6379")),
            )],
        },
    },
}

# =========================
# PASSWORD VALIDATORS
# =========================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# =========================
# INTERNACIONALIZACIÓN
# =========================
LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

# =========================
# STATIC & MEDIA
# =========================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# =========================
# AUTH
# =========================
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# =========================
# EMAIL (GMAIL)
# =========================
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL")

# =========================
# STREAMING / ENTORNO
# =========================
STREAMING_MODE = os.getenv("STREAMING_MODE", "local")

# HLS: URLs y ruta en disco provistas por .env (ya incluyen /hls según entorno)
HLS_SERVER_URL_HTTP = os.getenv("HLS_SERVER_URL_HTTP")
HLS_SERVER_URL_HTTPS = os.getenv("HLS_SERVER_URL_HTTPS")
HLS_PATH = os.getenv("HLS_PATH")

def get_hls_base_url():
    if STREAMING_MODE == "production" and HLS_SERVER_URL_HTTPS:
        return HLS_SERVER_URL_HTTPS
    return HLS_SERVER_URL_HTTP or "http://127.0.0.1:8080/hls"

HLS_BASE_URL = get_hls_base_url()

# FFmpeg y RTMP interno (para reenvío program)
FFMPEG_BIN_PATH = os.getenv("FFMPEG_BIN_PATH", "ffmpeg")
RTMP_SERVER_HOST_INTERNAL = os.getenv("RTMP_SERVER_HOST_INTERNAL", "127.0.0.1")
RTMP_SERVER_PORT_INTERNAL = int(os.getenv("RTMP_SERVER_PORT_INTERNAL", "9000"))
