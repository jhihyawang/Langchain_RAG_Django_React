# Generated by Django 5.1.7 on 2025-04-09 13:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "enterprise_assistant",
            "0002_remove_knowledge_title_alter_knowledge_department_and_more",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="knowledge",
            name="chunk",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
