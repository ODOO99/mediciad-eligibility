"""Base settings shared by all environments."""
import os
from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('DJANGO_SECRET_KEY')
DEBUG = config('DJANGO_DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Local apps
    'imports.apps.ImportsConfig',
    'patients.apps.PatientsConfig',
    'eligibility.apps.EligibilityConfig',
    'emedny.apps.EmednyConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='medicaid_eligibility'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
            'connect_timeout': 10,
            'options': '-c search_path=medicaid_schema,public',
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = config('APP_TIMEZONE', default='America/New_York')
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Redis
REDIS_URL = config('REDIS_URL', default='redis://127.0.0.1:6379/0')

# Celery
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_SOFT_TIME_LIMIT = 120
CELERY_TASK_TIME_LIMIT = 180
CELERY_BEAT_SCHEDULE = {}

# Dedicated queue for medicaid-eligibility tasks.
# This prevents the shared 'celery' default queue from letting the Medicaid-Back-End
# Celery worker accidentally consume (and crash on) imports.tasks.* messages.
CELERY_TASK_DEFAULT_QUEUE = 'eligibility'
CELERY_TASK_ROUTES = {
    'imports.tasks.process_import_batch': {'queue': 'eligibility'},
    'imports.tasks.process_import_row': {'queue': 'eligibility'},
    'imports.tasks.watch_batch_completion': {'queue': 'eligibility'},
}

# Cache (used for SSE channel state)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
        'TIMEOUT': 3600,
    }
}

# Sessions
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# eMedNY settings
EMEDNY_ENDPOINT = config('EMEDNY_ENDPOINT', default='https://www.emedny.org/ebiz/core/eligibility/RealTimeTransaction')
EMEDNY_USERNAME = config('EMEDNY_USERNAME', default='')
EMEDNY_PASSWORD = config('EMEDNY_PASSWORD', default='')
EMEDNY_ETIN = config('EMEDNY_ETIN', default='')
EMEDNY_PROVIDER_ID = config('EMEDNY_PROVIDER_ID', default='')
EMEDNY_ORGANIZATION_NAME = config('EMEDNY_ORGANIZATION_NAME', default='')
EMEDNY_SENDER_ID = config('EMEDNY_SENDER_ID', default='')
EMEDNY_RECEIVER_ID = config('EMEDNY_RECEIVER_ID', default='EMEDNYREL')
EMEDNY_USAGE_INDICATOR = config('EMEDNY_USAGE_INDICATOR', default='T')
EMEDNY_TAXONOMY_CODE = config('EMEDNY_TAXONOMY_CODE', default='')
EMEDNY_SERVICE_TYPE = config('EMEDNY_SERVICE_TYPE', default='30')
EMEDNY_TIMEOUT = config('EMEDNY_TIMEOUT', default=30, cast=int)
EMEDNY_MOCK_MODE = config('EMEDNY_MOCK_MODE', default=True, cast=bool)

# WS-Security credentials (for SOAP header only).
# If blank, falls back to EMEDNY_USERNAME / EMEDNY_PASSWORD.
# Some eMedNY gateway configurations authenticate using the ETIN (EMEDNY_ETIN)
# as the WS-Security username rather than the web-services username.
EMEDNY_WS_USERNAME = config('EMEDNY_WS_USERNAME', default='')
EMEDNY_WS_PASSWORD = config('EMEDNY_WS_PASSWORD', default='')

# Import settings
MAX_CSV_FILE_SIZE_MB = config('MAX_CSV_FILE_SIZE_MB', default=10, cast=int)
MAX_CSV_FILE_SIZE_BYTES = MAX_CSV_FILE_SIZE_MB * 1024 * 1024
MAX_RETRY_COUNT = config('MAX_RETRY_COUNT', default=3, cast=int)
CELERY_CONCURRENCY = config('CELERY_CONCURRENCY', default=4, cast=int)

# Security
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_BROWSER_XSS_FILTER = True
