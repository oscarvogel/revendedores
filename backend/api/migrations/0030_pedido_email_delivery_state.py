from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('api', '0029_pedido_idempotency_key')]
    operations = [
        migrations.AddField(model_name='pedido', name='email_cliente_estado', field=models.CharField(default='PENDIENTE', max_length=12)),
        migrations.AddField(model_name='pedido', name='email_cliente_intentos', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='pedido', name='email_cliente_enviado_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='pedido', name='email_cliente_ultimo_error', field=models.TextField(blank=True, default='')),
        migrations.AddField(model_name='pedido', name='email_ventas_estado', field=models.CharField(default='PENDIENTE', max_length=12)),
        migrations.AddField(model_name='pedido', name='email_ventas_intentos', field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name='pedido', name='email_ventas_enviado_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='pedido', name='email_ventas_ultimo_error', field=models.TextField(blank=True, default='')),
    ]
