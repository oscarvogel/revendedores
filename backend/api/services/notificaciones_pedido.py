"""Envío de notificaciones de pedidos con estado persistente por destinatario."""

import logging

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
