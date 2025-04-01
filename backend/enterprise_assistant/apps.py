from django.apps import AppConfig

class EnterpriseAssistantConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "enterprise_assistant"

    def ready(self):
        import enterprise_assistant.admin  # ✅ 確保 admin.py 被載入