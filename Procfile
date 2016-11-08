web: gunicorn litebelt.wsgi --log-file -
worker: python manage.py celery worker -A litebelt --loglevel=info --logfile=CELERY.log
monitor: python manage.py celerycam
