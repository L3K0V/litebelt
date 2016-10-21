# Litebelt
> Our lifebelt as a teachers... (lite version)

![Lifebelt](https://lh3.googleusercontent.com/IFnHVAhi2wuEdOEn55RbC0JuSCADuGQC39Y4kNbW0CE=w1680-h780-no)

As teacher, you have many responsibilities: to prepare materials, assignments, to check for student precipitating, submitting exams and more. One of the most time-expensive tasks are submission and review of assignments. And so was born the need for a lifebelt.

This project depends very badly on our [elsys-teachers-tools](https://github.com/elsys/elsys-teachers-tools) project (for now).

## Local install guide

0. Prerequisites

  - Python 3.5
  - Redis server

0. Setup django requirements
  ```
  $ pip3 install -r requirements_local.txt
  $ python3 manage.py makemigrations
  $ python3 manage.py migrate
  ```

0. Create superuser, follow instructions
  ```
  $ python3 manage.py createsuperuser
  ```

0. Setup initial data
  ```
  $ python3 manage.py loaddata initial
  $ python3 manage.py importstudents students.csv
  $ python3 manage.py importpulls
  ```

  > Initial data yaml and googledrive.json must be provided to you

0. Run the server locally
  ```
  $ python3 manage.py runserver
  $ python3 manage.py celerycam (optional)
  $ python3 manage.py celery worker -A litebelt --loglevel=info --logfile=CELERY.log
  ```

0. Login to the admin panel
0. Create Github user for Genady form the admin panel

  > skip if you load initial data

## Deploying on Dokku

0. Install these plugins on dokku:
  - https://github.com/dokku/dokku-postgres
  - https://github.com/dokku/dokku-redis

0. Create app, postgres and redis databases on dokku
  ```
  $ dokku apps:create litebelt

  $ dokku postgres:create litebelt
  $ dokku postgres:link litebelit litebelet

  $ dokku redis:create litebelt
  $ dokku redis:link litebelt litebelt
  ```
0. Setup API keys and secrets on dokku

  **Setup API keys and environments**
  http://dokku.viewdocs.io/dokku/configuration/environment-variables/

  Mandatory env keys to set:
    - `SECRET_KEY` for Django.
    - `GENADY_TOKEN` for Django.

  ```
  $ dokku config:set litebelt SERVER_KEY=value
  $ dokku config:set litebelt GENADY_TOKEN=value
  ```

  Make sure all the environment variables are set

  ```
  $ dokku config litebelt
  ```

  **Setup needed files**
  https://github.com/dokku/dokku-copy-files-to-image

  Files:
    - `googledrive.json` - API access for Genady to Google Drive
    - `students.csv` - For importing students
    - `initial.yaml` - For loading initial data in the db


0. Push the application to dokku
  ```
  $ git push dokku master
  ```

  or if you want to push local branch

  ```
  $ git push dokku <local branch>:master
  ```
0. Post configuration
  - Migrate
  - Setup git config for `user.name` and `user.email`
  - Start celery worker
  - Start celerycam

  ```
  $ dokku enter litebelt web.1
  u5643@2015c21f7d50:~$ python manage.py migrate
  u5643@2015c21f7d50:~$ python manage.py celerycam&
  u5643@2015c21f7d50:~$ python3 manage.py celery worker -A litebelt --loglevel=info --logfile=CELERY.log
  ```
