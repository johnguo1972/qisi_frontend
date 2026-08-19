"""Django settings for front (study room) project."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-change-me')

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    # Reused from tiku
    'apps.common.apps.CommonConfig',
    'apps.papers',
    'apps.parser',
    'apps.review',
    'apps.knowledge',
    # New apps
    'apps.accounts',
    'apps.missions',
    'apps.study',
    'apps.wrongbook',
    'apps.institutions',
    'apps.courses',
    'apps.qrcode',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'qidi_front'),
        'USER': os.environ.get('DB_USER', 'qidi_admin'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'True').lower() == 'true'

# Durable AI queue limits.  These values are deliberately independent from
# Celery worker concurrency: three batch jobs may be active while at most
# sixteen individual question pipelines are leased globally.
AI_MAX_ACTIVE_JOBS = int(os.environ.get('AI_MAX_ACTIVE_JOBS', '3'))
AI_GLOBAL_CONCURRENCY = int(os.environ.get('AI_GLOBAL_CONCURRENCY', '16'))
AI_QUEUE_CAPACITY = int(os.environ.get('AI_QUEUE_CAPACITY', '10000'))
AI_QWEN_CONCURRENCY = int(os.environ.get('AI_QWEN_CONCURRENCY', '16'))
AI_DEEPSEEK_CONCURRENCY = int(os.environ.get('AI_DEEPSEEK_CONCURRENCY', '8'))

# AI calls are long-running and must not be prefetched ahead of available
# workers.  Late acknowledgement allows a lost worker to return its item to
# the broker instead of silently dropping it.
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_ROUTES = {
    'apps.review.tasks.execute_ai_job_item': {'queue': 'ai.batch'},
    'apps.review.tasks.dispatch_queued_ai_items_task': {'queue': 'ai.batch'},
}

CELERY_BEAT_SCHEDULE = {
    'ai-queue-recovery': {
        'task': 'apps.review.tasks.recover_and_dispatch_ai_items',
        'schedule': 5.0,
    },
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get(
            'CACHE_URL',
            f"redis://:{os.environ.get('REDIS_PASSWORD', '')}@{os.environ.get('REDIS_HOST', 'localhost')}:{os.environ.get('REDIS_PORT', '6379')}/3",
        ),
    }
}


# Tencent Cloud SMS
SMS_DEV_MODE = os.environ.get('SMS_DEV_MODE', '0').lower() in ('1', 'true', 'yes')
# A local/test-only account may bypass the SMS cache. Keep this disabled by
# default; deployments must opt in explicitly through their environment.
TEST_LOGIN_ENABLED = os.environ.get('TEST_LOGIN_ENABLED', '0').lower() in ('1', 'true', 'yes')
TEST_LOGIN_PHONE = os.environ.get('TEST_LOGIN_PHONE', '')
TEST_LOGIN_CODE = os.environ.get('TEST_LOGIN_CODE', '')
TENCENT_SMS_SECRET_ID = os.environ.get('TENCENT_SMS_SECRET_ID', '')
TENCENT_SMS_SECRET_KEY = os.environ.get('TENCENT_SMS_SECRET_KEY', '')
TENCENT_SMS_SDK_APP_ID = os.environ.get('TENCENT_SMS_SDK_APP_ID', '1400878428')
TENCENT_SMS_SIGN_NAME = os.environ.get('TENCENT_SMS_SIGN_NAME', '深圳市优途致远信息')
TENCENT_SMS_LOGIN_TEMPLATE_ID = os.environ.get('TENCENT_SMS_LOGIN_TEMPLATE_ID', '2028981')
TENCENT_SMS_REGISTER_TEMPLATE_ID = os.environ.get('TENCENT_SMS_REGISTER_TEMPLATE_ID', '2028979')
TENCENT_SMS_REGION = os.environ.get('TENCENT_SMS_REGION', 'ap-guangzhou')

# JWT settings
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)
JWT_ACCESS_TOKEN_EXPIRE_HOURS = int(os.environ.get('JWT_ACCESS_EXPIRE_HOURS', '24'))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get('JWT_REFRESH_EXPIRE_DAYS', '30'))

# DRF configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.accounts.auth.OptionalJWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'EXCEPTION_HANDLER': 'apps.common.exceptions.api_exception_handler',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# SimpleJWT settings
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=JWT_ACCESS_TOKEN_EXPIRE_HOURS),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# CORS
cors_origins = os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:5173')
CORS_ALLOWED_ORIGINS = [o.strip() for o in cors_origins.split(',') if o.strip()]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False

AUTH_USER_MODEL = 'accounts.UserAccount'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
WECHAT_MP_APPID = os.environ.get('WECHAT_MP_APPID', '')
WECHAT_MP_APPSECRET = os.environ.get('WECHAT_MP_APPSECRET', '')
WECHAT_WEB_APP_ID = os.environ.get('WECHAT_WEB_APP_ID', '')
WECHAT_WEB_APP_SECRET = os.environ.get('WECHAT_WEB_APP_SECRET', '')
WECHAT_WEB_REDIRECT_URI = os.environ.get('WECHAT_WEB_REDIRECT_URI', '')
PUBLIC_WEB_URL = os.environ.get('PUBLIC_WEB_URL', 'https://qisi.chengxuelu.com')

# Aliyun OSS Configuration
ALIYUN_OSS_ACCESS_KEY_ID = os.environ.get('ALIYUN_OSS_ACCESS_KEY_ID', '')
ALIYUN_OSS_ACCESS_KEY_SECRET = os.environ.get('ALIYUN_OSS_ACCESS_KEY_SECRET', '')
ALIYUN_OSS_BUCKET = os.environ.get('ALIYUN_OSS_BUCKET', '')
ALIYUN_OSS_REGION = os.environ.get('ALIYUN_OSS_REGION', 'cn-shanghai')
ALIYUN_OSS_ENDPOINT = os.environ.get('ALIYUN_OSS_ENDPOINT', 'https://oss-cn-shanghai.aliyuncs.com')
