from .base import *
from decouple import config

DEBUG = False
SECURE_COOKIES = config('SECURE_COOKIES', default=True, cast=bool)
SESSION_COOKIE_SECURE = SECURE_COOKIES
CSRF_COOKIE_SECURE = SECURE_COOKIES
SECURE_SSL_REDIRECT = SECURE_COOKIES
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

STATIC_ROOT = '/var/www/medicaid/static/'
MEDIA_ROOT = '/var/www/medicaid/media/'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '{levelname} {asctime} {module} {message}', 'style': '{'},
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/medicaid/django.log',
            'maxBytes': 1024 * 1024 * 50,
            'backupCount': 10,
            'formatter': 'verbose',
        },
    },
    'root': {'handlers': ['file'], 'level': 'WARNING'},
    'loggers': {
        'django': {'handlers': ['file'], 'level': 'WARNING', 'propagate': False},
        'imports': {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
        'emedny': {'handlers': ['file'], 'level': 'INFO', 'propagate': False},
    },
}
