from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_phone_and_invite"),
    ]

    operations = [
        migrations.CreateModel(
            name="Profile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("patronymic", models.CharField(blank=True, default="", max_length=150, verbose_name="Отчество")),
                ("last_name_lat", models.CharField(blank=True, default="", max_length=150, verbose_name="Фамилия латиницей")),
                ("first_name_lat", models.CharField(blank=True, default="", max_length=150, verbose_name="Имя латиницей")),
                ("patronymic_lat", models.CharField(blank=True, default="", max_length=150, verbose_name="Отчество латиницей")),
                ("gender", models.CharField(blank=True, choices=[("male", "Мужской"), ("female", "Женский"), ("other", "Другое")], default="", max_length=20, verbose_name="Пол")),
                ("citizenship", models.CharField(blank=True, choices=[("RU", "РФ"), ("OTHER", "Другое")], default="RU", max_length=20, verbose_name="Гражданство")),
                ("telegram", models.CharField(blank=True, default="", max_length=150, verbose_name="Телеграм")),
                ("qualification", models.CharField(blank=True, default="", max_length=255, verbose_name="Квалификация, навыки")),
                ("travel_ready", models.CharField(blank=True, choices=[("yes", "Да"), ("no", "Нет"), ("limited", "Ограниченно")], default="", max_length=20, verbose_name="Готовность к командировкам")),
                ("quarantine_ready", models.CharField(blank=True, choices=[("yes", "Да"), ("no", "Нет"), ("limited", "Ограниченно")], default="", max_length=20, verbose_name="Готовность к карантину")),
                ("restrictions_companies", models.CharField(blank=True, default="Нет", max_length=255, verbose_name="Ограничения по работе с компаниями")),
                ("restrictions_topics", models.CharField(blank=True, default="Нет", max_length=255, verbose_name="Ограничения на участие в проектах с определённой тематикой")),
                ("restrictions_schedule", models.CharField(blank=True, default="Нет", max_length=255, verbose_name="Ограничения по графику работы")),
                ("fso_status", models.CharField(blank=True, choices=[("yes", "Да"), ("no", "Нет"), ("in_progress", "В процессе"), ("na", "Не требуется/не знаю")], default="", max_length=30, verbose_name="Прохождение ФСО")),
                ("own_equipment", models.CharField(blank=True, default="Нет", max_length=255, verbose_name="Наличие собственного оборудования")),
                ("education", models.CharField(blank=True, choices=[("higher_full", "Высшее-полное"), ("higher", "Высшее"), ("secondary", "Среднее"), ("other", "Другое")], default="", max_length=30, verbose_name="Образование")),
                ("additional_skills", models.TextField(blank=True, default="", verbose_name="Дополнительные навыки")),
                ("resume", models.FileField(blank=True, null=True, upload_to="staff/resumes/", verbose_name="Резюме")),
                ("photo", models.ImageField(blank=True, null=True, upload_to="staff/photos/", verbose_name="Фото")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="profile", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]