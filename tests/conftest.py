"""pytest configuration — configures Django in-memory for testing."""
import django
from django.conf import settings


def pytest_configure(config):
    if not settings.configured:
        settings.configure(
            DATABASES={
                'default': {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': ':memory:',
                }
            },
            INSTALLED_APPS=[
                'django.contrib.contenttypes',
                'django.contrib.auth',
                'imports.apps.ImportsConfig',
                'patients.apps.PatientsConfig',
                'eligibility.apps.EligibilityConfig',
                'emedny.apps.EmednyConfig',
            ],
            DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
            SECRET_KEY='test-secret-key-not-for-production',
            USE_TZ=True,
            TIME_ZONE='UTC',
            # eMedNY settings for tests
            EMEDNY_ETIN='0000000001',
            EMEDNY_PROVIDER_ID='TEST001',
            EMEDNY_ORGANIZATION_NAME='Test Organization',
            EMEDNY_USAGE_INDICATOR='T',
            EMEDNY_TAXONOMY_CODE='',
            EMEDNY_SERVICE_TYPE='30',
            EMEDNY_ENDPOINT='http://localhost/test',
            EMEDNY_USERNAME='testuser',
            EMEDNY_PASSWORD='testpass',
            EMEDNY_RECEIVER_ID='EMEDNY',
            EMEDNY_SENDER_ID='TESTSENDER',
            EMEDNY_TIMEOUT=10,
            EMEDNY_MOCK_MODE=True,
            MAX_CSV_FILE_SIZE_BYTES=10 * 1024 * 1024,
            MAX_RETRY_COUNT=3,
            REDIS_URL='redis://127.0.0.1:6379/0',
            CELERY_TASK_ALWAYS_EAGER=True,
            CELERY_TASK_EAGER_PROPAGATES=True,
            CELERY_BROKER_URL='memory://',
            CELERY_RESULT_BACKEND='cache+memory://',
            CACHES={
                'default': {
                    'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
                }
            },
        )
