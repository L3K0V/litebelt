from __future__ import absolute_import

from django.db.models import Sum
from django.conf import settings

from celery import shared_task
from celery.utils.log import get_task_logger

from classroom.utils import HeadquartersHelper
from classroom.models import GithubUser, Student, Assignment, AssignmentTask, AssignmentSubmission

import re
import shlex
import math
import tempfile
import itertools
from enum import Enum
from os import path, sep
from subprocess import Popen, PIPE, TimeoutExpired

from git import Repo, GitCommandError
from github3 import login

log = get_task_logger(__name__)

GENADY_TOKEN = getattr(settings, 'GENADY_TOKEN', None)
COURSE_REPO = getattr(settings, 'COURSE_REPO', None)

TESTCASE_TIMEOUT = 1
GCC_TEMPLATE = 'gcc -Wall -std=c11 -pedantic {0} -o {1} -lm 2>&1'
FILENAME_TEMPLATES = ('.*task(\d+)\.[cC]$', '(\d\d+)_.*\.[cC]$')
FOLDER_TEMPLATE = ('([ABVG])\/(\d+)\/(\d+)\/.+[cC]$')


class TaskStatus(Enum):
    SUBMITTED = 1
    UNSUBMITTED = 0


class ExecutionStatus(Enum):
    MISMATCH = 1
    TIMEOUT = 2
    OTHER = 3


@shared_task()
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
        return

    with tempfile.NamedTemporaryFile() as temp:
        temp.write(pull.patch())
        temp.flush()
        try:
            # Create working branch and apply the pull-request patch on it
            repo.git.checkout('HEAD', b='review#{}'.format(submission.id))
            repo.git.am('--ignore-space-change', '--ignore-whitespace', temp.name)

            summary = []
            completed_tasks = []
            unrecognized_files = []

            for current in pull.files():
                abs_path = path.join(path.join(course_dir, str(pull.user.id)), current)
                student_class, hw_number, student_number = get_info_from_filename(current.filename)
                task_index = get_task_number_from_filename(current.filename)

                if not student_class:
                    continue

                homework = Assignment.objects.filter(number=hw_number)

                if not homework:
                    pull.create_comment('I cannot recognize and grade homework for file `{}`'.format(current))
                    continue

                tasks = AssignmentTask.objects.filter(assignment=homework)
                tasks_count = len(tasks)
                tasks_points = tasks.aggregate(Sum('points'))

                if (task_index is None or
                        task_index > tasks_count or
                        task_index <= 0):
                    unrecognized_files.append({
                        'name': current
                    })
                    continue

                if student_class is not student.student_class or student_number is not student.student_number:
                    pull.create_comment('File `{}` is not it your personal folder! I cannot merge this!'.format(current))
                    continue

                selected = tasks.get(number=task_index)

                completed_tasks.append(task_index)
                task = {}
                task['name'] = selected.title
                task['index'] = task_index
                task['points'] = selected.points

                compiled_name = current.split('.')[0] + '.out'
                exec_path = path.abspath(path.join(course_dir, compiled_name))

                gcc_invoke = GCC_TEMPLATE.format(shlex.quote(abs_path),
                                                 shlex.quote(exec_path))

                out, err, code = execute(gcc_invoke, timeout=10)
                msg = out + err

                if code != 0:
                    summary.append({
                        'status': TaskStatus.SUBMITTED,
                        'compiled': False,
                        'compiler_exit_code': code,
                        'compiler_message': remove_path_from_output(
                            path.abspath(course_dir), msg.decode()),
                        'task': task
                    })
                    continue

                testcases = []
                for test in selected.testcases.all():
                    try:
                        (stdout, stderr, exitcode) = \
                            execute(exec_path,
                                    input=test.case_input.encode('utf-8'))
                    except (FileNotFoundError, IOError, Exception):
                        testcases.append({
                            "index": test.id,
                            "success": False,
                            "status": ExecutionStatus.OTHER,
                        })
                        continue

                    output = stdout.decode('latin-1') or ""
                    output = " ".join(
                        filter(None, [line.strip() for line in output.split('\n')]))
                    if exitcode != 0:
                        testcases.append({
                            "index": test.id,
                            "success": False,
                            "status": ExecutionStatus.TIMEOUT,
                            "input": test.case_input,
                        })
                        continue

                    if output == test.case_output:
                        testcases.append({
                            "index": test.id,
                            "success": True
                        })
                    else:
                        testcases.append({
                            "index": test.id,
                            "success": False,
                            "status": ExecutionStatus.MISMATCH,
                            "input": test.case_input,
                            "output": output,
                            "expected": test.case_output,
                        })

                summary.append({
                    "status": TaskStatus.SUBMITTED,
                    "compiled": True,
                    "task": task,
                    "testcases": testcases,
                    "compiler_message": remove_path_from_output(
                        path.abspath(course_dir), msg.decode())
                })

            # Report for unsubmitted tasks
            for unsubmitted in tasks.exclude(number__in=completed_tasks):
                task = {}
                task['name'] = unsubmitted.title
                task['index'] = unsubmitted.number
                task['points'] = unsubmitted.points
                summary.append({
                    'status': TaskStatus.UNSUBMITTED,
                    'compiled': False,
                    'task': task
                })

            publish_result(summary, unrecognized_files, pull, tasks_points,
                           submission.assignment.get_current_score_ratio())

            publish_to_headquarters(summary,
                                    student.user.get_full_name(),
                                    submission.assignment.number,
                                    submission.assignment.get_current_score_ratio())

        except GitCommandError as e:
            print(e)
            pull.create_comment('I have some troubles with git!\n\n```\n{}\n```\n'.format(e))
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
    Returns tuple of students' class, homework and student's number
    """
    match = re.match(FOLDER_TEMPLATE, filename, flags=0)
    if match:
        return (str(match.group(1)), int(match.group(2)), int(match.group(3)))

    return (None, None, None)


def get_task_number_from_filename(filename):
    for regexp_str in FILENAME_TEMPLATES:
        match = re.match(regexp_str, filename, flags=0)
        if match:
            return int(match.group(1))
    return None


def remove_path_from_output(folder, output):
    return output.replace(folder + sep, '')


def execute(command, input=None, timeout=1):
    proc = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)

    try:
        std_out, std_err = proc.communicate(timeout=timeout, input=input)
    except TimeoutExpired:
        proc.kill()
        std_out, std_err = proc.communicate()

    return (std_out, std_err, proc.returncode)


def publish_result(summary, unrecognized, pull, points, penalty):
    sb = []
    for task in sorted(summary, key=lambda x: x['task']['index']):
        task_ = task["task"]
        sb.append(
            "## Task {}: {} [{}/{} points]\n".format(
                task_["index"],
                task_["name"],
                get_points_for_task(task),
                task_["points"]))

        if task["status"] is TaskStatus.UNSUBMITTED:
            sb.append("### Not submitted\n")
            continue

        if not task["compiled"]:
            sb.append("Failed compiling\n")
            sb.append("Exit code: {}\n".format(task["compiler_exit_code"]))
            sb.append("Error\n")
            sb.append("```\n{}\n```\n".format(task["compiler_message"]))
            continue

        if task["compiler_message"]:
            print("Compiled with warning(s)\n")
            sb.append("```\n{}\n```\n".format(task["compiler_message"]))

        for testcase in task["testcases"]:
            sb.append("### Testcase {}\n".format(testcase["index"]))

            if testcase["success"]:
                sb.append("passed\n")
                continue

            sb.append("failed\n")
            if testcase["status"] is ExecutionStatus.MISMATCH:
                sb.append("Input:\n")
                sb.append("```\n{}\n```\n\n".format(testcase["input"]))
                sb.append("Expected:\n")
                sb.append("```\n{}\n```\n\n".format(testcase["expected"]))
                sb.append("Output:\n")
                sb.append("```\n{}\n```\n\n".format(testcase["output"]))
            elif testcase["status"] is ExecutionStatus.TIMEOUT:
                sb.append("Execution took more than {} seconds\n".format(TESTCASE_TIMEOUT))

    if len(unrecognized) > 0:
        sb.append('## Unrecognized files')
        sb.append('\n')

        for unrecognized in sorted(unrecognized, key=lambda x: x['name']):
            sb.append('- {}'.format(unrecognized['name']))

    earned_points = get_earned_points(summary)

    sb.append('\n\n')
    sb.append('## Overall\n\n')
    sb.append('### Points earned: **{}** of max **{}**\n'.format(
              earned_points, points['points__sum']))

    pull.create_comment(''.join(sb))

    if (get_earned_points(summary) >= points['points__sum'] * penalty and not pull.is_merged() and pull.mergeable):
        pull.merge(commit_message='Everything looks good, merging...', squash=True)


def publish_to_headquarters(summary, name, homework, penalty):
    hq = HeadquartersHelper()
    hq.select_worksheet('Grades')

    current_points = HeadquartersHelper.formula_to_points(hq.get_student_homework(name, homework)[2])
    review_points = [get_points_for_task(task) * penalty for task in sorted(summary, key=lambda x: x['task']['index'])]
    new_points = list(map(lambda pair: max(pair),
                      itertools.zip_longest(current_points, review_points, fillvalue=0.0)))

    hq.update_student_homework(name, homework, HeadquartersHelper.points_to_formula(new_points))


def get_total_points(summary):
    return sum(map(lambda x: x['task']['points'], summary))


def get_points_for_task(task):
    if "testcases" not in task:
        return 0
    correct_tc = sum(testcase["success"] for testcase in task["testcases"])

    points = task['task']['points'] * \
        float(correct_tc) / len(task["testcases"])

    if task["compiler_message"]:
        points -= correct_tc

    return math.ceil(points)


def get_earned_points(summary):
    result = 0
    for task in summary:
        if task.get("testcases") is None:
            continue

        result += get_points_for_task(task)
    return result
