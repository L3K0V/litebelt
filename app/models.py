from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from django.db import models
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


class StudentManager(BaseUserManager):

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


class Student(AbstractBaseUser):
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

    student_class = models.CharField(max_length=1, choices=STUDENT_CLASSES, blank=True, null=True)
    student_grade = models.PositiveSmallIntegerField(blank=True, null=True)
    student_number = models.PositiveSmallIntegerField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)

    objects = StudentManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['github']

    def get_full_name(self):
        # The user is identified by their email address
        return "{} {}".format(self.firstname, self.lastname)

    def get_short_name(self):
        # The user is identified by their email address
        return self.email

    def __str__(self):              # __unicode__ on Python 2
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


@receiver(post_save, sender=Student, dispatch_uid="update_github_id")
def update_github_id(sender, instance, **kwargs):
    if instance.github:
        pass

    gh = login(token=GENADY_TOKEN)
    gh_id = gh.user(instance.github).id

    Student.objects.filter(pk=instance.pk).update(github_id=gh_id)
