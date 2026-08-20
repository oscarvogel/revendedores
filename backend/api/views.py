import threading
import secrets
import string
from django.db import models, transaction, IntegrityError
from django.contrib.auth import logout
from django.db.models import Case, When, BooleanField

from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.shortcuts import redirect
from django.http import HttpResponse, HttpResponseBadRequest
from django.core import signing
from django.urls import reverse
from urllib.parse import quote
from datetime import timedelta
from rest_framework.permissions import IsAuthenticated
from rest_framework import filters

from .models import Articulos, Cliente, FormaPago, Favorito, Busqueda, Pedido, RegistroSesion, BonificacionCliente, ConsultaPrecio, ArticuloVista, LinkOpen, ShortTrackingLink
from .serializers import ArticuloSerializer, FormaPagoSerializer, FavoritoSerializer, BusquedaSerializer, PedidoSerializer
from .services.precios import calcular_precio_articulo
from backend.BaseViewSet import BaseAppModelViewSet
from rest_framework import viewsets
from rest_framework.decorators import action

from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
import logging

logger = logging.getLogger('api')


def _build_short_code(length=8):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def enviar_emails_pedido_async(pedido_id):
    """Envía los correos de confirmación de pedido de forma asíncrona."""
    try:
        # Importar aquí para evitar problemas de sincronización con la DB
        from .models import Pedido
        pedido = Pedido.objects.get(id=pedido_id)
        
        print(f"📧 [THREAD] Iniciando envío de correos para pedido {pedido.id}")
        
        # Email para el cliente
        print(f"📬 [THREAD] Enviando correo al cliente: {pedido.user.email}")
        subject_cliente = f"Confirmación de tu Pedido #{pedido.id}"
        html_message_cliente = render_to_string('emails/confirmacion_pedido_cliente.html', {'pedido': pedido})
        plain_message_cliente = f"Tu pedido #{pedido.id} ha sido confirmado. Total: ${pedido.total}"
        send_mail(
            subject_cliente,
            plain_message_cliente,
            settings.DEFAULT_FROM_EMAIL,
            [pedido.user.email],
            html_message=html_message_cliente,
            fail_silently=False,
        )
        print(f"✅ [THREAD] Correo al cliente enviado")

        # Email para el vendedor
        print(f"📬 [THREAD] Enviando correo al vendedor: {settings.EMAIL_RECIPIENT}")
        subject_vendedor = f"Nuevo Pedido Recibido #{pedido.id} de {pedido.user.username}"
        html_message_vendedor = render_to_string('emails/notificacion_pedido_vendedor.html', {'pedido': pedido})
        plain_message_vendedor = f"Se ha recibido un nuevo pedido de {pedido.user.username}. Total: ${pedido.total}"
        send_mail(
            subject_vendedor,
            plain_message_vendedor,
            settings.DEFAULT_FROM_EMAIL,
            [settings.EMAIL_RECIPIENT],
            html_message=html_message_vendedor,
            fail_silently=False,
        )
        print(f"✅ [THREAD] Correo al vendedor enviado")
        print(f"🎉 [THREAD] Todos los correos enviados exitosamente para pedido {pedido.id}")
        
    except Exception as e:
        print(f"❌ [THREAD] Error al enviar correos para pedido {pedido_id}: {e}")
        logger.exception("Error en thread de emails para pedido %s", pedido_id)


def enviar_emails_pedido(pedido):
    """Envía los correos de confirmación de pedido."""
    try:
        print(f"📧 Iniciando envío de correos para pedido {pedido.id}")
        
        # Email para el cliente
        print(f"📬 Enviando correo al cliente: {pedido.user.email}")
        subject_cliente = f"Confirmación de tu Pedido #{pedido.id}"
        html_message_cliente = render_to_string('emails/confirmacion_pedido_cliente.html', {'pedido': pedido})
        plain_message_cliente = f"Tu pedido #{pedido.id} ha sido confirmado. Total: ${pedido.total}"
        send_mail(
            subject_cliente,
            plain_message_cliente,
            settings.DEFAULT_FROM_EMAIL,
            [pedido.user.email],
            html_message=html_message_cliente,
            fail_silently=False,
        )
        print(f"✅ Correo al cliente enviado")

        # Email para el vendedor
        print(f"📬 Enviando correo al vendedor: {settings.EMAIL_RECIPIENT}")
        subject_vendedor = f"Nuevo Pedido Recibido #{pedido.id} de {pedido.user.username}"
        html_message_vendedor = render_to_string('emails/notificacion_pedido_vendedor.html', {'pedido': pedido})
        plain_message_vendedor = f"Se ha recibido un nuevo pedido de {pedido.user.username}. Total: ${pedido.total}"
        send_mail(
            subject_vendedor,
            plain_message_vendedor,
            settings.DEFAULT_FROM_EMAIL,
            [settings.EMAIL_RECIPIENT],
            html_message=html_message_vendedor,
            fail_silently=False,
        )
        print(f"✅ Correo al vendedor enviado")
        print(f"🎉 Todos los correos enviados exitosamente para pedido {pedido.id}")
        return True
    except Exception as e:
        print(f"❌ Error al enviar correos para pedido {pedido.id}: {e}")
        logger.exception("Error al enviar correos para pedido %s", pedido.id)
        return False




class PedidoViewSet(viewsets.ModelViewSet):
    serializer_class = PedidoSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        return Pedido.objects.filter(user=self.request.user).order_by('-fecha_creacion')

    def create(self, request, *args, **kwargs):
        return Response(
            {'error': 'Use el endpoint /api/pedidos/checkout/ para enviar pedidos.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        estado = request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(self.get_serializer(queryset, many=True).data)

    @action(detail=False, methods=['get'])
    def mis_pedidos_resumen(self, request):
        queryset = self.get_queryset()
        return Response({
            'total_pedidos': queryset.count(),
            'pedidos_pendientes': queryset.filter(estado='PENDIENTE').count(),
            'pedidos_confirmados': queryset.filter(estado='CONFIRMADO').count(),
            'pedidos_en_proceso': queryset.filter(estado='EN_PROCESO').count(),
            'pedidos_entregados': queryset.filter(estado='ENTREGADO').count(),
            'ultimos_pedidos': self.get_serializer(queryset[:5], many=True).data,
        })

    @action(detail=False, methods=['post'])
    def checkout(self, request):
        idempotency_key = (
            request.headers.get('Idempotency-Key')
            or request.data.get('idempotency_key')
            or ''
        ).strip()
        if not idempotency_key:
            return Response(
                {'error': 'Falta Idempotency-Key para procesar el pedido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(idempotency_key) > 64:
            return Response(
                {'error': 'Idempotency-Key supera el máximo de 64 caracteres.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing = Pedido.objects.filter(
            user=request.user,
            idempotency_key=idempotency_key,
        ).first()
        if existing:
            data = self.get_serializer(existing).data
            data['idempotent_replay'] = True
            return Response(data, status=status.HTTP_200_OK)

        payload = request.data.copy()
        payload.pop('idempotency_key', None)
        try:
            with transaction.atomic():
                serializer = self.get_serializer(data=payload)
                serializer.is_valid(raise_exception=True)
                pedido = serializer.save(
                    user=request.user,
                    idempotency_key=idempotency_key,
                    estado='CONFIRMADO',
                )
                pedido_id = pedido.id
                transaction.on_commit(
                    lambda: threading.Thread(
                        target=enviar_emails_pedido_async,
                        args=(pedido_id,),
                        daemon=True,
                    ).start()
                )
        except IntegrityError:
            existing = Pedido.objects.filter(
                user=request.user,
                idempotency_key=idempotency_key,
            ).first()
            if not existing:
                raise
            data = self.get_serializer(existing).data
            data['idempotent_replay'] = True
            return Response(data, status=status.HTTP_200_OK)

        data = self.get_serializer(pedido).data
        data['idempotent_replay'] = False
        return Response(data, status=status.HTTP_201_CREATED)


class BusquedaViewSet(viewsets.ModelViewSet):
    serializer_class = BusquedaSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        """Devuelve las búsquedas del usuario actual."""
        return Busqueda.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Asigna el usuario actual al crear una búsqueda."""
        serializer.save(user=self.request.user)


class FavoritoViewSet(viewsets.ModelViewSet):
    serializer_class = FavoritoSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'articulo' # Usar la clave del artículo para lookup
    lookup_value_regex = r'[\w.]+'  # Permitir puntos en la clave

    def get_queryset(self):
        """Solo devuelve los favoritos del usuario actual."""
        return Favorito.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Asigna el usuario actual al crear un favorito."""
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Permite eliminar un favorito por la clave del artículo."""
        try:
            # El lookup_field es 'articulo', así que kwargs['articulo'] tiene la clave.
            favorito = self.get_queryset().get(articulo__clave=kwargs.get('articulo'))
            favorito.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Favorito.DoesNotExist:
            return Response(
                {"error": "Favorito no encontrado."},
                status=status.HTTP_404_NOT_FOUND
            )

        
User = get_user_model()

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def user_logout(request):
    session_id = request.data.get('session_id')

    if session_id:
        # Intentar cerrar esa sesión específica
        try:
            sesion = RegistroSesion.objects.get(
                id=session_id,
                usuario=request.user,
                fin_sesion__isnull=True
            )
            sesion.fin_sesion = timezone.now()
            sesion.save()
        except RegistroSesion.DoesNotExist:
            pass  # No hacer nada si no existe o ya fue cerrada
    else:
        # Si no hay ID, cerrar la última sesión activa
        sesion = RegistroSesion.objects.filter(
            usuario=request.user,
            fin_sesion__isnull=True
        ).last()
        if sesion:
            sesion.fin_sesion = timezone.now()
            sesion.save()

    return Response({'message': 'Sesión finalizada correctamente.'}, status=200)
    
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    user = request.user
    data = request.data

    # Actualizar campos básicos
    user.first_name = data.get('first_name', user.first_name).strip()
    user.last_name = data.get('last_name', user.last_name).strip()
    user.email = data.get('email', user.email).strip()

    # Validar email
    if not user.email:
        return Response(
            {'error': 'El email es requerido.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Validar contraseña si se envía
    password = data.get('password')
    if password:
        try:
            validate_password(password, user)
        except ValidationError as e:
            return Response(
                {'error': ' '.join(e.messages)},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(password)  # Esto encripta la contraseña

    try:
        user.save()
    except Exception as e:
        return Response(
            {'error': 'Error al guardar el usuario: ' + str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Respuesta sin contraseña
    return Response({
        'message': 'Perfil actualizado con éxito.',
        'user': {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'is_staff': user.is_staff,
            'date_joined': user.date_joined,
        }
    }, status=status.HTTP_200_OK)        


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def track_articulos_view(request):
    """Registra cuando un usuario entra a ver ofertas o discontinuados."""
    tipo = request.data.get('tipo')
    if tipo not in ['oferta', 'discontinuado']:
        return Response({'error': 'Tipo no válido'}, status=status.HTTP_400_BAD_REQUEST)

    # Buscar cliente asociado si existe
    cliente = None
    try:
        cliente = request.user.cliente
    except Exception:
        cliente = None

    # IP y User-Agent
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    user_agent = request.META.get('HTTP_USER_AGENT', '')

    ArticuloVista.objects.create(
        usuario=request.user,
        cliente=cliente,
        tipo=tipo,
        ip_address=ip,
        user_agent=user_agent
    )

    return Response({'success': True})


@api_view(['GET'])
@permission_classes([AllowAny])
def track_redirect(request):
    """Recibe `?t=<token>`; registra la apertura y redirige al `url` del payload.

    Token: generado con `django.core.signing.dumps(payload)` donde payload debe incluir
    al menos: `url` (target), opcionalmente `email` y `campaign`.
    """
    token = request.GET.get('t')
    if not token:
        return HttpResponseBadRequest("missing token")
    try:
        payload = signing.loads(token, max_age=60 * 60 * 24 * 30)  # 30 días
    except Exception:
        return HttpResponseBadRequest("token inválido o expirado")

    # IP y user-agent
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    # Intentar varias fuentes para el header Referer/Origin (algunos clientes/middlewares difieren)
    referer = ''
    try:
        referer = (request.headers.get('Referer') or
                   request.META.get('HTTP_REFERER') or
                   request.META.get('HTTP_ORIGIN') or
                   request.META.get('ORIGIN') or
                   '')
    except Exception:
        referer = request.META.get('HTTP_REFERER', '') or request.META.get('HTTP_ORIGIN', '') or ''

    if not referer:
        # No bloquear; añadir trazas para debugging si hace falta
        logger.debug('track_redirect: no referer header (ip=%s, ua=%s, token=%s)', ip, (user_agent or '')[:200], (token or '')[:50])

    # Registrar, evitando duplicados: si ya existe un registro con el mismo
    # token + IP + user_agent en los últimos 10 segundos, no lo duplicamos.
    try:
        now = timezone.now()
        window = now - timedelta(seconds=10)
        # Dedupe por token en una ventana corta para ignorar prefetchs (WhatsApp, etc.)
        duplicate = LinkOpen.objects.filter(
            token=token,
            opened_at__gte=window
        ).exists()
        if duplicate:
            logger.info("Ignorado LinkOpen duplicado por token=%s", token)
        else:
            LinkOpen.objects.create(
                token=token,
                recipient_email=payload.get('email'),
                campaign=payload.get('campaign'),
                target_url=payload.get('url') or '',
                ip_address=ip,
                user_agent=user_agent,
                referer=referer,
            )
    except Exception:
        # No bloquear la redirección si falla el registro
        logger.exception("Error guardando LinkOpen")

    # Redirigir al destino final
    dest = payload.get('url')
    if not dest:
        return HttpResponseBadRequest("url objetivo no encontrada en token")
    return redirect(dest)


@api_view(['GET'])
@permission_classes([AllowAny])
def track_pixel(request):
    """Recibe `?t=<token>`, registra la apertura y devuelve un GIF 1x1 transparente."""
    transparent_gif = (
        b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
        b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01'
        b'\x00\x00\x02\x02D\x01\x00;'
    )
    token = request.GET.get('t')
    if not token:
        return HttpResponseBadRequest("missing token")
    try:
        payload = signing.loads(token, max_age=60 * 60 * 24 * 30)  # 30 dias
    except Exception:
        return HttpResponseBadRequest("token invalido o expirado")

    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    try:
        referer = (request.headers.get('Referer') or
                   request.META.get('HTTP_REFERER') or
                   request.META.get('HTTP_ORIGIN') or
                   request.META.get('ORIGIN') or
                   '')
    except Exception:
        referer = request.META.get('HTTP_REFERER', '') or request.META.get('HTTP_ORIGIN', '') or ''

    try:
        now = timezone.now()
        window = now - timedelta(seconds=10)
        duplicate = LinkOpen.objects.filter(
            token=token,
            opened_at__gte=window
        ).exists()
        if duplicate:
            logger.info("Ignorado LinkOpen duplicado por token=%s", token)
        else:
            LinkOpen.objects.create(
                token=token,
                recipient_email=payload.get('email'),
                campaign=payload.get('campaign'),
                target_url=payload.get('url') or '',
                ip_address=ip,
                user_agent=user_agent,
                referer=referer,
            )
    except Exception:
        logger.exception("Error guardando LinkOpen desde pixel")

    response = HttpResponse(transparent_gif, content_type='image/gif')
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@api_view(['POST'])
@permission_classes([AllowAny])
def track_token(request):
    """Genera y devuelve un token firmado para uso en `?t=`.

    Espera JSON con al menos `url` y opcionalmente `email` y `campaign`.
    Respuesta: {"token": "<TOKEN>"}
    """
    data = request.data
    url = data.get('url')
    if not url:
        return Response({'error': 'url is required'}, status=status.HTTP_400_BAD_REQUEST)

    payload = {
        'url': url,
    }
    if data.get('email'):
        payload['email'] = data.get('email')
    if data.get('campaign'):
        payload['campaign'] = data.get('campaign')

    try:
        token = signing.dumps(payload)
        # Devolver token en texto plano para clientes ligeros (VFP, scripts)
        return HttpResponse(token, content_type='text/plain')
    except Exception as e:
        logger.exception('Error generando token de tracking')
        return Response({'error': 'could not generate token'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def track_preview(request):
    """Devuelve el payload del token sin registrar la apertura.

    Útil para clientes que quieren validar/previewear el link (VFP, scripts)
    sin provocar que se registre un `LinkOpen`.
    """
    token = request.GET.get('t')
    if not token:
        return HttpResponseBadRequest("missing token")
    try:
        payload = signing.loads(token, max_age=60 * 60 * 24 * 30)  # 30 días
    except Exception:
        return HttpResponseBadRequest("token inválido o expirado")

    # Devolver sólo el payload (no creamos LinkOpen)
    return Response(payload)


@api_view(['POST'])
@permission_classes([AllowAny])
def track_shorten(request):
    """Genera un link corto que redirige al endpoint de tracking existente."""
    data = request.data or {}
    token = (data.get('token') or '').strip()

    if token:
        try:
            payload = signing.loads(token, max_age=60 * 60 * 24 * 30)
        except Exception:
            return Response({'error': 'token inválido o expirado'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        target_url = data.get('url')
        if not target_url:
            return Response({'error': 'url is required'}, status=status.HTTP_400_BAD_REQUEST)

        payload = {'url': target_url}
        if data.get('email'):
            payload['email'] = data.get('email')
        if data.get('campaign'):
            payload['campaign'] = data.get('campaign')

        try:
            token = signing.dumps(payload)
        except Exception:
            logger.exception('Error generando token para acortador')
            return Response({'error': 'could not generate token'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    existing = ShortTrackingLink.objects.filter(token=token).first()
    if existing:
        short_path = reverse('track_short_redirect_api', kwargs={'code': existing.code})
        short_url = request.build_absolute_uri(short_path)
        return HttpResponse(short_url, content_type='text/plain')

    target_url = payload.get('url')
    if not target_url:
        return Response({'error': 'url objetivo no encontrada en token'}, status=status.HTTP_400_BAD_REQUEST)

    short_link = None
    for _ in range(15):
        code = _build_short_code(8)
        try:
            short_link = ShortTrackingLink.objects.create(
                code=code,
                token=token,
                recipient_email=payload.get('email'),
                campaign=payload.get('campaign'),
                target_url=target_url,
            )
            break
        except Exception:
            # Si hubo colisión de código o error puntual, reintentamos con otro código.
            continue

    if not short_link:
        return Response({'error': 'could not create short url'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    short_path = reverse('track_short_redirect_api', kwargs={'code': short_link.code})
    short_url = request.build_absolute_uri(short_path)
    return HttpResponse(short_url, content_type='text/plain')


@api_view(['GET'])
@permission_classes([AllowAny])
def track_short_redirect(request, code):
    """Resuelve un código corto y redirige al endpoint /api/track/ para registrar apertura."""
    short_link = ShortTrackingLink.objects.filter(code=code).first()
    if not short_link:
        return HttpResponseBadRequest('short code inválido')

    track_path = reverse('track_redirect')
    encoded_token = quote(short_link.token, safe='')
    return redirect(f"{track_path}?t={encoded_token}")

class ArticuloViewSet(BaseAppModelViewSet):
    # Limitar queryset base a la empresa configurada en .env
    queryset = Articulos.objects.filter(empresa_id=settings.EMPRESA_ID)
    serializer_class = ArticuloSerializer
    search_fields = ['clave', 'nombre', 'descripcion']  # Búsqueda
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = ['nombre', 'clave', 'ultact']

    def get_queryset(self):
        user = self.request.user
        # Permitir filtrar por artículos discontinuados mediante query param `discontinuados`
        discontinuados_q = self.request.query_params.get('discontinuados')
        oferta_q = self.request.query_params.get('oferta')

        if user.is_authenticated:
            # Obtener claves de artículos favoritos del usuario
            favoritos_claves = Favorito.objects.filter(user=user).values_list('articulo__clave', flat=True)

            # Anotar el queryset para marcar favoritos
            queryset = Articulos.objects.filter(empresa_id=settings.EMPRESA_ID).annotate(
                is_favorito=Case(
                    When(clave__in=favoritos_claves, then=True),
                    default=False,
                    output_field=BooleanField()
                )
            )

            # Si se pide solo discontinuados, aplicar filtro
            if discontinuados_q and discontinuados_q.lower() in ['1', 'true', 's']:
                queryset = queryset.filter(discontinuado='S')

            # Si se pide solo ofertas, intentar filtrar por el campo disponible que contenga 'ofert'
            if oferta_q and oferta_q.lower() in ['1', 'true', 's']:
                try:
                    # Buscar un campo del modelo cuyo nombre contenga 'ofert' o 'oferta'
                    ofert_field = None
                    for f in Articulos._meta.get_fields():
                        name = getattr(f, 'name', '')
                        if 'ofert' in name.lower() or 'oferta' in name.lower():
                            ofert_field = name
                            break

                    if ofert_field:
                        # Sólo incluir artículos marcados como oferta y que tengan stock mayor a 0
                        queryset = queryset.filter(**{ofert_field: 'S'}).filter(stock__gt=0)
                except Exception:
                    # Si algo falla, no interrumpir; devolver queryset sin filtrar
                    pass

            queryset = queryset.order_by('-is_favorito', 'clave')
            return queryset

        # Para usuarios no autenticados, usar el queryset por defecto y aplicar el filtro si corresponde
        qs = super().get_queryset()
        if discontinuados_q and discontinuados_q.lower() in ['1', 'true', 's']:
            qs = qs.filter(discontinuado='S')
        # Si se solicita sólo ofertas, filtrar por campo de oferta y stock>0
        if oferta_q and oferta_q.lower() in ['1', 'true', 's']:
            try:
                ofert_field = None
                for f in Articulos._meta.get_fields():
                    name = getattr(f, 'name', '')
                    if 'ofert' in name.lower() or 'oferta' in name.lower():
                        ofert_field = name
                        break

                if ofert_field:
                    qs = qs.filter(**{ofert_field: 'S'}).filter(stock__gt=0)
            except Exception:
                pass
        return qs

    def list(self, request, *args, **kwargs):
        search_query = request.query_params.get('search', None)
        if search_query and request.user.is_authenticated:
            # Guardar la búsqueda
            Busqueda.objects.create(user=request.user, query=search_query)
        return super().list(request, *args, **kwargs)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        request = self.request
        condicion_pago = request.query_params.get('condicion_pago') or '00'
        custom_params = {
            'modalidad': request.query_params.get('modalidad', 'retira'),
            'con_impuestos': request.query_params.get('con_impuestos', 'true').lower() == 'true',
            'condicion_pago': condicion_pago,
        }
        # print("Custom context params:", custom_params)  # Debug
        context.update(custom_params)
        return context    

class FormasPagoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            cliente = request.user.cliente
            lista_precio = cliente.lista_precio

            # Filtrar formas de pago: lista == lista_precio o lista está vacía
            formas_pago = FormaPago.objects.filter(
                models.Q(lista=lista_precio) | models.Q(lista='')
            ).distinct()

            serializer = FormaPagoSerializer(formas_pago, many=True)
            return Response(serializer.data)

        except Cliente.DoesNotExist:
            return Response(
                {"error": "Cliente no encontrado."}, 
                status=404
            )    


# views.py
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def keep_alive(request):
    try:
        sesion = RegistroSesion.objects.filter(
            usuario=request.user,
            fin_sesion__isnull=True
        ).latest('inicio_sesion')
        sesion.last_activity = timezone.now()
        sesion.save(update_fields=['last_activity'])
        return Response({'message': 'Actividad registrada'}, status=200)
    except RegistroSesion.DoesNotExist:
        return Response({'error': 'No hay sesión activa'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def consultar_precio(request):
    """
    Endpoint para consultar el precio de un artículo.
    Registra la consulta en la base de datos y retorna el precio.
    """
    from .models import ConsultaPrecio
    
    try:
        articulo_clave = request.data.get('articulo_clave')
        if not articulo_clave:
            return Response({'error': 'La clave del artículo es requerida'}, status=400)
        
        try:
            articulo = Articulos.objects.get(clave=articulo_clave)
        except Articulos.DoesNotExist:
            return Response({'error': 'Artículo no encontrado'}, status=404)
        
        # Obtener la IP del usuario
        def get_client_ip(request):
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
            return ip
        
        ip_address = get_client_ip(request)
        
        # Registrar la consulta de precio
        ConsultaPrecio.objects.create(
            usuario=request.user,
            articulo=articulo,
            ip_address=ip_address
        )
        
        # Obtener datos del cliente para calcular el precio
        try:
            cliente = Cliente.objects.select_related('codigo_localidad', 'condicion_pago').get(user=request.user)
        except Cliente.DoesNotExist:
            return Response({'error': 'Cliente no encontrado'}, status=404)
        
        # Obtener parámetros de consulta
        modalidad = request.data.get('modalidad', 'retira')
        con_impuestos = request.data.get('con_impuestos', True)
        condicion_pago_id = request.data.get('condicion_pago', cliente.condicion_pago.id if cliente.condicion_pago else None)
        
        precio_calculado = calcular_precio_articulo(
            articulo=articulo,
            cliente=cliente,
            modalidad=modalidad,
            con_impuestos=con_impuestos,
            condicion_pago_id=condicion_pago_id,
        )
        
        logger.info(
            "Usuario %s consulto precio de %s - %s: $%s",
            request.user.username,
            articulo.clave,
            articulo.nombre,
            precio_calculado,
        )
        
        return Response({
            'success': True,
            'articulo': {
                'clave': articulo.clave,
                'nombre': articulo.nombre,
                'precio_lista': precio_calculado,
                'modalidad': modalidad,
                'con_impuestos': con_impuestos
            },
            'message': 'Precio consultado exitosamente'
        })
        
    except Exception as e:
        logger.exception("Error al consultar precio")
        return Response({
            'error': 'Error al consultar precio',
            'details': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def exportar_favoritos(request):
    """
    Endpoint para exportar todos los artículos favoritos del usuario con información completa.
    Optimizado para manejar grandes cantidades de datos.
    """
    try:
        # Obtener datos del cliente para calcular precios
        try:
            cliente = Cliente.objects.select_related('codigo_localidad', 'condicion_pago').get(user=request.user)
        except Cliente.DoesNotExist:
            return Response({'error': 'Cliente no encontrado'}, status=404)
        
        # Obtener parámetros de consulta (los mismos que usa en la vista principal)
        modalidad = request.query_params.get('modalidad', 'retira')
        con_impuestos = request.query_params.get('con_impuestos', 'true').lower() == 'true'
        condicion_pago_id = request.query_params.get('condicion_pago', cliente.condicion_pago.id if cliente.condicion_pago else '00')
        
        # Obtener todos los favoritos del usuario con artículos relacionados
        favoritos = list(
            Favorito.objects.filter(user=request.user)
            .select_related('articulo')
            .only(
                'fecha_creacion',
                'articulo__clave',
                'articulo__nombre',
                'articulo__unidad',
                'articulo__peso',
                'articulo__iva',
                'articulo__pblret1',
                'articulo__pblrep1',
                'articulo__pblret4',
                'articulo__pblrep4',
                'articulo__ultact',
                'articulo__visible',
                'articulo__grupo',
                'articulo__stock',
                'articulo__tiporeparto',
            )
        )
        
        if not favoritos:
            return Response({'error': 'No tienes artículos favoritos para exportar'}, status=404)

        try:
            forma_pago = FormaPago.objects.get(id=condicion_pago_id)
            precio_condicion_pago_id = condicion_pago_id
        except FormaPago.DoesNotExist:
            forma_pago = None
            precio_condicion_pago_id = None

        bonificaciones_cliente = list(
            BonificacionCliente.objects.filter(cliente=cliente)
            .only('desde_articulo', 'hasta_articulo', 'bonificacion')
            .order_by('pk')
        )
        
        # Preparar datos para exportación
        datos_exportacion = []
        for favorito in favoritos:
            articulo = favorito.articulo
            precio_calculado = calcular_precio_articulo(
                articulo=articulo,
                cliente=cliente,
                modalidad=modalidad,
                con_impuestos=con_impuestos,
                condicion_pago_id=precio_condicion_pago_id,
                forma_pago=forma_pago,
                bonificaciones_cliente=bonificaciones_cliente,
            )
            
            datos_exportacion.append({
                'clave': articulo.clave,
                'nombre': articulo.nombre,
                'unidad': articulo.unidad,
                'peso': float(articulo.peso),
                'iva': float(articulo.iva),
                'precio_actual': float(precio_calculado),
                'modalidad': modalidad,
                'con_impuestos': con_impuestos,
                'precio_base_retira_l1': float(articulo.pblret1),
                'precio_base_reparto_l1': float(articulo.pblrep1),
                'precio_base_retira_l4': float(articulo.pblret4),
                'precio_base_reparto_l4': float(articulo.pblrep4),
                'ultima_actualizacion': articulo.ultact.strftime('%Y-%m-%d') if articulo.ultact else '',
                'visible': 'Sí' if articulo.visible == 'S' else 'No',
                'grupo': articulo.grupo,
                'stock': float(articulo.stock),
                'fecha_favorito': favorito.fecha_creacion.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        # Log para auditoría
        logger.info("Usuario %s exporto %s articulos favoritos", request.user.username, len(datos_exportacion))

        # Registrar el evento de exportación en la base de datos (no bloquear la respuesta)
        try:
            from .models import ExportEvent

            # Obtener IP y user-agent
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')

            user_agent = request.META.get('HTTP_USER_AGENT', '')

            ExportEvent.objects.create(
                usuario=request.user,
                tipo='favoritos',
                parametros={
                    'modalidad': modalidad,
                    'con_impuestos': con_impuestos,
                    'condicion_pago': condicion_pago_id
                },
                total_items=len(datos_exportacion),
                ip_address=ip_address,
                user_agent=user_agent
            )
        except Exception as e:
            # No queremos bloquear la exportación por un fallo en el registro
            logger.warning("No se pudo registrar ExportEvent: %s", e)

        return Response({
            'success': True,
            'data': datos_exportacion,
            'total_articulos': len(datos_exportacion),
            'parametros': {
                'modalidad': modalidad,
                'con_impuestos': con_impuestos,
                'condicion_pago': condicion_pago_id
            },
            'message': f'Datos de {len(datos_exportacion)} artículos favoritos preparados para exportación'
        })
        
    except Exception as e:
        logger.exception("Error al exportar favoritos")
        return Response({
            'error': 'Error al exportar favoritos',
            'details': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_kpis(request):
    """
    Endpoint para obtener los KPIs del dashboard del cliente logueado
    basados en su cuenta corriente.
    """
    try:
        # Obtener el cliente asociado al usuario logueado
        try:
            cliente = Cliente.objects.get(user=request.user)
            numero_cliente = cliente.numero_cliente
        except Cliente.DoesNotExist:
            return Response({
                'error': 'Cliente no encontrado',
                'message': 'El usuario no tiene un cliente asociado'
            }, status=404)

        # Importar el modelo aquí para evitar problemas de importación circular
        from .models import CuentaCorrienteCliente

        # Obtener todos los registros de cuenta corriente del cliente
        cuenta_corriente = CuentaCorrienteCliente.objects.filter(cliente=numero_cliente)
        
        if not cuenta_corriente.exists():
            # Si no hay registros, devolver KPIs en cero
            return Response({
                'success': True,
                'data': {
                    'saldo_total': 0.00,
                    'cantidad_comprobantes': 0,
                    'total_pagos': 0.00,
                    'total_creditos': 0.00,
                    'total_facturas_debitos': 0.00,
                    'deuda_vencida': 0.00,
                    'deuda_por_vencer': 0.00
                }
            })

        # Calcular KPIs usando el ORM de Django
        from django.db.models import Sum, Count, Q
        from django.utils import timezone
        
        # 1. Saldo total actual (suma de todos los saldos)
        saldo_total = cuenta_corriente.aggregate(
            total=Sum('saldo')
        )['total'] or 0

        # 2. Cantidad de comprobantes únicos
        cantidad_comprobantes = cuenta_corriente.values('numero').distinct().count()

        # 3. Total de pagos (código='R')
        total_pagos = cuenta_corriente.filter(
            codigo='R'
        ).aggregate(
            total=Sum('total')
        )['total'] or 0

        # 4. Total de créditos (código='C') 
        total_creditos = cuenta_corriente.filter(
            codigo='C'
        ).aggregate(
            total=Sum('total')
        )['total'] or 0

        # 5. Total de facturas y débitos (código='F' o 'D')
        total_facturas_debitos = cuenta_corriente.filter(
            Q(codigo='F') | Q(codigo='D')
        ).aggregate(
            total=Sum('total')
        )['total'] or 0

        # 6. Deuda vencida (saldo > 0 y fecha de vencimiento < hoy)
        hoy = timezone.now().date()
        deuda_vencida = cuenta_corriente.filter(
            saldo__gt=0,
            fechaven__lt=hoy
        ).aggregate(
            total=Sum('saldo')
        )['total'] or 0

        # 7. Deuda por vencer (saldo > 0 y fecha de vencimiento >= hoy)
        deuda_por_vencer = cuenta_corriente.filter(
            saldo__gt=0,
            fechaven__gte=hoy
        ).aggregate(
            total=Sum('saldo')
        )['total'] or 0

        # Preparar respuesta
        kpis = {
            'saldo_total': float(saldo_total),
            'cantidad_comprobantes': cantidad_comprobantes,
            'total_pagos': float(total_pagos),
            'total_creditos': float(total_creditos),
            'total_facturas_debitos': float(total_facturas_debitos),
            'deuda_vencida': float(deuda_vencida),
            'deuda_por_vencer': float(deuda_por_vencer)
        }

        print(f"📊 KPIs dashboard generados para cliente {numero_cliente}: {kpis}")

        return Response({
            'success': True,
            'data': kpis,
            'cliente': {
                'numero': numero_cliente,
                'nombre': cliente.nombre
            }
        })

    except Exception as e:
        print(f"❌ Error al obtener KPIs del dashboard: {e}")
        import traceback
        traceback.print_exc()
        return Response({
            'error': 'Error al obtener KPIs del dashboard',
            'details': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def comprobantes_cliente(request):
    """
    Endpoint para obtener los comprobantes de cuenta corriente del cliente logueado
    con paginación y filtros de fecha.
    """
    try:
        # Obtener el cliente asociado al usuario logueado
        try:
            cliente = Cliente.objects.get(user=request.user)
            numero_cliente = cliente.numero_cliente
        except Cliente.DoesNotExist:
            return Response({
                'error': 'Cliente no encontrado',
                'message': 'El usuario no tiene un cliente asociado'
            }, status=404)

        # Importar el modelo aquí para evitar problemas de importación circular
        from .models import CuentaCorrienteCliente
        from django.core.paginator import Paginator
        from datetime import datetime, timedelta
        from django.utils import timezone

        # Obtener parámetros de filtro y paginación
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        fecha_desde = request.GET.get('fecha_desde')
        fecha_hasta = request.GET.get('fecha_hasta')
        codigo_tipo = request.GET.get('codigo')  # F, D, R, C

        # Base queryset
        queryset = CuentaCorrienteCliente.objects.filter(cliente=numero_cliente)

        # Aplicar filtros de fecha
        if fecha_desde:
            try:
                fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                queryset = queryset.filter(fecha__gte=fecha_desde_obj)
            except ValueError:
                return Response({
                    'error': 'Formato de fecha inválido',
                    'message': 'Use el formato YYYY-MM-DD para fecha_desde'
                }, status=400)

        if fecha_hasta:
            try:
                fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
                queryset = queryset.filter(fecha__lte=fecha_hasta_obj)
            except ValueError:
                return Response({
                    'error': 'Formato de fecha inválido', 
                    'message': 'Use el formato YYYY-MM-DD para fecha_hasta'
                }, status=400)

        # Filtro por tipo de comprobante
        if codigo_tipo:
            queryset = queryset.filter(codigo=codigo_tipo.upper())

        # Ordenar por fecha más reciente
        queryset = queryset.order_by('-fecha', '-numero')

        # Aplicar paginación
        paginator = Paginator(queryset, page_size)
        
        if page > paginator.num_pages and paginator.num_pages > 0:
            return Response({
                'error': 'Página no encontrada',
                'message': f'La página {page} no existe. Total de páginas: {paginator.num_pages}'
            }, status=404)

        comprobantes_page = paginator.get_page(page)

        # Convertir a formato JSON serializable
        comprobantes_data = []
        for comprobante in comprobantes_page:
            comprobantes_data.append({
                'numero': comprobante.numero,
                'fecha': comprobante.fecha.strftime('%Y-%m-%d'),
                'fecha_vencimiento': comprobante.fechaven.strftime('%Y-%m-%d'),
                'fecha_primer_vencimiento': comprobante.fecha1venc.strftime('%Y-%m-%d'),
                'codigo': comprobante.codigo,
                'tipo_comprobante': {
                    'F': 'Factura',
                    'D': 'Débito', 
                    'R': 'Recibo/Pago',
                    'C': 'Crédito'
                }.get(comprobante.codigo, comprobante.codigo),
                'neto': float(comprobante.neto),
                'total': float(comprobante.total),
                'saldo': float(comprobante.saldo),
                'forma_pago': comprobante.forma_pago,
                'pago': comprobante.pago,
                'clase': comprobante.clase,
                'estado': 'Vencido' if comprobante.fechaven < timezone.now().date() and comprobante.saldo > 0 else 'Vigente'
            })

        # Estadísticas de la página actual
        totales_pagina = {
            'total_neto': sum(float(c.neto) for c in comprobantes_page if c.codigo in ['F', 'D']),
            'total_importe': sum(float(c.total) for c in comprobantes_page if c.codigo in ['F', 'D']),
            'total_saldo': sum(float(c.saldo) for c in comprobantes_page),
            'cantidad': len(comprobantes_data)
        }

        # Estadísticas generales (aplicando los mismos filtros)
        totales_generales = {
            'total_registros': queryset.count(),
            'total_neto_filtrado': sum(float(c.neto) for c in queryset if c.codigo in ['F', 'D']),
            'total_importe_filtrado': sum(float(c.total) for c in queryset if c.codigo in ['F', 'D']),
            'total_saldo_filtrado': sum(float(c.saldo) for c in queryset)
        }

        # Información de paginación
        paginacion = {
            'current_page': page,
            'total_pages': paginator.num_pages,
            'page_size': page_size,
            'total_records': paginator.count,
            'has_next': comprobantes_page.has_next(),
            'has_previous': comprobantes_page.has_previous(),
            'next_page': comprobantes_page.next_page_number() if comprobantes_page.has_next() else None,
            'previous_page': comprobantes_page.previous_page_number() if comprobantes_page.has_previous() else None
        }

        print(f"📄 Comprobantes obtenidos para cliente {numero_cliente}: página {page} de {paginator.num_pages}")

        return Response({
            'success': True,
            'data': comprobantes_data,
            'pagination': paginacion,
            'totales_pagina': totales_pagina,
            'totales_generales': totales_generales,
            'filtros_aplicados': {
                'fecha_desde': fecha_desde,
                'fecha_hasta': fecha_hasta,
                'codigo_tipo': codigo_tipo,
                'cliente': numero_cliente
            }
        })

    except Exception as e:
        print(f"❌ Error al obtener comprobantes: {e}")
        import traceback
        traceback.print_exc()
        return Response({
            'error': 'Error al obtener comprobantes',
            'details': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalle_comprobante(request, numero_comprobante):
    """
    Endpoint para obtener el detalle de un comprobante específico.
    - Códigos C, D, F: obtiene datos de la tabla Factura
    - Código R: por implementar (pagos/recibos)
    """
    try:
        # Obtener el cliente asociado al usuario logueado
        try:
            cliente = Cliente.objects.get(user=request.user)
            numero_cliente = cliente.numero_cliente
        except Cliente.DoesNotExist:
            return Response({
                'error': 'Cliente no encontrado',
                'message': 'El usuario no tiene un cliente asociado'
            }, status=404)

        # Importar modelos
        from .models import CuentaCorrienteCliente, Factura

        # LOG: depuración - registrar quien solicita y qué número
        try:
            usuario_nombre = request.user.username
        except Exception:
            usuario_nombre = str(request.user)
        print(f"[detalle_comprobante] solicitud usuario={usuario_nombre} cliente_num={numero_cliente} numero_comprobante={numero_comprobante}")

        # Primero verificar que el comprobante pertenece al cliente
        try:
            comprobante_cc = CuentaCorrienteCliente.objects.get(
                cliente=numero_cliente,
                numero=numero_comprobante
            )
        except CuentaCorrienteCliente.DoesNotExist:
            # LOG: detalle para depuración en servidor
            print(f"[detalle_comprobante] NO ENCONTRADO cliente={numero_cliente} numero={numero_comprobante}")
            return Response({
                'error': 'Comprobante no encontrado',
                'message': f'El comprobante {numero_comprobante} no existe o no pertenece al cliente'
            }, status=404)

        codigo_comprobante = comprobante_cc.codigo

        # Si es código R (Recibo/Pago), buscar en la tabla 'cobranzas' y devolver líneas de pago
        if codigo_comprobante == 'R':
            from .models import Cobranzas

            # Buscar registros que pertenezcan al recibo o al comprobante asociado
            cobranzas_qs = Cobranzas.objects.filter(models.Q(recibo=numero_comprobante) | models.Q(comp=numero_comprobante)).order_by('id')

            if not cobranzas_qs.exists():
                return Response({
                    'error': 'Detalle de recibo no encontrado',
                    'message': f'No se encontraron registros de cobranza para el recibo {numero_comprobante}'
                }, status=404)

            # Construir encabezado a partir de la cuenta corriente y el primer registro (si existe)
            primer = cobranzas_qs.first()
            encabezado = {
                'numero': comprobante_cc.numero,
                'codigo': comprobante_cc.codigo,
                'tipo_comprobante': 'Recibo/Pago',
                'fecha': comprobante_cc.fecha.strftime('%Y-%m-%d') if comprobante_cc.fecha else None,
                'total': float(comprobante_cc.total),
                'saldo': float(comprobante_cc.saldo),
                'forma_pago': comprobante_cc.forma_pago,
                'estado': 'Vencido' if comprobante_cc.fechaven < timezone.now().date() and comprobante_cc.saldo > 0 else 'Vigente'
            }

            items = []
            total_monto = 0
            for c in cobranzas_qs:
                monto = float(c.monto) if c.monto is not None else 0.0
                total_monto += monto
                items.append({
                    'tipo': c.tipo,
                    'recibo': c.recibo,
                    'monto': monto,
                    'detalle': c.detalle,
                    'banco': c.banco,
                    'numero': c.numero,
                    'vence': c.vence.strftime('%Y-%m-%d') if c.vence else None,
                    'impentra': float(c.impentra) if c.impentra is not None else 0.0,
                    'comp': c.comp
                })

            resumen = {
                'cantidad_items': len(items),
                'total_monto': total_monto
            }

            return Response({
                'success': True,
                'data': {
                    'encabezado': encabezado,
                    'items': items,
                    'resumen': resumen
                }
            })

        # Para códigos C, D, F: buscar en tabla Factura
        if codigo_comprobante in ['C', 'D', 'F']:
            # Obtener todos los renglones de la factura
            renglones_factura = Factura.objects.filter(
                cliente=numero_cliente,
                comp=numero_comprobante
            ).order_by('item')

            if not renglones_factura.exists():
                return Response({
                    'error': 'Detalle no encontrado',
                    'message': f'No se encontraron detalles para el comprobante {numero_comprobante}'
                }, status=404)

            # Tomar datos del encabezado del primer renglón
            primer_renglon = renglones_factura.first()
            
            # Preparar datos del encabezado
            encabezado = {
                'numero': primer_renglon.comp,
                'codigo': primer_renglon.codigo,
                'tipo_comprobante': {
                    'F': 'Factura',
                    'D': 'Nota de Débito',
                    'C': 'Nota de Crédito'
                }.get(primer_renglon.codigo, primer_renglon.codigo),
                'fecha': primer_renglon.fecha.strftime('%Y-%m-%d'),
                'fecha_vencimiento': primer_renglon.fechaven.strftime('%Y-%m-%d'),
                'fecha_primer_vencimiento': primer_renglon.fecha1venc.strftime('%Y-%m-%d'),
                'cliente': {
                    'numero': primer_renglon.cliente,
                    'nombre': primer_renglon.nombre
                },
                'localidad': primer_renglon.nombre_localidad,
                'lista_precio': primer_renglon.lista,
                'vendedor': primer_renglon.nombre_vendedor,
                'clase': primer_renglon.clase,
                'reparto': primer_renglon.reparto,
                'nota': primer_renglon.nota or '',
                'totales': {
                    'subtotal': float(primer_renglon.neto_neto if primer_renglon.regiva.strip() == 'C' else primer_renglon.neto),
                    'iva': float(primer_renglon.iva),
                    'percepcion_dgr': float(primer_renglon.percepcion_dgr),
                    'flete': float(primer_renglon.flete),
                    'total': float(primer_renglon.neto),
                    'saldo': float(comprobante_cc.saldo)  # Saldo actual de cuenta corriente
                },
                'estado': 'Vencido' if comprobante_cc.fechaven < timezone.now().date() and comprobante_cc.saldo > 0 else 'Vigente',
                'forma_pago' : primer_renglon.forma_pago
            }

            # Preparar datos de los renglones/items
            items = []
            for renglon in renglones_factura:
                items.append({
                    'item': renglon.item,
                    'articulo': {
                        'clave': renglon.clave,
                        'descripcion': renglon.nota,
                        'unidad': renglon.unidad
                    },
                    'cantidad': float(renglon.cantidad),
                    'precio_unitario': float(renglon.unitario),
                    'precio_lista': float(renglon.precio),
                    'bonificacion': float(renglon.boni),
                    'descuento_1': float(renglon.des1),
                    'neto_renglon': float(renglon.neto_renglon) if renglon.neto_renglon else 0,
                    'alicuota_iva': float(renglon.aliciva),
                    'total_renglon': float(renglon.neto_renglon or 0) * (1 + float(renglon.aliciva) / 100) if renglon.regiva.strip() != 'C' else float(renglon.neto_renglon or 0),
                })

            return Response({
                'success': True,
                'data': {
                    'encabezado': encabezado,
                    'items': items,
                    'resumen': {
                        'cantidad_items': len(items),
                        'peso_total': sum(float(r.cantidad) for r in renglones_factura),
                        'subtotal': float(primer_renglon.neto),
                        'total': float(primer_renglon.total)
                    }
                }
            })

        # Si llegamos aquí, es un código no reconocido
        return Response({
            'error': 'Código de comprobante no soportado',
            'message': f'El código "{codigo_comprobante}" no está implementado'
        }, status=400)

    except Exception as e:
        print(f"❌ Error al obtener detalle del comprobante {numero_comprobante}: {e}")
        import traceback
        traceback.print_exc()
        return Response({
            'error': 'Error al obtener detalle del comprobante',
            'details': str(e)
        }, status=500)
