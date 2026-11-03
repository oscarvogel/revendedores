from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0027_bot_conversation_feedback"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="botconversation",
            new_name="api_botconv_origen_1da4e4_idx",
            old_name="api_botconv_origen_0d9062_idx",
        ),
        migrations.RenameIndex(
            model_name="botconversation",
            new_name="api_botconv_feedbac_970783_idx",
            old_name="api_botconv_feedbac_5bbebf_idx",
        ),
    ]
