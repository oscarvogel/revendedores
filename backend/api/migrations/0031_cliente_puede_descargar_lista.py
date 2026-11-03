from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('api', '0030_pedido_email_delivery_state')]
    operations = [
        migrations.AddField(
            model_name='cliente', name='puede_descargar_lista',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='cliente', name='puede_descargar_lista',
            field=models.BooleanField(default=False),
        ),
    ]
