web: gunicorn litebelt.wsgi --log-file -
celery: celery worker --beat --app litebelt --loglevel info
beat: celery beat -app litebelt  
