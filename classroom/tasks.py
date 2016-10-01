from __future__ import absolute_import

from django.conf import settings

from celery import shared_task

from classroom.models import GithubUser, Student, AssignmentTask, AssignmentSubmission

import tempfile
import os.path
from os import path, walk

from git import Repo, GitCommandError
from github3 import login

GENADY_TOKEN = getattr(settings, 'GENADY_TOKEN', None)


@shared_task
def review_submission(submission_pk):

    gh = login(token=GENADY_TOKEN)
    course_dir = getattr(settings, 'GIT_ROOT', None)

    submission = AssignmentSubmission.objects.get(pk=submission_pk)
    author = GithubUser.objects.get(github_id=gh.me().id)

    if not author:
        return

    api, repo, pull = initialize_repo(submission, course_dir, gh)

    student = Student.objects.get(user__github_id=pull.user.id)
    if not student:
        pull.create_comment("User not recognized as student, calling the police!")
        pull.close()
        pass

    working_dir = os.path.join(course_dir, '{}/{}/{}/'.format(
                               student.student_class,
                               submission.assignment.assignment_index,
                               str(student.student_number).zfill(2)))

    with tempfile.NamedTemporaryFile() as temp:
        temp.write(pull.patch())
        temp.flush()
        try:
            repo.git.checkout('HEAD', b='review#{}'.format(submission.id))
            repo.git.apply('--ignore-space-change', '--ignore-whitespace', temp.name)

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

        except GitCommandError as e:
            print(e)
            pull.create_comment("Git error while preparing to review...")
        finally:
            try:
                print('Cleanup...')
                repo.git.checkout('master')
                repo.git.clean('-fd')
                repo.git.branch(D='review#{}'.format(submission.id))
            except GitCommandError as e:
                print(e)


def clone_repo_if_needed(directory):
    if not os.path.exists(directory):
        print("Cloning...")
        Repo.clone_from("https://github.com/lifebelt/litebelt-test", directory)


def initialize_repo(submission, directory, login):
    clone_repo_if_needed(directory)

    pull_request_number = submission.pull_request.split('/')[-1]

    api = login.repository(submission.pull_request.split('/')[-4], submission.pull_request.split('/')[-3])
    pr = api.pull_request(pull_request_number)

    repo = Repo(directory)
    o = repo.remotes.origin
    o.pull()

    return (api, repo, pr)
