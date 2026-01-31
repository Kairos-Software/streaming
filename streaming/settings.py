import os
from pathlib import Path
from dotenv import load_dotenv

# ======================================================
# BASE
# ======================================================
BASE_DIR = Path(__file__).resolve().parent.parent

# ======================================================
# ENTORNO (.env selector)
# ======================================================
ENV = os.getenv("ENV", "local")

if ENV == "production":
    load_dotenv(BASE_DIR / ".env.production")
else:
    load_dotenv(BASE_DIR / ".env.local")

# ======================================================
# SEGURIDAD
# ======================================================
SECRET_KEY = os.getenv("SECRET_KEY", "insecure-dev-key")

DEBUG = os.getenv("DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = [h.strip() for h in os.getenv(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost"
).split(",") if h]

# CSRF
raw_origins = os.getenv("CSRF_TRUSTED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in raw_origins.split(",") if o]

# ======================================================
# APLICACIONES
# ======================================================
INSTALLED_APPS = [
    "daphne",
    "core",
    "multistream",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "django_otp",
    "django_otp.plugins.otp_totp",
]

# ======================================================
# MIDDLEWARE
# ======================================================
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

# ======================================================
# URLS / ASGI / WSGI
# ======================================================
ROOT_URLCONF = "streaming.urls"
WSGI_APPLICATION = "streaming.wsgi.application"
ASGI_APPLICATION = "streaming.asgi.application"

# ======================================================
# TEMPLATES
# ======================================================
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

# ======================================================
# DATABASE (PostgreSQL)
# ======================================================
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

# ======================================================
# CHANNELS + REDIS
# ======================================================
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

# ======================================================
# INTERNACIONALIZACIÓN
# ======================================================
LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

# ======================================================
# STATIC & MEDIA
# ======================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ======================================================
# AUTH
# ======================================================
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# ======================================================
# EMAIL
# ======================================================
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL")

# ======================================================
# STREAMING / HLS
# ======================================================
STREAMING_MODE = os.getenv("STREAMING_MODE", "local")

HLS_SERVER_URL_HTTP = os.getenv("HLS_SERVER_URL_HTTP")
HLS_SERVER_URL_HTTPS = os.getenv("HLS_SERVER_URL_HTTPS")
HLS_PATH = os.getenv("HLS_PATH")
HLS_PROGRAM_PATH = os.path.join(HLS_PATH, "program")

def get_hls_base_url():
    if STREAMING_MODE == "production" and HLS_SERVER_URL_HTTPS:
        return HLS_SERVER_URL_HTTPS
    return HLS_SERVER_URL_HTTP or "http://127.0.0.1:8080/hls"

HLS_BASE_URL = get_hls_base_url()

# ======================================================
# RTMP / FFMPEG
# ======================================================
FFMPEG_BIN_PATH = os.getenv("FFMPEG_BIN_PATH", "ffmpeg")
RTMP_SERVER_HOST_PUBLIC = os.getenv("RTMP_SERVER_HOST_PUBLIC", "127.0.0.1")
RTMP_SERVER_PORT = int(os.getenv("RTMP_SERVER_PORT", "9000"))
RTMP_SERVER_HOST_INTERNAL = os.getenv("RTMP_SERVER_HOST_INTERNAL", "127.0.0.1")
RTMP_SERVER_PORT_INTERNAL = int(os.getenv("RTMP_SERVER_PORT_INTERNAL", "9000"))

# ======================================================
# LOGGING - ⚡ VERSIÓN CORREGIDA ⚡
# ======================================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    
    # ==========================================
    # FORMATTERS - Cómo se ven los logs
    # ==========================================
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {module}.{funcName} - {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "[{levelname}] {message}",
            "style": "{",
        },
    },
    
    # ==========================================
    # HANDLERS - Dónde van los logs
    # ==========================================
    "handlers": {
        # Handler para consola (lo que ves en el terminal)
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "level": "INFO",
        },
        
        # Handler para archivo (opcional - para debugging)
        "file": {
            "level": "DEBUG",
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "django.log",
            "formatter": "verbose",
        },
    },
    
    # ==========================================
    # LOGGERS - Qué se loguea
    # ==========================================
    "loggers": {
        # ⭐ Logger para MULTISTREAM (esto es lo que faltaba!)
        "multistream": {
            "handlers": ["console", "file"],  # Consola Y archivo
            "level": "INFO",  # Cambiar a DEBUG si necesitas más detalle
            "propagate": False,
        },
        
        # Logger para CORE (tu otra app)
        "core": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        
        # Logger para Django general
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
    
    # ==========================================
    # ROOT - Logger por defecto
    # ==========================================
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}

# ======================================================
# DEBUG VISUAL DE ENTORNO
# ======================================================
print("=== DJANGO ENV ===")
print("ENV:", ENV)
print("DEBUG:", DEBUG)
print("DB_NAME:", os.getenv("DB_NAME"))
print("REDIS:", os.getenv("REDIS_HOST"), os.getenv("REDIS_PORT"))
print("HLS_BASE_URL:", HLS_BASE_URL)
print("RTMP_PUBLIC:", RTMP_SERVER_HOST_PUBLIC, RTMP_SERVER_PORT)
print("RTMP_INTERNAL:", RTMP_SERVER_HOST_INTERNAL, RTMP_SERVER_PORT_INTERNAL)
print("==================")