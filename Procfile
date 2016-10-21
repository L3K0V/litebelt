web: gunicorn litebelt.wsgi --log-file -
worker: python3 manage.py celery worker -A litebelt --loglevel=info --logfile=CELERY.log
