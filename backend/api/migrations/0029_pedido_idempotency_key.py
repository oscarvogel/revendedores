from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('api', '0028_alter_pedidoitem_cantidad_decimal')]

    operations = [
        migrations.AddField(
            model_name='pedido',
            name='idempotency_key',
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
    ]
