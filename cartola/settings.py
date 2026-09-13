"""Configuracoes do Cartola Nautico."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Le o arquivo .env, se existir. E onde ficam a chave secreta e a chave da API,
# fora do codigo e fora do GitHub. Sem o arquivo, tudo continua funcionando.
try:
    from dotenv import load_dotenv  # type: ignore[reportMissingImports]

    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

# Em producao, defina DJANGO_SECRET_KEY como variavel de ambiente.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "troque-esta-chave-antes-de-publicar")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"
).split(",")
CSRF_TRUSTED_ORIGINS = [
    origem for origem in os.environ.get("DJANGO_CSRF_ORIGINS", "").split(",") if origem
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serve CSS, JS e imagens sem precisar configurar servidor de arquivos.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "cartola.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "cartola.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Recife"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "escalacao"
LOGOUT_REDIRECT_URL = "home"

# Em producao (DJANGO_DEBUG=0) o site so responde por HTTPS.
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    X_FRAME_OPTIONS = "DENY"

# Chave da API-Football (opcional). Ver core/services/api_football.py.
API_FOOTBALL_KEY = os.environ.get("API_FOOTBALL_KEY", "")
# ID do Nautico na API-Football. Pegue no dashboard, em Apis > Football > Ids > Teams.
API_FOOTBALL_TEAM_ID = os.environ.get("API_FOOTBALL_TEAM_ID", "755")
