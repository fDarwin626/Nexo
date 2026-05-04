# config/__init__.py
# This makes Celery start automatically with Django

from .celery import app as celery_app

__all__ = ('celery_app',)