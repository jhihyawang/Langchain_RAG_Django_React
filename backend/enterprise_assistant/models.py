from django.contrib.auth.models import User
from django.db import models


class Knowledge(models.Model):
    id = models.AutoField(primary_key=True)
    file = models.FileField(upload_to="knowledge_files/", blank=True, null=True)  # 允許上傳文件
    title = models.CharField(max_length=255, null=False, blank=False, default="未分類")
    department = models.CharField(max_length=255, null=False, blank=False, default="未分類")
    content = models.TextField(blank=True, null=True)  # 存放第一個chunk供使用者預覽
    chunk = models.IntegerField(blank=True, null=True)  # 切割後的chunk數量
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.file.name if self.file else "未命名文件"

class AdminUser(models.Model):
    """ 知識庫管理員 """
    user = models.OneToOneField(User, on_delete=models.CASCADE)  
    department = models.CharField(max_length=100, blank=True, null=True)  
    is_superadmin = models.BooleanField(default=False)  # 是否為超級管理員

    def __str__(self):
        return f"{self.user.username} - {'超級管理員' if self.is_superadmin else '部門管理員'}"