from django.contrib import admin

from classroom.models import Assignment, AssignmentSubmission, AssignmentTestCase


class AssignmentsAdmin(admin.ModelAdmin):
    list_display = ('name', 'assignment_type', 'target', 'start', 'end', 'code')
    list_filter = ('assignment_type', 'target')
    readonly_fields = ('code',)


class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('author', 'assignment', 'pull_request', 'grade')
    list_filter = ('author', 'assignment')
    readonly_fields = ('date_created', 'date_modified',)
    search_fields = ('author', 'assignment')


class AssignmentTestCaseAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'assignment', 'task',)

admin.site.register(Assignment, AssignmentsAdmin)
admin.site.register(AssignmentSubmission, AssignmentSubmissionAdmin)
admin.site.register(AssignmentTestCase, AssignmentTestCaseAdmin)
