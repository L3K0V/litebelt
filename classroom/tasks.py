from __future__ import absolute_import

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from celery import shared_task
from celery.utils.log import get_task_logger

from classroom.utils import HeadquartersHelper
from classroom.legacy import execute
from classroom.models import GithubUser, Student, Assignment, AssignmentSubmission

import re
from collections import defaultdict
import itertools
from enum import Enum
from os import path

from git import Repo, GitCommandError
from github3 import login

log = get_task_logger(__name__)

GENADY_TOKEN = getattr(settings, 'GENADY_TOKEN', None)
COURSE_REPO = getattr(settings, 'COURSE_REPO', None)
COURSE_DIR = getattr(settings, 'GIT_ROOT', None)

TESTCASE_TIMEOUT = 1
GCC_TEMPLATE = 'gcc -Wall -std=c11 -pedantic {0} -o {1} -lm 2>&1'
FILENAME_TEMPLATES = ('(\d+)_.*\.[cC]', '.*task(\d+)\.[cC]$')
FOLDER_TEMPLATE = ('([ABVG])\/(\d+)\/(\d+)\/(.+\.[cC])$')


class TaskStatus(Enum):
    SUBMITTED = 1
    UNSUBMITTED = 0


class ExecutionStatus(Enum):
    MISMATCH = 1
    TIMEOUT = 2
    OTHER = 3


@shared_task()
def config_classroom_repo(repo, host):

    gh = login(token=GENADY_TOKEN)

    repo_obj = gh.repository(repo.split('/')[-2], repo.split('/')[-1])
    repo_obj.add_collaborator(gh.me())
    repo_obj.create_hook('web',
                         {'url': 'http://{}/{}'.format(host, 'github/receive'),
                          'content_type': 'json'}, events=[u'push'], active=True)


@shared_task()
def review_submission(submission_pk, force_merge=False):

    gh = login(token=GENADY_TOKEN)

    submission = AssignmentSubmission.objects.get(pk=submission_pk)
    author = GithubUser.objects.get(github_id=gh.me().id)

    if not author:
        return

    api, repo, pull = initialize_repo(submission, COURSE_DIR, gh)

    if pull.is_merged():
        return

    student = Student.objects.get(user__github_id=pull.user.id)
    if not student:
        pull.create_comment('User not recognized as student, calling the police!')
        pull.close()
        return

    try:
        # Create working branch and apply the pull-request patch on it
        repo.git.fetch('origin', 'pull/{}/head:review#{}'.format(
                       submission.pull_request.split('/')[-1], submission.id))
        repo.git.checkout('review#{}'.format(submission.id))

        homeworks_dict = defaultdict(lambda: {})

        happy_merging = True
        errors = []

        for current in pull.files():
            student_class, hw_number, student_number, filename = get_info_from_filename(current.filename)

            if not student_class:
                errors.append('Wrong working dir for file `{}`'.format(current))
                happy_merging = False
                continue

            try:
                homework = Assignment.objects.get(number=hw_number)
            except ObjectDoesNotExist:
                homework = None

            if not homework:
                errors.append('I cannot recognize and grade homework for file `{}`'.format(current))
                happy_merging = False
                continue

            if student_class is not student.student_class or student_number is not student.student_number:
                errors.append('File `{}` is not it your personal folder! I cannot merge this!'.format(current))
                happy_merging = False
                continue

            homeworks_dict[hw_number]['homework'] = homework

        pull.create_comment('\n'.join(errors))

        for h, v in homeworks_dict.items():
            summary, points = execute(path.join(COURSE_DIR, str(pull.user.id)),
                                      student_class, student_number,
                                      v['homework'], v['homework'].get_current_score_ratio())

            happy_merging = happy_merging and (sum(points) == v['homework'].get_overall_points())

            pull.create_comment(summary)
            publish_to_headquarters(points, student.user.get_full_name(),
                                    h, v['homework'].get_current_score_ratio())

        merge(pull, force_merge or happy_merging)

    except GitCommandError as e:
        print(e)
        pull.create_comment('I have some troubles with git!\n\n```\n{}\n```\n'.format(e))

        # Abort patching on fail to prevent future errors regarding patching.
        # We suppose this will return the local repo in clean rebase state.
        repo.git.am('--abort')
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
    if not path.exists(directory):
        print('Cloning...')
        Repo.clone_from(COURSE_REPO, directory)


def initialize_repo(submission, directory, login):
    pull_request_number = submission.pull_request.split('/')[-1]

    api = login.repository(submission.pull_request.split('/')[-4], submission.pull_request.split('/')[-3])
    pr = api.pull_request(pull_request_number)

    clone_repo_if_needed(path.join(directory, str(pr.user.id)))

    repo = Repo(path.join(directory, str(pr.user.id)))
    o = repo.remotes.origin
    o.pull()

    return (api, repo, pr)


def is_valid_taskname(filename):
    for regexp_str in FILENAME_TEMPLATES:
        match = re.match(regexp_str, filename, flags=0)
        if match:
            return True

    return False


def is_vaid_filename(filename):
    match = re.match(FOLDER_TEMPLATE, filename, flags=0)
    if match:
        return True

    return False


def get_info_from_filename(filename):
    """
    Geeting specific infor from the filename.
    Returns tuple of students' class, homework and student's number and filename
    """
    match = re.match(FOLDER_TEMPLATE, filename, flags=0)
    if match:
        return (str(match.group(1)), int(match.group(2)), int(match.group(3)), str(match.group(4)))

    return (None, None, None, None)


def get_task_number_from_filename(filename):
    for regexp_str in FILENAME_TEMPLATES:
        match = re.match(regexp_str, filename, flags=0)
        if match:
            return int(match.group(1))
    return None


def merge(pull, force_merge):
    if force_merge:
        pull.create_comment('Merging...')
    else:
        pull.create_comment('Not fully correct. Fix your tasks and submit them.')

    if (force_merge and (not pull.is_merged() and pull.mergeable)):
        pull.merge(commit_message='Everything looks good, merging...', squash=True)


def publish_to_headquarters(earned, name, homework, penalty):
    hq = HeadquartersHelper()
    hq.select_worksheet('Grades')

    current_points = HeadquartersHelper.formula_to_points(hq.get_student_homework(name, homework)[2])
    review_points = [task * penalty for task in earned]
    new_points = list(map(lambda pair: max(pair),
                      itertools.zip_longest(current_points, review_points, fillvalue=0.0)))

    hq.update_student_homework(name, homework, HeadquartersHelper.points_to_formula(new_points))
