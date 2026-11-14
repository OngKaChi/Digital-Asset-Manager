# assets/admin.py
from django.contrib import admin
from auditlog.admin import LogEntryAdmin
from auditlog.models import LogEntry
from .models import (
    Folder,
    Asset,
    Version,
    Tag,
    AssetTag,
    MetadataField,
    AssetMetadata,
)

admin.site.unregister(LogEntry)

@admin.register(LogEntry)
class AdminLogEntryAdmin(LogEntryAdmin):
    def has_module_permission(self, request):
        # Allow access to the audit log for superadmin and admin users
        return request.user.is_admin
    def has_view_permission(self, request, obj=None):
        # Allow view permission for superadmin and admin users
        return request.user.is_admin
    def has_add_permission(self, request):
        # Allow add permission for superadmin and admin users
        return request.user.is_admin
    def has_change_permission(self, request, obj=None):
        # Allow change permission for superadmin and admin users
        return request.user.is_admin
    def has_delete_permission(self, request, obj=None):
        # Allow delete permission for superadmin and admin users
        return request.user.is_admin

@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ("folder_id", "name", "parent_folder", "created_by", "created_at")
    search_fields = ("name",)
    list_filter = ("created_by",)


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("asset_id", "name", "asset_type", "folder", "uploaded_by", "uploaded_at", "size_bytes")
    search_fields = ("name", "file_path")
    list_filter = ("asset_type", "uploaded_by")


@admin.register(Version)
class VersionAdmin(admin.ModelAdmin):
    list_display = ("version_id", "asset", "version_number", "uploaded_by", "uploaded_at")
    search_fields = ("asset__name",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("tag_id", "name")
    search_fields = ("name",)


@admin.register(AssetTag)
class AssetTagAdmin(admin.ModelAdmin):
    list_display = ("asset", "tag")


@admin.register(MetadataField)
class MetadataFieldAdmin(admin.ModelAdmin):
    list_display = ("field_id", "name", "data_type", "created_by")
    search_fields = ("name",)
    list_filter = ("data_type",)


@admin.register(AssetMetadata)
class AssetMetadataAdmin(admin.ModelAdmin):
    list_display = ("asset", "field", "value")
    search_fields = ("asset__name", "field__name")
