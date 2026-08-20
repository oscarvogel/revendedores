from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0027_pedido_condicion_pago_cliente_snapshot'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pedidoitem',
            name='cantidad',
            field=models.DecimalField(decimal_places=3, default=1, max_digits=12),
        ),
    ]
