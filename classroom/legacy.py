from io import StringIO
import os

from elsys_tools.homework.evaluator import main as legacy_script
from elsys_tools.homework.evaluator import get_points_for_task


def execute(directory, student_class, student_number, homework, penalty):

    abs_path = os.path.join(directory, student_class,
                            str(homework.number).zfill(2),
                            str(student_number).zfill(2))

    tasks = homework.tasks.all()
    tmp_tasks = []
    earned_points = []

    for t in tasks:
        tmp_tasks.append({
            'name': t.title,
            'desc': t.description,
            'points': t.points,
            'testcase': [{'input': i.case_input, 'output': i.case_output} for i in t.testcases.all()]
        })

    # Legacy script args
    tasks_dict = {'task': tmp_tasks}
    args = [abs_path, '/dev/null']
    log = StringIO()

    def post_process(summary):
        for task in sorted(summary, key=lambda x: x["task"]["index"]):
            earned_points.append(get_points_for_task(task))

        return summary

    legacy_script(args, tasks_dict, post_process, log)

    res = log.getvalue()

    log.close()

    return res, earned_points
