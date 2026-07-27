from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']

# Run Celery tasks asynchronously using a background worker
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = True

# Show emails in console during development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'imports': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
        'emedny': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
        'eligibility': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
    },
}
