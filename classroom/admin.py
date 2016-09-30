from django.contrib import admin

from classroom.models import Assignment, AssignmentSubmission, AssignmentTestCase


class AssignmentsAdmin(admin.ModelAdmin):
    list_display = ('name', 'assignment_type', 'target', 'start', 'end', 'code')
    readonly_fields = ('code',)


class AssignmentSubmissionAdmin(admin.ModelAdmin):
    pass


class AssignmentTestCaseAdmin(admin.ModelAdmin):
    pass

admin.site.register(Assignment, AssignmentsAdmin)
admin.site.register(AssignmentSubmission, AssignmentSubmissionAdmin)
admin.site.register(AssignmentTestCase, AssignmentTestCaseAdmin)
