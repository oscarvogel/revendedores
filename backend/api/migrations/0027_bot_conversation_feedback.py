import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0026_bot_conversation_log"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BotConversation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_id", models.CharField(db_index=True, max_length=80, unique=True)),
                (
                    "origen",
                    models.CharField(
                        choices=[("chat_local", "Chat local"), ("whatsapp", "WhatsApp"), ("api", "API")],
                        db_index=True,
                        max_length=30,
                    ),
                ),
                ("telefono", models.CharField(blank=True, db_index=True, max_length=30, null=True)),
                ("started_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("last_message_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("message_count", models.PositiveIntegerField(default=0)),
                (
                    "feedback_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pendiente"),
                            ("useful", "Sirvio"),
                            ("not_useful", "No sirvio"),
                            ("dangerous", "Respuesta peligrosa"),
                            ("wrong_product", "Producto mal entendido"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=30,
                    ),
                ),
                ("feedback_comment", models.TextField(blank=True)),
                (
                    "reviewed_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="bot_conversation_reviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="bot_conversations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Conversacion Bot",
                "verbose_name_plural": "Conversaciones Bot",
                "ordering": ["-last_message_at"],
                "indexes": [
                    models.Index(fields=["origen", "last_message_at"], name="api_botconv_origen_0d9062_idx"),
                    models.Index(fields=["feedback_status", "last_message_at"], name="api_botconv_feedbac_5bbebf_idx"),
                ],
            },
        ),
        migrations.AddField(
            model_name="botconversationlog",
            name="conversation",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="logs",
                to="api.botconversation",
            ),
        ),
    ]
