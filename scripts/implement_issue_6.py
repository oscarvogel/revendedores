from pathlib import Path


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'No se encontró bloque para {label}')
    return text.replace(old, new, 1)


# Pedido notification state.
path = Path('backend/api/models.py')
text = path.read_text(encoding='utf-8')
needle = "    idempotency_key = models.CharField(max_length=64, null=True, blank=True, unique=True)\n"
fields = """    email_cliente_estado = models.CharField(max_length=12, default='PENDIENTE')
    email_cliente_intentos = models.PositiveIntegerField(default=0)
    email_cliente_enviado_at = models.DateTimeField(null=True, blank=True)
    email_cliente_ultimo_error = models.TextField(blank=True, default='')
    email_ventas_estado = models.CharField(max_length=12, default='PENDIENTE')
    email_ventas_intentos = models.PositiveIntegerField(default=0)
    email_ventas_enviado_at = models.DateTimeField(null=True, blank=True)
    email_ventas_ultimo_error = models.TextField(blank=True, default='')
"""
if 'email_cliente_estado = models.CharField' not in text:
    text = replace_once(text, needle, needle + fields, 'estado email Pedido')
path.write_text(text, encoding='utf-8')

# Serializer surfaces notification observability.
path = Path('backend/api/serializers.py')
text = path.read_text(encoding='utf-8')
old = "'idempotency_key', 'items']"
new = "'idempotency_key', 'email_cliente_estado', 'email_cliente_intentos', 'email_cliente_enviado_at', 'email_cliente_ultimo_error', 'email_ventas_estado', 'email_ventas_intentos', 'email_ventas_enviado_at', 'email_ventas_ultimo_error', 'items']"
if "'email_cliente_estado'" not in text:
    text = replace_once(text, old, new, 'campos email serializer')
    old_ro = "'cliente_snapshot', 'idempotency_key')"
    new_ro = "'cliente_snapshot', 'idempotency_key', 'email_cliente_estado', 'email_cliente_intentos', 'email_cliente_enviado_at', 'email_cliente_ultimo_error', 'email_ventas_estado', 'email_ventas_intentos', 'email_ventas_enviado_at', 'email_ventas_ultimo_error')"
    text = replace_once(text, old_ro, new_ro, 'readonly email serializer')
path.write_text(text, encoding='utf-8')

# Persistent delivery service.
Path('backend/api/services/notificaciones_pedido.py').write_text("""import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from api.models import Pedido

logger = logging.getLogger('api')


def _registrar_intento(pedido, destino):
    campo_intentos = f'email_{destino}_intentos'
    setattr(pedido, campo_intentos, getattr(pedido, campo_intentos) + 1)
    setattr(pedido, f'email_{destino}_estado', 'PENDIENTE')
    setattr(pedido, f'email_{destino}_ultimo_error', '')
    pedido.save(update_fields=[campo_intentos, f'email_{destino}_estado', f'email_{destino}_ultimo_error'])


def _registrar_exito(pedido, destino):
    setattr(pedido, f'email_{destino}_estado', 'ENVIADO')
    setattr(pedido, f'email_{destino}_enviado_at', timezone.now())
    setattr(pedido, f'email_{destino}_ultimo_error', '')
    pedido.save(update_fields=[f'email_{destino}_estado', f'email_{destino}_enviado_at', f'email_{destino}_ultimo_error'])


def _registrar_error(pedido, destino, exc):
    setattr(pedido, f'email_{destino}_estado', 'FALLIDO')
    setattr(pedido, f'email_{destino}_ultimo_error', str(exc)[:2000])
    pedido.save(update_fields=[f'email_{destino}_estado', f'email_{destino}_ultimo_error'])
    logger.exception('Error enviando email %s para pedido %s', destino, pedido.id)


def enviar_notificaciones_pedido(pedido_id, destinos=('cliente', 'ventas')):
    pedido = Pedido.objects.select_related('user').get(pk=pedido_id)
    snapshot = pedido.cliente_snapshot or {}
    numero_cliente = snapshot.get('numero_cliente') or ''
    nombre_cliente = snapshot.get('nombre') or pedido.user.username
    resultados = {}

    for destino in destinos:
        _registrar_intento(pedido, destino)
        try:
            if destino == 'cliente':
                destinatario = snapshot.get('email') or pedido.user.email
                if not destinatario:
                    raise ValueError('El cliente no tiene email configurado.')
                subject = f'Confirmación de tu Pedido #{pedido.id}'
                html = render_to_string('emails/confirmacion_pedido_cliente.html', {'pedido': pedido})
                plain = f'Tu pedido #{pedido.id} fue recibido. Total estimado: ${pedido.total}'
            elif destino == 'ventas':
                destinatario = settings.EMAIL_RECIPIENT
                if not destinatario:
                    raise ValueError('EMAIL_RECIPIENT no está configurado.')
                subject = f'[FASA] Nuevo pedido #{pedido.id} — Cliente {numero_cliente} — {nombre_cliente}'
                html = render_to_string('emails/notificacion_pedido_vendedor.html', {'pedido': pedido})
                plain = f'Nuevo pedido #{pedido.id} de {nombre_cliente}. Total estimado: ${pedido.total}'
            else:
                raise ValueError(f'Destino de notificación desconocido: {destino}')

            send_mail(
                subject,
                plain,
                settings.DEFAULT_FROM_EMAIL,
                [destinatario],
                html_message=html,
                fail_silently=False,
            )
            _registrar_exito(pedido, destino)
            resultados[destino] = {'estado': 'ENVIADO', 'error': ''}
        except Exception as exc:
            _registrar_error(pedido, destino, exc)
            resultados[destino] = {'estado': 'FALLIDO', 'error': str(exc)}

    return resultados
""", encoding='utf-8')

# Views: remove daemon dependency and invoke persistent delivery after commit.
path = Path('backend/api/views.py')
text = path.read_text(encoding='utf-8')
start = text.index('def enviar_emails_pedido_async(pedido_id):')
end = text.index('\n\n\n\nclass PedidoViewSet', start)
compat = """def enviar_emails_pedido_async(pedido_id):
    # Compatibilidad temporal para llamadas externas: ya no crea threads.
    from .services.notificaciones_pedido import enviar_notificaciones_pedido
    return enviar_notificaciones_pedido(pedido_id)


def enviar_emails_pedido(pedido):
    from .services.notificaciones_pedido import enviar_notificaciones_pedido
    resultado = enviar_notificaciones_pedido(pedido.id)
    return all(item['estado'] == 'ENVIADO' for item in resultado.values())
"""
text = text[:start] + compat + text[end:]
old_callback = """                pedido_id = pedido.id
                transaction.on_commit(
                    lambda: threading.Thread(
                        target=enviar_emails_pedido_async,
                        args=(pedido_id,),
                        daemon=True,
                    ).start()
                )
"""
if old_callback in text:
    text = text.replace(old_callback, '', 1)
old_return = """        data = self.get_serializer(pedido).data
        data['idempotent_replay'] = False
        return Response(data, status=status.HTTP_201_CREATED)
"""
new_return = """        from .services.notificaciones_pedido import enviar_notificaciones_pedido
        notificaciones = enviar_notificaciones_pedido(pedido.id)
        pedido.refresh_from_db()
        data = self.get_serializer(pedido).data
        data['idempotent_replay'] = False
        data['notificaciones'] = notificaciones
        return Response(data, status=status.HTTP_201_CREATED)
"""
text = replace_once(text, old_return, new_return, 'respuesta checkout con notificaciones')
path.write_text(text, encoding='utf-8')

# Staff retry becomes synchronous, observable, target-selectable.
path = Path('backend/api/staff_views.py')
text = path.read_text(encoding='utf-8')
start = text.index("@api_view(['POST'])\n@permission_classes([IsAdminUser])\ndef reenviar_email_pedido")
end = text.index("\n\n@api_view(['GET'])\n@permission_classes([IsAdminUser])\ndef resumen_pedidos_staff", start)
new_func = """@api_view(['POST'])
@permission_classes([IsAdminUser])
def reenviar_email_pedido(request, pedido_id):
    try:
        Pedido.objects.get(pk=pedido_id)
    except Pedido.DoesNotExist:
        return Response({'error': 'Pedido no encontrado'}, status=404)

    destino = request.data.get('destino')
    destinos = (destino,) if destino in {'cliente', 'ventas'} else ('cliente', 'ventas')
    from .services.notificaciones_pedido import enviar_notificaciones_pedido
    resultados = enviar_notificaciones_pedido(pedido_id, destinos=destinos)
    success = all(item['estado'] == 'ENVIADO' for item in resultados.values())
    return Response({
        'success': success,
        'pedido_id': pedido_id,
        'resultados': resultados,
        'message': 'Notificación procesada; revise el estado por destinatario.',
    }, status=200)
"""
text = text[:start] + new_func + text[end:]
path.write_text(text, encoding='utf-8')

# Email timeout.
path = Path('backend/backend/settings.py')
text = path.read_text(encoding='utf-8')
needle = "EMAIL_RECIPIENT = config('EMAIL_RECIPIENT', default='')\n"
if 'EMAIL_TIMEOUT =' not in text:
    text = replace_once(text, needle, needle + "EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=10, cast=int)\n", 'EMAIL_TIMEOUT')
path.write_text(text, encoding='utf-8')

# Migration.
Path('backend/api/migrations/0030_pedido_email_delivery_state.py').write_text("""from django.db import migrations, models


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
""", encoding='utf-8')

# Tests.
Path('backend/api/tests/test_pedido_notifications.py').write_text("""from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from api.models import Pedido
from api.services.notificaciones_pedido import enviar_notificaciones_pedido


@override_settings(DEFAULT_FROM_EMAIL='ventas@fasa.test', EMAIL_RECIPIENT='pedidos@fasa.test')
class PedidoNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='mail-test', email='cliente@fasa.test')
        self.pedido = Pedido.objects.create(
            user=self.user,
            estado='CONFIRMADO',
            cliente_snapshot={
                'numero_cliente': '00125',
                'nombre': 'CLIENTE PRUEBA',
                'email': 'cliente@fasa.test',
            },
        )

    @patch('api.services.notificaciones_pedido.send_mail', return_value=1)
    def test_envio_exitoso_registra_ambos_destinos(self, mocked):
        result = enviar_notificaciones_pedido(self.pedido.id)
        self.pedido.refresh_from_db()
        self.assertEqual(result['cliente']['estado'], 'ENVIADO')
        self.assertEqual(result['ventas']['estado'], 'ENVIADO')
        self.assertEqual(self.pedido.email_cliente_intentos, 1)
        self.assertEqual(self.pedido.email_ventas_intentos, 1)
        self.assertEqual(mocked.call_count, 2)
        asunto_ventas = mocked.call_args_list[1].args[0]
        self.assertIn('[FASA] Nuevo pedido #', asunto_ventas)
        self.assertIn('Cliente 00125', asunto_ventas)

    @patch('api.services.notificaciones_pedido.send_mail', side_effect=RuntimeError('SMTP fuera de servicio'))
    def test_fallo_queda_persistido(self, _mocked):
        result = enviar_notificaciones_pedido(self.pedido.id, destinos=('cliente',))
        self.pedido.refresh_from_db()
        self.assertEqual(result['cliente']['estado'], 'FALLIDO')
        self.assertEqual(self.pedido.email_cliente_estado, 'FALLIDO')
        self.assertEqual(self.pedido.email_cliente_intentos, 1)
        self.assertIn('SMTP fuera de servicio', self.pedido.email_cliente_ultimo_error)

    @patch('api.services.notificaciones_pedido.send_mail', return_value=1)
    def test_reintento_incrementa_intentos_y_recupera(self, _mocked):
        self.pedido.email_cliente_estado = 'FALLIDO'
        self.pedido.email_cliente_intentos = 1
        self.pedido.email_cliente_ultimo_error = 'error anterior'
        self.pedido.save()
        enviar_notificaciones_pedido(self.pedido.id, destinos=('cliente',))
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.email_cliente_estado, 'ENVIADO')
        self.assertEqual(self.pedido.email_cliente_intentos, 2)
        self.assertEqual(self.pedido.email_cliente_ultimo_error, '')
""", encoding='utf-8')
