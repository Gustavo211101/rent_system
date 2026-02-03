from .base import *

DEBUG = True

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "[::1]",
    ".ngrok-free.app",
    ".ngrok.app",
    ".ngrok.io",
    ".ngrok-free.dev",
] + ALLOWED_HOSTS

CSRF_TRUSTED_ORIGINS = [
    "https://*.ngrok-free.app",
    "https://*.ngrok.app",
    "https://*.ngrok.io",
] + CSRF_TRUSTED_ORIGINS

CSRF_COOKIE_SECURE = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"