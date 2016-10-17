import uuid
from django.db import models
from django.utils import timezone
from django.conf import settings
import math

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import (
    BaseUserManager, AbstractBaseUser
)

from github3 import login

STUDENT_CLASSES = (
    ('A', 'A'),
    ('B', 'B'),
    ('V', 'V'),
    ('G', 'G')
)

GENADY_TOKEN = getattr(settings, 'GENADY_TOKEN', None)


class GithubUserManager(BaseUserManager):

    def create_user(self, email, github, password=None):
        """
        Creates and saves a User with the given email, github username and password.
        """
        if not email:
            raise ValueError('Student must have an email address')

        if not github:
            raise ValueError('Student must have github username provided')

        user = self.model(
            email=self.normalize_email(email),
            github=github
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, github, password):
        """
        Creates and saves a superuser with the given email, github username and password.
        """
        user = self.create_user(
            email, github, password=password,
        )
        user.is_admin = True
        user.save(using=self._db)
        return user


class GithubUser(AbstractBaseUser):
    email = models.EmailField(
        verbose_name='email address',
        max_length=255,
        unique=True,
    )

    firstname = models.CharField(max_length=64, blank=True)
    lastname = models.CharField(max_length=64, blank=True)

    github = models.CharField(max_length=48, blank=True, unique=True)
    github_id = models.PositiveIntegerField(blank=True, null=True, unique=True)
    github_token = models.CharField(max_length=256, blank=True)
    avatar_url = models.CharField(max_length=256, blank=True)

    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)

    objects = GithubUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['github']

    def get_full_name(self):
        return "{} {}".format(self.firstname, self.lastname)

    def get_short_name(self):
        return self.email

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        "Does the user have a specific permission?"
        # Simplest possible answer: Yes, always
        return True

    def has_module_perms(self, app_label):
        "Does the user have permissions to view the app `app_label`?"
        # Simplest possible answer: Yes, always
        return True

    @property
    def is_staff(self):
        "Is the user a member of staff?"
        # Simplest possible answer: All admins are staff
        return self.is_admin


@receiver(post_save, sender=GithubUser, dispatch_uid="update_github_id")
def update_github_id(sender, instance, **kwargs):
    """
        After save we update the github id based on the github username.
        We user post_save signal to prevent many queries to GitHub if model cannot
        be save because of some constraints.
    """

    # Skip if github is already set
    if instance.github_id:
        return

    gh = login(token=GENADY_TOKEN)

    # Failed logging on github
    if not gh:
        return

    gh_id = gh.user(instance.github).id
    GithubUser.objects.filter(pk=instance.pk).update(github_id=gh_id)


class Student(models.Model):
    user = models.OneToOneField(GithubUser, on_delete=models.CASCADE)

    student_class = models.CharField(max_length=1, choices=STUDENT_CLASSES, blank=True, null=True)
    student_grade = models.PositiveSmallIntegerField(blank=True, null=True)
    student_number = models.PositiveSmallIntegerField(blank=True, null=True)

    def __str__(self):
        return self.user.email

    class Meta:
        unique_together = ('student_grade', 'student_class', 'student_number',)


class Assignment(models.Model):
    name = models.CharField(max_length=64)

    number = models.PositiveIntegerField(unique=True)

    start = models.DateTimeField()
    end = models.DateTimeField()

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    def get_current_score_ratio(self):
        time_left = self.end - timezone.now()
        penalty = 1.0

        if time_left.days > 0:
            return penalty

        multipler = abs(math.floor(time_left.days / 7))

        return 1.0 * (0.7 ** int(multipler))

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Assignment'


class AssignmentTask(models.Model):

    title = models.CharField(max_length=64, blank=False)

    assignment = models.ForeignKey('Assignment', related_name='tasks')

    number = models.PositiveIntegerField(default=1)
    points = models.PositiveSmallIntegerField(default=1)

    def __str__(self):
        return 'Task {} - {}'.format(self.number, self.assignment)

    class Meta:
        unique_together = ('assignment', 'number',)
        verbose_name = 'Task'


class AssignmentTestCase(models.Model):
    tasks = models.ForeignKey('AssignmentTask', related_name='testcases')

    case_input = models.TextField(max_length=8096, blank=True)
    case_output = models.TextField(max_length=8096, blank=True)

    flags = models.TextField(max_length=1024, blank=True)

    def __str__(self):
        return 'Testcase {}'.format(self.id)

    class Meta:
        verbose_name = 'Task Testcase'


class AssignmentSubmission(models.Model):
    author = models.ForeignKey(Student)
    pull_request = models.URLField(blank=True, null=True, unique=True)
    merged = models.BooleanField(default=False)

    def __str__(self):
        return self.pull_request

    class Meta:
        verbose_name = 'Submission'
