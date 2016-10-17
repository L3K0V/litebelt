from django.contrib import admin
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from classroom.models import GithubUser, Student
from classroom.models import Assignment, AssignmentTask, AssignmentSubmission, AssignmentTestCase
from classroom.forms import GithubUserCreationForm, GithubUserChangeForm

from classroom.tasks import review_submission

from github3 import login

GENADY_TOKEN = getattr(settings, 'GENADY_TOKEN', None)


@admin.register(GithubUser)
class GithubUserAdmin(BaseUserAdmin):
    # The forms to add and change user instances
    form = GithubUserChangeForm
    add_form = GithubUserCreationForm
    model = GithubUser

    # The fields to be used in displaying the User model.
    # These override the definitions on the base UserAdmin
    # that reference specific fields on auth.User.
    list_display = ('email', 'github', 'is_admin')
    list_filter = ('is_admin',)
    fieldsets = (
        (None, {'fields': ('email', 'password', 'firstname', 'lastname')}),
        ('GitHub information', {'fields': ('github', 'github_id', 'github_token')}),
        ('Permissions', {'fields': ('is_admin', 'is_active')}),

    )
    readonly_fields = ('github_id', 'github_token')

    # add_fieldsets is not a standard ModelAdmin attribute. UserAdmin
    # overrides get_fieldsets to use this attribute when creating a user.
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'github', 'password1', 'password2')}
        ),
    )
    search_fields = ('email', 'github')
    ordering = ('email',)
    filter_horizontal = ()
    actions = ['refresh_github_id', ]

    def refresh_github_id(self, request, queryset):
        gh = login(token=GENADY_TOKEN)

        # Failed logging on github
        if not gh:
            return

        for user in queryset:
            gh_id = gh.user(user.github).id
            GithubUser.objects.filter(pk=user.pk).update(github_id=gh_id)
    refresh_github_id.short_description = "Refresh GitHub ID of selected users"


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('user', 'student_grade', 'student_class', 'student_number')
    list_filter = ('student_class',)
    fieldsets = (
        ('Github profile', {'fields': ('user',)}),
        (None, {'fields': ('student_grade', 'student_class', 'student_number')}),
    )
    ordering = ('student_class',)


@admin.register(Assignment)
class AssignmentsAdmin(admin.ModelAdmin):
    list_display = ('name', 'number', 'start', 'end', 'get_current_score_ratio')


@admin.register(AssignmentTask)
class AssignmentTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'assignment', 'number', 'points')
    list_filter = ('assignment',)


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('author', 'pull_request', 'merged')
    list_filter = ('author', 'merged')
    actions = ['force_grade', 'force_grade_and_merge']

    def force_grade(self, request, queryset):
        for submission in queryset:
            review_submission.delay(submission_pk=submission.pk, force_merge=False)
    force_grade.short_description = "Force grading of selected submissions"

    def force_grade_and_merge(self, request, queryset):
        for submission in queryset.filter(merged=False):
            review_submission.delay(submission_pk=submission.pk, force_merge=True)
    force_grade.short_description = "Force grading and merge of selected submissions"


@admin.register(AssignmentTestCase)
class AssignmentTestCaseAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'tasks')
    list_filter = ('tasks',)

admin.site.unregister(Group)
