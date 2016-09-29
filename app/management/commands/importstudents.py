import argparse
from django.conf import settings
from django.core.management.base import BaseCommand
from app.models import Student
from django.db import IntegrityError

import csv

CSV_FORMAT = getattr(settings, 'CVS_MEMBERS_IMPORT_FORMAT', None)

CLASS_MAPPING = {
    'А': 'A',
    'Б': 'B',
    'В': 'V',
    'Г': 'G',
}


class Command(BaseCommand):
    help = 'Import CSV of students as Django users'

    def add_arguments(self, parser):
        parser.add_argument('csv', nargs=1, type=argparse.FileType('r'))

    def handle(self, *args, **options):

        students = options['csv']

        reader = csv.DictReader(students[0], delimiter=',')
        for row in reader:
            email = row[CSV_FORMAT['email']]
            github = row[CSV_FORMAT['github']].split("/")[-1]

            try:
                user = Student.objects.create_user(email, github)
                user.student_grade = 10
                user.student_class = CLASS_MAPPING[row[CSV_FORMAT['student_class']]]
                user.student_number = row[CSV_FORMAT['student_number']]

                user.firstname = row[CSV_FORMAT['name']].split()[0]
                user.lastname = row[CSV_FORMAT['name']].split()[1]

                user.save()
                self.stdout.write(self.style.SUCCESS('Successfully imported user "%s"' % user.email))
            except IntegrityError:
                    self.stderr.write(self.style.WARNING('Skipping duplicating github id for user "%s"' % github))
                    pass
            except ValueError:
                    self.stderr.write(self.style.ERROR('Invalid data in row: "%s"' % row))
