web: gunicorn litebelt.wsgi --log-file -
worker: celery worker --beat --app litebelt --loglevel info
