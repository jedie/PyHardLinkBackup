"""
Django settings for pyhardlinkbackup project.

Generated by 'django-admin startproject' using Django 1.8.8.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.8/ref/settings/
"""

import os
# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import tempfile

# https://github.com/jedie/PyHardLinkBackup
from pyhardlinkbackup.phlb.config import phlb_config as _phlb_config

# _phlb_config.print_config()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Username/password for pyhardlinkbackup.backup_app.middleware.AlwaysLoggedInAsSuperUser
DEFAULT_USERNAME = "AutoLoginUser"
DEFAULT_USERPASS = "no password needed!"

INSTALLED_APPS = (
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "pyhardlinkbackup.backup_app",
)
ROOT_URLCONF = "pyhardlinkbackup.django_project.urls"


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "no-secet"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


MIDDLEWARE = (
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # WARNING:
    # This will 'disable' the authentication, because
    # the default user will always be logged in.
    # But only if phlb_config["ENABLE_AUTO_LOGIN"] == True
    "pyhardlinkbackup.backup_app.middleware.AlwaysLoggedInAsSuperUser",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.security.SecurityMiddleware",
)

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        'DIRS': [
            os.path.join(BASE_DIR, "django_project", "templates"),
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "pyhardlinkbackup.backup_app.context_processors.phlb_version_string",
            ]
        },
    }
]


# Database
# https://docs.djangoproject.com/en/1.8/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _phlb_config.database_name,
        "TEST_NAME": ":memory:"
    }
}
print(f"Use Database file: '{DATABASES['default']['NAME']}'")

# Internationalization
# https://docs.djangoproject.com/en/1.8/topics/i18n/

# https://docs.djangoproject.com/en/1.8/ref/settings/#std:setting-LANGUAGE_CODE
LANGUAGE_CODE = _phlb_config.language_code

USE_TZ = False
TIME_ZONE = "UTC"

USE_I18N = True
USE_L10N = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.8/howto/static-files/

STATIC_URL = "/static/"


_file_object, LOG_FILEPATH = tempfile.mkstemp(prefix="pyhardlinkbackup_", suffix=".log")
print(f"temp log file: {LOG_FILEPATH}")
with open(_file_object, "w") as f:
    f.write("\n\n")
    f.write("_" * 79)
    f.write("\n")
    f.write(f"Start low level logging from: {__file__}\n")
    f.write("\n")

# CRITICAL 	50
# ERROR 	40
# WARNING 	30
# INFO 	    20
# DEBUG 	10
# NOTSET 	0
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': LOG_FILEPATH,
            'level': 'DEBUG',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        '': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': False
        },
        'django': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': False
        },
        'pyhardlinkbackup': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': False
        },
        'pyhardlinkbackup.phlb.path_helper': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False
        },
        'pyhardlinkbackup.backup_app.models': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False
        },
    },
}
