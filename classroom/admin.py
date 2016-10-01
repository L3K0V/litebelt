from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from classroom.models import GithubUser, Student
from classroom.models import Assignment, AssignmentTask, AssignmentSubmission, AssignmentTestCase
from classroom.forms import GithubUserCreationForm, GithubUserChangeForm


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
    list_display = ('name', 'assignment_index', 'start', 'end', 'code')
    readonly_fields = ('code',)


@admin.register(AssignmentTask)
class AssignmentTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'assignment', 'number', 'points')
    list_filter = ('assignment',)


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('author', 'assignment', 'pull_request',)
    list_filter = ('author', 'assignment')
    readonly_fields = ('date_created', 'date_modified',)
    search_fields = ('author', 'assignment')


@admin.register(AssignmentTestCase)
class AssignmentTestCaseAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'tasks')
    list_filter = ('tasks',)

admin.site.unregister(Group)
