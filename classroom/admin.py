from django.contrib import admin

from classroom.models import Course, CourseAssignment, AssignmentSubmission, AssignmentTestCase


class CourseAdmin(admin.ModelAdmin):
    pass


class CourseAssignmentsAdmin(admin.ModelAdmin):
    list_display = ('name', 'assignment_type', 'target', 'start', 'end', 'code')
    readonly_fields = ('code',)


class AssignmentSubmissionAdmin(admin.ModelAdmin):
    pass


class AssignmentTestCaseAdmin(admin.ModelAdmin):
    pass

admin.site.register(Course, CourseAdmin)
admin.site.register(CourseAssignment, CourseAssignmentsAdmin)
admin.site.register(AssignmentSubmission, AssignmentSubmissionAdmin)
admin.site.register(AssignmentTestCase, AssignmentTestCaseAdmin)
