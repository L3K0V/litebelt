from django.http import HttpResponse

from classroom.models import Student
from classroom.models import Assignment
from classroom.models import AssignmentSubmission

from classroom.tasks import review_submission

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

import json


@method_decorator(csrf_exempt)
def handle(request):
    data = json.loads(request.body.decode("utf-8"))

    if ('pull_request' not in data and 'action' not in data and 'number' not in data):
        # Not a pull request
        return HttpResponse('Received but not processed', status=202)

    if (data['action'] == 'closed'):
        # We are not supporting this hook when pull-request is closing
        return HttpResponse('Received but already processed and finished', status=202)

    member = Student.objects.get(user__github_id=data['pull_request']['user']['id'])
    assignment = Assignment.objects.get(code__in=data['pull_request']['body'].split())

    if not member:
        return HttpResponse('User not recognized as student, calling the police!', status=202)

    if not assignment:
        return HttpResponse('Assigment not found matching this request', status=202)

    new_submission, created = AssignmentSubmission.objects.get_or_create(
        assignment=assignment,
        author=member,
        pull_request=data['pull_request']['html_url'])

    if new_submission:
        review_submission.delay(submission_pk=new_submission.pk)
        if created:
            return HttpResponse('Submission created, now processing!', status=201)
        else:
            return HttpResponse('Submission already created, now processing again!', 200)
    else:
        return HttpResponse('Submission cannot be created', status=202)
