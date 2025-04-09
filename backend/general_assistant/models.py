from django.db import models
from django.contrib.auth.models import User

class Document(models.Model):
    id = models.AutoField(primary_key=True)
    file = models.FileField(upload_to="documents/", blank=True, null=True)  # 允許上傳文件
    content = models.TextField(blank=True, null=True)  # 存放第一個chunk供使用者預覽
    chunk = models.IntegerField(blank=True, null=True)  # 切割後的chunk數量
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    def __str__(self):
        return self.file.name if self.file else "未命名文件"