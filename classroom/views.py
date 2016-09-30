from django.http import HttpResponse

from app.models import Student
from classroom.models import Assignment
from classroom.models import AssignmentSubmission

from classroom.tasks import review_submission

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

import json


@method_decorator(csrf_exempt)
def handle(request):
    data = json.loads(request.body.decode("utf-8"))
    if ('pull_request' in data and 'action' in data and 'number' in data):
        # if (data['action'] == 'opened' or data['action'] == 'reopened' or data['action'] == 'synchronize'):
        member = Student.objects.get(user__github_id=data['pull_request']['user']['id'])
        assignment = Assignment.objects.get(code__in=data['pull_request']['body'].split())

        if assignment:
            print('Assignment found, so create submission')
            new_submission = AssignmentSubmission.objects.create(
                assignment=assignment,
                author=member,
                pull_request=data['pull_request']['html_url'],
                grade=0,
                description=data['pull_request']['body'])

            if new_submission:
                print('Submission found, so execute it')
                review_submission.delay(submission_pk=new_submission.pk)
                return HttpResponse('Submission created!', status=200)
            else:
                return HttpResponse('Submission cannot be created', status=500)
        else:
            return HttpResponse('Assigment not found matching this request', status=200)

    return HttpResponse('Received but submission not created', status=200)
