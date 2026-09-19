from django.contrib import admin


class SoftDeleteAdminMixin:

    actions = ['restore_selected']

    def get_queryset(self, request):
        return self.model.all_objects.all()

    @admin.display(boolean=True, description='Deleted')
    def is_deleted(self, obj):
        return obj.is_deleted

    @admin.action(description='Restore selected')
    def restore_selected(self, request, queryset):
        for obj in queryset:
            obj.restore()