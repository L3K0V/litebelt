web: gunicorn litebelt.wsgi --log-file -
celery: python manage.py celery worker --beat --app litebelt --loglevel info
beat: python manage.py celery beat -app litebelt  
