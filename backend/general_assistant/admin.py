from django.contrib import admin
from django.utils.html import format_html
from .models import Document
import os
from django.conf import settings

class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "file_name", "author", "created_at", "file_link", "delete_file_action")
    search_fields = ("file_name", "content")
    actions = ["delete_selected_files"]

    def file_name(self, obj):
        return obj.file.name.split("/")[-1] if obj.file else "無檔案"
    file_name.short_description = "檔案名稱"

    def file_link(self, obj):
        if obj.file:
            return format_html(f'<a href="{obj.file.url}" target="_blank">📄 下載檔案</a>')
        return "無檔案"
    file_link.short_description = "檔案下載"

    def delete_file_action(self, obj):
        return format_html(f'<a href="/admin/delete_file/{obj.id}/" style="color:red;">❌ 刪除檔案</a>')
    delete_file_action.short_description = "刪除操作"

    def delete_selected_files(self, request, queryset):
        """批量刪除選中的文件"""
        for obj in queryset:
            if obj.file:
                file_path = os.path.join(settings.MEDIA_ROOT, obj.file.name)
                if os.path.exists(file_path):
                    os.remove(file_path)
            obj.delete()
        self.message_user(request, "成功刪除選定的文件及其記錄")
    delete_selected_files.short_description = "刪除選定的文件及記錄"

admin.site.register(Document, DocumentAdmin)