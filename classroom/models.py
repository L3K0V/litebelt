from django.db import models
import uuid
from django.db import models
from django.utils import timezone


class Course(models.Model):
    initials = models.CharField(max_length=16, blank=False)
    full_name = models.CharField(max_length=48, blank=False)
    repository = models.URLField(blank=True)
    description = models.TextField()
    year = models.PositiveSmallIntegerField(blank=False)

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '{} ({})'.format(self.full_name, self.year)


class CourseAssignment(models.Model):
    A = 'A'
    B = 'B'
    V = 'V'
    G = 'G'
    ALL = 'ALL'

    ASSIGNMENT_TARGET = (
        (A, 'A class'),
        (B, 'B class'),
        (V, 'V class'),
        (G, 'G class'),
        (ALL, 'ALL classes')
    )

    HOMEWORK = 'H'
    EXAM = 'E'
    PRACTICE = 'P'

    ASSIGNMENT_TYPE = (
        (HOMEWORK, 'Homework'),
        (EXAM, 'Exam'),
        (PRACTICE, 'Practice')
    )

    name = models.CharField(max_length=48)
    description = models.TextField()
    assignment_type = models.CharField(max_length=1, choices=ASSIGNMENT_TYPE, default=HOMEWORK)
    start = models.DateTimeField(default=timezone.now)
    end = models.DateTimeField()
    target = models.CharField(max_length=3, choices=ASSIGNMENT_TARGET, default=ALL)
    code = models.CharField(max_length=200, default=uuid.uuid4, editable=False)

    course = models.ForeignKey('classroom.Course', related_name='assignments')

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class AssignmentTestCase(models.Model):
    assignment = models.ForeignKey('CourseAssignment', related_name='testcases')

    case_input = models.TextField(max_length=8096, blank=True)
    case_output = models.TextField(max_length=8096, blank=True)

    max_memory_usage = models.PositiveSmallIntegerField(default=0)
    max_cpu_usage = models.PositiveSmallIntegerField(default=0)

    flags = models.TextField(max_length=1024, blank=True)


class AssignmentSubmission(models.Model):
    assignment = models.ForeignKey('CourseAssignment', related_name='submissions')
    author = models.ForeignKey('app.Student')

    pull_request = models.URLField(blank=True, null=True)
    grade = models.PositiveSmallIntegerField(default=0)
    description = models.CharField(max_length=256, blank=True)

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('assignment', 'pull_request',)


class SubmissionReview(models.Model):
    submission = models.ForeignKey('AssignmentSubmission', related_name='reviews')
    author = models.ForeignKey('app.Student')

    description = models.TextField()
    points = models.PositiveSmallIntegerField(default=0)

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
