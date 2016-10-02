# Litebelt
## Local install guide

1. Prerequisites

  - Python 3.5
  - Redis

2. Setup django requirements
  ```
  $ pip3 install -r requirements.txt
  $ python3 manage.py makemigrations
  $ python3 manage.py migrate
  ```

3. Create superuser, follow instructions to enable write access and manage oauth applications
  ```
  $ python3 manage.py createsuperuser
  ```

4. Run the server locally
  ```
  $ python3 manage.py runserver
  ```

5. Login to the admin panel
6. Create Github user for Genady form the admin panel

## Deploying on Dokku

1. Install these plugins on dokku:
  - `https://github.com/dokku/dokku-postgres`
  - `https://github.com/dokku/dokku-redis`

2. Create postgres and redis databases on dokku
3. Create application for litebelt on dokku
4. Setup API keys and secrets on dokku

  **Setup API keys and environments**
  http://dokku.viewdocs.io/dokku/configuration/environment-variables/

  Mandatory env keys to set:
    - `SECRET_KEY` for Django.
    - `GENADY_TOKEN` for Django.

5. Push the application to dokku
6. Enter deployed litebelt web container and:

   - Start celery worker
   - Start celerycam
