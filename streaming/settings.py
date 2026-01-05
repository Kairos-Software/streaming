import os
from pathlib import Path

# Directorio base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Seguridad
SECRET_KEY = 'django-insecure-zg0x2j(fv!$23%u92=%293997w^#8kd)!5^j*=bpld^)zpkskc'

# En desarrollo lo dejamos en True, en producción debe ser False
DEBUG = True

# Hosts permitidos
ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "192.168.0.186",
    "kaircampanel.grupokairosarg.com",  # Dominio de producción
    "85.209.92.238",  # IP de la VPS
]


# Aplicaciones instaladas
INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'core',  # tu app principal
    'django_otp',
    'django_otp.plugins.otp_totp',

]

# Middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_otp.middleware.OTPMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Configuración de URLs
ROOT_URLCONF = 'streaming.urls'

# Configuración de plantillas
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# WSGI
WSGI_APPLICATION = 'streaming.wsgi.application'
ASGI_APPLICATION = "streaming.asgi.application"

# Configuración de Channels (Redis)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)], # Asegúrate que tu Redis corra aquí
        },
    },
}

# Base de datos (PostgreSQL desde el inicio)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'streaming2',              # nombre exacto de la base en tu VPS
        'USER': 'postgres',         # usuario que creaste en PostgreSQL
        'PASSWORD': 'Psrs950599',  # la contraseña de ese usuario
        'HOST': 'localhost',         # IP pública de tu VPS
        'PORT': '5432',                   # puerto de PostgreSQL
    }
}

# Validación de contraseñas
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internacionalización
LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

# Archivos estáticos
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Archivos multimedia (si subís imágenes/videos)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Tipo de clave primaria por defecto
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"

# --- CONFIGURACIÓN DE CORREO (Desarrollo) ---
# Esto hará que el link de recuperación aparezca en tu terminal (pantalla negra)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ==============================================================================
# CONFIGURACIÓN DE STREAMING (URLs y Puertos)
# ==============================================================================
# Para desarrollo local, estos valores funcionan por defecto
# Para producción en VPS, cambiar según corresponda

# URL base para HLS (streams individuales y programa)
# Desarrollo: http://localhost:8080
# Producción: https://kaircampanel.grupokairosarg.com:9443 (HTTPS) o http://kaircampanel.grupokairosarg.com:9080 (HTTP)
HLS_BASE_URL = os.environ.get('HLS_BASE_URL', 'http://localhost:8080')

# URL RTMP pública (la que se muestra al usuario para conectar OBS)
# Desarrollo: rtmp://127.0.0.1:1935/live
# Producción: rtmp://kaircampanel.grupokairosarg.com:9000/live
RTMP_PUBLIC_URL = os.environ.get('RTMP_PUBLIC_URL', 'rtmp://127.0.0.1:1935/live')

# URL RTMP interna (para FFmpeg, siempre localhost)
# Desarrollo: rtmp://127.0.0.1:9000
# Producción: rtmp://127.0.0.1:9000 (igual, es interno)
RTMP_INTERNAL_HOST = os.environ.get('RTMP_INTERNAL_HOST', '127.0.0.1')
RTMP_INTERNAL_PORT = os.environ.get('RTMP_INTERNAL_PORT', '9000')