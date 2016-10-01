from __future__ import absolute_import

from django.conf import settings

from celery import shared_task

from classroom.models import GithubUser, Student, AssignmentTask, AssignmentSubmission

import tempfile
import os.path
from os import path, walk
import re
from enum import Enum
from subprocess import Popen, PIPE, TimeoutExpired

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
            # Create working branch and apply the pull-request patch on it
            repo.git.checkout('HEAD', b='review#{}'.format(submission.id))
            repo.git.am('--ignore-space-change', '--ignore-whitespace', temp.name)

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
            summary = []
            completed_tasks = []
            tasks = AssignmentTask.objects.filter(assignment=submission.assignment)

            for current, abs_path in files:
                task_index = get_task_number_from_filename(current)
                if task_index is not None:
                    completed_tasks.append(task_index)
                    task = {}
                    task['name'] = tasks.get(number=task_index).title
                    task['points'] = tasks.get(number=task_index).points
                    task['index'] = task_index
                else:
                    task = {}
                    task['name'] = 'Unrecognized'
                    task['desc'] = "File name doesn't not match any of filenames conventions"
                    task['index'] = -1

                if not is_valid_taskname(current):
                    summary.append({
                        "status": TaskStatus.SUBMITTED,
                        "name_matching": False,
                        "file_name": current,
                        "task": task
                    })
                    continue

                compiled_name = current.split('.')[0] + ".out"
                exec_path = path.abspath(path.join(course_dir, compiled_name))

                gcc_invoke = GCC_TEMPLATE.format(abs_path, exec_path)

                out, err, code = execute(gcc_invoke)

                if code != 0:
                    summary.append({
                        "status": TaskStatus.SUBMITTED,
                        "compiled": False,
                        "compiler_exit_code": code,
                        "compiler_message": out.decode('latin-1'),
                        "task": task
                    })
                    continue

            publish_result(summary, pull)

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


def is_valid_taskname(filename):
    for regexp_str in FILENAME_TEMPLATES:
        match = re.match(regexp_str, filename, flags=0)
        if match:
            return True

    return False


def get_task_number_from_filename(filename):
    for regexp_str in FILENAME_TEMPLATES:
        match = re.match(regexp_str, filename, flags=0)
        if match:
            return int(match.group(1))
    return None


def execute(command, input=None, timeout=1):
    proc = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)

    try:
        std_out, std_err = proc.communicate(timeout=timeout, input=input)
    except TimeoutExpired:
        proc.kill()
        std_out, std_err = proc.communicate()

    return (std_out, std_err, proc.returncode)


def publish_result(summary, pull):
    sb = []
    for task in sorted(summary, key=lambda x: x['task']['index']):
        sb.append("## {} (Task {})\n".format(task['task']['name'], task['task']['index']))

        if 'name_matching' in task:
            sb.append("**Filename: {}**\n".format(task['file_name']))
            continue

        if task["status"] is TaskStatus.UNSUBMITTED:
            sb.append("### Not submitted\n")
            continue

        if not task["compiled"]:
            sb.append("Failed compiling\n")
            sb.append("Exit code: {}".format(task["compiler_exit_code"]))
            sb.append("\n")
            sb.append("Error\n```\n{}\n```\n".format(task["compiler_message"]))
            sb.append("\n")
            continue

    pull.create_comment(''.join(sb))
