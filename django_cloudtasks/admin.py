from django.contrib import admin
from .models import CloudChain, CloudTask
from django_cloudtasks.utils import revoke_task, revoke_chain
from django.contrib import messages

class CloudTaskInline(admin.TabularInline):
    model = CloudTask
    fk_name = 'chain'
    extra = 0
    fields = ('id', 'endpoint_path', 'status', 'delay_seconds', 'is_group', 'parent', 'next_task', 'created_at', 'updated_at')
    readonly_fields = ('id', 'created_at', 'updated_at')

    def has_add_permission(self, request, obj=None):
        return False

class CloudChainAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'parent_chain_link', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at', 'updated_at')
    readonly_fields = ('id', 'created_at', 'updated_at', 'result', 'parent_chain')
    inlines = [CloudTaskInline]
    actions = ['admin_revoke_chains']

    def parent_chain_link(self, obj):
        return obj.parent_chain.id if obj.parent_chain else None
    parent_chain_link.short_description = 'Parent Chain'

    @admin.action(description='Revoke selected chains')
    def admin_revoke_chains(self, request, queryset):
        revoked = 0
        for chain in queryset:
            success = revoke_chain(chain.id)
            if success:
                revoked += 1
        messages.info(request, f"Revoked {revoked} chain(s).")

class CloudTaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'endpoint_path', 'status', 'chain_link', 'is_group', 'delay_seconds', 'created_at')
    list_filter = ('status', 'is_group', 'created_at')
    search_fields = ('id', 'endpoint_path', 'external_task_name')
    readonly_fields = ('id', 'chain', 'parent', 'next_task', 'created_at', 'updated_at', 'execution_result', 'payload', 'external_task_name')
    actions = ['admin_revoke_tasks']

    def chain_link(self, obj):
        return obj.chain.id
    chain_link.short_description = 'Chain'

    @admin.action(description='Revoke selected tasks')
    def admin_revoke_tasks(self, request, queryset):
        revoked = 0
        for task in queryset:
            success = revoke_task(task.id)
            if success:
                revoked += 1
        messages.info(request, f"Revoked {revoked} task(s).")

admin.site.register(CloudChain, CloudChainAdmin)
admin.site.register(CloudTask, CloudTaskAdmin)