from __future__ import absolute_import

from django.conf import settings

from celery import shared_task

from classroom.models import AssignmentSubmission
from classroom.models import SubmissionReview
from classroom.models import GithubUser, Student, AssignmentTask

import tempfile
import os.path
from os import path, walk

from git import Repo, GitCommandError
from github3 import login

GENADY_TOKEN = getattr(settings, 'GENADY_TOKEN', None)


@shared_task
def review_submission(submission_pk):

    gh = login(token=GENADY_TOKEN)

    submission = AssignmentSubmission.objects.get(pk=submission_pk)
    pull_request_number = submission.pull_request.split('/')[-1]
    repo = gh.repository(submission.pull_request.split('/')[-4], submission.pull_request.split('/')[-3])
    author = GithubUser.objects.get(github_id=gh.me().id)

    if author:
        desc = 'Compiled and running without problems!'

        SubmissionReview.objects.create(author=author, submission=submission, points=1, description=desc)

        course_dir = getattr(settings, 'GIT_ROOT', None)

        if not os.path.exists(course_dir):
            print("Cloning...")
            Repo.clone_from("https://github.com/lifebelt/litebelt-test", course_dir)

        r = Repo(course_dir)
        o = r.remotes.origin
        o.pull()

        pr = repo.pull_request(pull_request_number)

        student = Student.objects.get(user__github_id=pr.user.id)

        if not student:
            pr.create_comment("User not recognized as student, calling the police!")
            pr.close()
            pass

        working_dir = os.path.join(course_dir, '{}/{}/{}/'.format(
                                   student.student_class,
                                   submission.assignment.assignment_index,
                                   str(student.student_number).zfill(2)))

        with tempfile.NamedTemporaryFile() as temp:
            temp.write(pr.patch())
            temp.flush()
            try:
                r.git.checkout('HEAD', b='review#{}'.format(submission.id))
                r.git.apply('--ignore-space-change', '--ignore-whitespace', temp.name)

                files = []
                for root, _, filenames in walk(working_dir, topdown=False):
                    files += [
                        (f, path.abspath(path.join(working_dir, f)))
                        for f
                        in filenames
                        if (path.isfile(path.join(root, f)) and
                            (f.endswith('.c') or f.endswith('.C')))
                    ]

                # if everything is okay - merge and pull
                tasks = AssignmentTask.objects.filter(assignment=submission.assignment)

            except GitCommandError:
                pr.create_comment("Git error while preparing to review...")
            finally:
                r.git.clean('-f')
                r.git.checkout('master')
                r.git.checkout('.')
                r.git.branch(D='review#{}'.format(submission.id))

        pr.create_comment(desc)
