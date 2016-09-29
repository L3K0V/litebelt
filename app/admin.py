
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from app.models import GithubUser
from app.forms import GithubUserCreationForm, GithubUserChangeForm


class GithubUserAdmin(BaseUserAdmin):
    # The forms to add and change user instances
    form = GithubUserChangeForm
    add_form = GithubUserCreationForm
    model = GithubUser

    # The fields to be used in displaying the User model.
    # These override the definitions on the base UserAdmin
    # that reference specific fields on auth.User.
    list_display = ('email', 'github', 'is_admin', 'student_grade', 'student_class', 'student_number')
    list_filter = ('is_admin', 'student_class')
    fieldsets = (
        (None, {'fields': ('email', 'password', 'firstname', 'lastname')}),
        ('GitHub information', {'fields': ('github', 'github_id', 'github_token')}),
        ('Student information', {'fields': ('student_grade', 'student_class', 'student_number')}),
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
    ordering = ('email', 'student_class')
    filter_horizontal = ()

admin.site.register(GithubUser, GithubUserAdmin)
admin.site.unregister(Group)
