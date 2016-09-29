from django.http import HttpResponse

from app.models import Student
from classroom.models import CourseAssignment
from classroom.models import AssignmentSubmission

from classroom.tasks import review_submission

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt


@method_decorator(csrf_exempt)
def handle(request):
    if ('pull_request' in request.POST and 'action' in request.POST and 'number' in request.POST):
        if (request.POST['action'] == 'opened' or request.POST['action'] == 'reopened'):
                member = Student.objects.get(github_id=request.POST['pull_request']['user']['id'])

                assignment = CourseAssignment.objects.get(code__in=request.POST['pull_request']['body'].split())

                if assignment:
                    new_submission = AssignmentSubmission.objects.create(
                        assignment=assignment,
                        author=member,
                        pull_request=request.POST['pull_request']['html_url'],
                        grade=0,
                        description=request.POST['pull_request']['body'])

                    if new_submission:
                        review_submission.delay(submission_pk=new_submission.pk)
                        return HttpResponse('Submission created!', status=200)
                    else:
                        return HttpResponse('Submission cannot be created', status=500)

    return HttpResponse('Received but submission not created', status=200)
