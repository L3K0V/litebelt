from django.http import HttpResponse
from django.views import View

from app.models import Student
from classroom.models import CourseAssignment
from classroom.models import AssignmentSubmission

from classroom.tasks import review_submission


class GitHubReceiveHook(View):
    def post(self, request):
        if ('pull_request' in request.data and 'action' in request.data and 'number' in request.data):
            if (request.data['action'] == 'opened' or request.data['action'] == 'reopened'):
                    member = Student.objects.get(github_id=request.data['pull_request']['user']['id'])

                    assignment = CourseAssignment.objects.get(code__in=request.data['pull_request']['body'].split())

                    if assignment:
                        new_submission = AssignmentSubmission.objects.create(
                            assignment=assignment,
                            author=member,
                            pull_request=request.data['pull_request']['html_url'],
                            grade=0,
                            description=request.data['pull_request']['body'])

                        if new_submission:
                            review_submission.delay(submission_pk=new_submission.pk)
                            return HttpResponse('Submission created!', status=200)
                        else:
                            return HttpResponse('Submission cannot be created', status=500)

        return HttpResponse('Received but submission not created', status=200)
