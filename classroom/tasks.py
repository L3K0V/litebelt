from __future__ import absolute_import

from django.conf import settings

from celery import shared_task

from classroom.models import GithubUser, Student, AssignmentSubmission

import tempfile
import os.path
from os import walk
from enum import Enum

from git import Repo, GitCommandError
from github3 import login

GENADY_TOKEN = getattr(settings, 'GENADY_TOKEN', None)

TESTCASE_TIMEOUT = 1
GCC_TEMPLATE = 'gcc -Wall -std=c11 -pedantic {0} -o {1} -lm 2>&1'
FILENAME_TEMPLATES = ('.*task(\d+)\.[cC]$', '(\d\d+)_.*\.[cC]$')


class TaskStatus(Enum):
    SUBMITTED = 1
    UNSUBMITTED = 0


class ExecutionStatus(Enum):
    MISMATCH = 1
    TIMEOUT = 2
    OTHER = 3


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
        pull.create_comment('User not recognized as student, calling the police!')
        pull.close()
        pass

    working_dir = os.path.join(os.path.join(course_dir, str(pull.user.id)), '{}/{}/{}/'.format(
                               student.student_class,
                               str(submission.assignment.assignment_index).zfill(2),
                               str(student.student_number).zfill(2)))

    with tempfile.NamedTemporaryFile() as temp:
        temp.write(pull.patch())
        temp.flush()
        try:
            # Create working branch and apply the pull-request patch on it
            repo.git.checkout('HEAD', b='review#{}'.format(submission.id))
            repo.git.am('--ignore-space-change', '--ignore-whitespace', temp.name)

            if not os.path.exists(working_dir):
                print('not exists')
                pull.create_comment('Your working folder is not right!')
                return

            for root, _, filenames in walk(working_dir, topdown=False):
                if filenames:
                    publish_result(filenames, pull)
                    break

        except GitCommandError as e:
            print(e)
            pull.create_comment('I have some troubles!')
        finally:
            try:
                print('Cleanup...')
                # Checkout master, clear repo state and delete work branch
                repo.git.checkout('master')
                repo.git.checkout('.')
                repo.git.clean('-fd')
                repo.git.branch(D='review#{}'.format(submission.id))
            except GitCommandError as e:
                print(e)


def clone_repo_if_needed(directory):
    if not os.path.exists(directory):
        print('Cloning...')
        Repo.clone_from('https://github.com/elsys/c-programming-homework', directory)


def initialize_repo(submission, directory, login):
    pull_request_number = submission.pull_request.split('/')[-1]

    api = login.repository(submission.pull_request.split('/')[-4], submission.pull_request.split('/')[-3])
    pr = api.pull_request(pull_request_number)

    clone_repo_if_needed(os.path.join(directory, str(pr.user.id)))

    repo = Repo(os.path.join(directory, str(pr.user.id)))
    o = repo.remotes.origin
    o.pull()

    return (api, repo, pr)


def publish_result(okay, pull):

    if okay:
        pull.create_comment('Nice one!')

    if (okay and not pull.is_merged() and pull.mergeable):
        print('Merge successfull? = {}'.format(pull.merge(commit_message='Everything looks good, merging...', squash=True)))
