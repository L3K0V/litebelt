from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from classroom.models import Student, AssignmentSubmission

from github3 import login

GENADY_TOKEN = getattr(settings, 'GENADY_TOKEN', None)
COURSE_REPO = getattr(settings, 'COURSE_REPO', None)


class Command(BaseCommand):
    help = 'Import all open pull requests'

    def handle(self, *args, **options):
        gh = login(token=GENADY_TOKEN)
        repo = gh.repository(COURSE_REPO.split('/')[-2], COURSE_REPO.split('/')[-1])

        for pull in repo.pull_requests(state='open'):

            try:
                member = Student.objects.get(user__github_id=pull.user.id)
            except ObjectDoesNotExist:
                member = None

            if not member:
                self.stderr.write(self.style.ERROR('User "{}" not found from pull {}'.format(pull.user, pull)))
                continue

            new_submission, created = AssignmentSubmission.objects.get_or_create(
                author=member,
                pull_request=pull.url)
