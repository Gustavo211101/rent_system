from .base import *

DEBUG = False

# In prod you MUST set:
#   DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
#   DJANGO_CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
#   DJANGO_SECRET_KEY=...

STATIC_ROOT = BASE_DIR / "staticfiles"

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

# Optionally enable HTTPS redirect in real prod:
# SECURE_SSL_REDIRECT = True
