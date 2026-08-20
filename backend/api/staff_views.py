from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from django.db import models, transaction
from django.db.models import Count, Sum, F
from datetime import timedelta, datetime
from .models import RegistroSesion, Articulos, Favorito, Pedido, Busqueda, Cliente, Localidades, FormaPago, ArticuloVista, BotConversationLog
from .models import LinkOpen
from .serializers import ArticuloStaffSerializer, BusquedaCountSerializer
from django.contrib.auth.models import User
from .serializers import ExportEventSerializer
from .models import ExportEvent
from django.db.models import Q, Max
from django.db.models.functions import TruncDate
import logging

logger = logging.getLogger('api')


@api_view(['GET'])
@permission_classes([IsAdminUser])
def bot_report(request):
    days = int(request.query_params.get('days', 7))
    days = max(1, min(days, 90))
    since = timezone.now() - timedelta(days=days)
    logs = BotConversationLog.objects.filter(fecha_hora__gte=since)

    def grouped_counts(field):
        return {
            row[field]: row['total']
            for row in logs.values(field).annotate(total=Count('id')).order_by(field)
        }

    recent = [
        {
            'id': log.id,
            'fecha_hora': log.fecha_hora.isoformat(),
            'origen': log.origen,
            'usuario': log.usuario.username if log.usuario else None,
            'telefono': log.telefono,
            'mensaje_usuario': log.mensaje_usuario,
            'respuesta_bot': log.respuesta_bot,
            'intencion': log.intencion,
            'estado': log.estado,
            'contexto': log.contexto,
            'error_tecnico': log.error_tecnico,
        }
        for log in logs.select_related('usuario').order_by('-fecha_hora')[:50]
    ]

    by_status = grouped_counts('estado')
    recommendations = []
    if by_status.get('ambiguous', 0):
        recommendations.append('Revisar consultas ambiguas: indican productos que necesitan mejores sinonimos o desambiguacion.')
    if by_status.get('not_found', 0):
        recommendations.append('Revisar no encontrados: pueden requerir aliases, marcas o busqueda mas flexible.')
    if by_status.get('fallback', 0):
        recommendations.append('Revisar fallback: son mensajes que el bot todavia no entiende como intencion concreta.')
    if not recommendations:
        recommendations.append('Sin alertas fuertes en el periodo seleccionado.')

    return Response({
        'period_days': days,
        'total_messages': logs.count(),
        'by_origin': grouped_counts('origen'),
        'by_intention': grouped_counts('intencion'),
        'by_status': by_status,
        'recent': recent,
        'recommendations': recommendations,
    })

class MostFavoritedProductsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, format=None):
        # Obtener filtro de usuario si está presente
        filtro_usuario = request.query_params.get('usuario')
        
        # Query base para productos favoritos
        favoritos_query = Favorito.objects.select_related('articulo', 'user')
        
        # Aplicar filtro de usuario si está presente
        if filtro_usuario:
            favoritos_query = favoritos_query.filter(user__username=filtro_usuario)
        
        # Obtener artículos más favoritos
        most_favorited_products = Articulos.objects.filter(
            favoritos__in=favoritos_query
        ).annotate(
            favoritos_count=Count('favoritos', filter=models.Q(favoritos__in=favoritos_query))
        ).order_by('-favoritos_count')[:10]

        serializer = ArticuloStaffSerializer(most_favorited_products, many=True)
        
        if filtro_usuario:
            print(f"🔍 Productos favoritos filtrados por usuario: {filtro_usuario}")
            
        return Response(serializer.data)

class SalesSummaryView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, format=None):
        # Obtener filtro de usuario si está presente
        filtro_usuario = request.query_params.get('usuario')
        
        # Query base para pedidos
        pedidos_query = Pedido.objects.all()
        
        # Aplicar filtro de usuario si está presente
        if filtro_usuario:
            pedidos_query = pedidos_query.filter(user__username=filtro_usuario)
        
        total_orders = pedidos_query.count()
        total_sales = pedidos_query.aggregate(total_sum=Sum('total'))['total_sum']

        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        sales_last_30_days = pedidos_query.filter(
            fecha_creacion__range=(start_date, end_date)
        ).aggregate(total_sum=Sum('total'))['total_sum']

        if filtro_usuario:
            print(f"🔍 Resumen de ventas filtrado por usuario: {filtro_usuario}")

        return Response({
            'total_orders': total_orders,
            'total_sales': total_sales if total_sales else 0,
            'sales_last_30_days': sales_last_30_days if sales_last_30_days else 0,
        })

class MostSearchedWordsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, format=None):
        # Obtener filtro de usuario si está presente
        filtro_usuario = request.query_params.get('usuario')
        
        # Query base para búsquedas
        busquedas_query = Busqueda.objects.all()
        
        # Aplicar filtro de usuario si está presente
        if filtro_usuario:
            busquedas_query = busquedas_query.filter(user__username=filtro_usuario)
        
        most_searched_words = busquedas_query.values('query').annotate(
            count=Count('query')
        ).order_by('-count')[:10]

        if filtro_usuario:
            print(f"🔍 Búsquedas filtradas por usuario: {filtro_usuario}")

        return Response(most_searched_words)
    
class DailySalesView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, format=None):
        # Obtener filtro de usuario si está presente
        filtro_usuario = request.query_params.get('usuario')
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        # Query base para pedidos con filtro de fecha
        pedidos_query = Pedido.objects.filter(
            fecha_creacion__range=(start_date, end_date)
        )
        
        # Aplicar filtro de usuario si está presente
        if filtro_usuario:
            pedidos_query = pedidos_query.filter(user__username=filtro_usuario)

        # Agrupar por fecha y sumar el total
        daily_data = pedidos_query.extra(
            select={'day': 'date(fecha_creacion)'}
        ).values('day').annotate(
            total_ventas=Sum('total')
        ).order_by('day')

        dates = [entry['day'] for entry in daily_data]
        sales = [float(entry['total_ventas']) for entry in daily_data]

        if filtro_usuario:
            print(f"🔍 Ventas diarias filtradas por usuario: {filtro_usuario}")

        return Response({
            'dates': dates,
            'sales': sales,
        })    


@api_view(['GET'])
def session_metrics(request):
    if not request.user.is_staff:
        return Response({'error': 'No autorizado'}, status=403)

    # Obtener filtro de usuario si está presente
    filtro_usuario = request.query_params.get('usuario')

    ahora = timezone.now()
    inicio_rango = ahora - timedelta(days=30)

    sesiones_por_hora = [0] * 24

    # Query base para sesiones
    sesiones_query = RegistroSesion.objects.filter(
        inicio_sesion__gte=inicio_rango,
        inicio_sesion__lt=ahora
    )
    
    # Aplicar filtro de usuario si está presente
    if filtro_usuario:
        sesiones_query = sesiones_query.filter(usuario__username=filtro_usuario)
    
    sesiones = sesiones_query

    # ✅ Convertir a hora local para contar correctamente
    for sesion in sesiones:
        hora_local = timezone.localtime(sesion.inicio_sesion).hour
        sesiones_por_hora[hora_local] += 1

    dias = 30
    promedio_por_hora = [round(count / dias, 2) for count in sesiones_por_hora]
    labels = [f"{h}:00" for h in range(24)]

    # === Métricas adicionales ===
    inicio_hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    sesiones_hoy_query = RegistroSesion.objects.filter(inicio_sesion__gte=inicio_hoy)
    
    if filtro_usuario:
        sesiones_hoy_query = sesiones_hoy_query.filter(usuario__username=filtro_usuario)
    
    sesiones_hoy = sesiones_hoy_query

    sesiones_activas_query = RegistroSesion.objects.filter(
        last_activity__gte=ahora - timedelta(minutes=30),
        fin_sesion__isnull=True
    )
    
    if filtro_usuario:
        sesiones_activas_query = sesiones_activas_query.filter(usuario__username=filtro_usuario)
    
    sesiones_activas = sesiones_activas_query.count()

    duraciones_segundos = [
        s.duracion.total_seconds() for s in sesiones_hoy if s.duracion
    ]

    avg_duration = f"{round(sum(duraciones_segundos) / 60 / len(duraciones_segundos))} min" \
        if duraciones_segundos else "0 min"

    total_duration = f"{sum(duraciones_segundos) / 3600:.1f} h" if duraciones_segundos else "0 h"

    if filtro_usuario:
        print(f"🔍 Métricas de sesión filtradas por usuario: {filtro_usuario}")

    return Response({
        'sessionsToday': sesiones_hoy.count(),
        'activeUsers': sesiones_activas,
        'avgDuration': avg_duration,
        'totalDuration': total_duration,
        'sessions_by_hour': {
            'labels': labels,
            'data': promedio_por_hora
        }
    })    


@api_view(['GET'])
@permission_classes([IsAdminUser])
def ingresos_por_dispositivo(request):
    """Agrupa ingresos (sesiones) por tipo de dispositivo usando el user-agent."""
    try:
        filtro_usuario = request.query_params.get('usuario')
        dias = int(request.query_params.get('dias', 30))
        dias = max(1, min(dias, 365))

        inicio_rango = timezone.now() - timedelta(days=dias)

        sesiones_query = RegistroSesion.objects.filter(
            inicio_sesion__gte=inicio_rango
        )

        if filtro_usuario:
            sesiones_query = sesiones_query.filter(usuario__username=filtro_usuario)

        user_agents = sesiones_query.values_list('user_agent', flat=True)

        mobile_keywords = (
            'mobile', 'android', 'iphone', 'ipad', 'ipod',
            'windows phone', 'blackberry', 'opera mini', 'iemobile',
            'tablet', 'phone', 'silk', 'kindle',
            # WebViews / in-app browsers comunes en mobile
            'whatsapp', 'fb_iab', 'fban', 'fbav', 'instagram', 'line/',
            'micromessenger', 'wv'
        )
        desktop_keywords = (
            'windows nt', 'macintosh', 'x11', 'linux x86_64',
            'cros', 'ubuntu', 'fedora', 'freebsd'
        )

        mobile_count = 0
        desktop_count = 0
        unknown_count = 0

        for ua in user_agents:
            ua_normalized = (ua or '').lower()
            if not ua_normalized.strip():
                unknown_count += 1
            elif any(keyword in ua_normalized for keyword in mobile_keywords):
                mobile_count += 1
            elif any(keyword in ua_normalized for keyword in desktop_keywords):
                desktop_count += 1
            else:
                unknown_count += 1

        return Response({
            'labels': ['Celular', 'Escritorio'],
            'data': [mobile_count, desktop_count],
            'mobile': mobile_count,
            'desktop': desktop_count,
            'unknown': unknown_count,
            'total': mobile_count + desktop_count + unknown_count,
            'days_window': dias,
        })
    except Exception as e:
        print(f"❌ Error al obtener ingresos por dispositivo: {e}")
        return Response({'error': 'Error al obtener ingresos por dispositivo'}, status=500)
            
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sessions_by_hour(request):
    hoy = timezone.now().date()
    data = RegistroSesion.objects.filter(inicio_sesion__date=hoy) \
        .extra(select={'hour': 'strftime("%%H", inicio_sesion)'}) \
        .values('hour') \
        .annotate(count=models.Count('id')) \
        .order_by('hour')

    hours = [str(h).zfill(2) + ':00' for h in range(24)]
    counts = [0] * 24
    for d in data:
        idx = int(d['hour'])
        counts[idx] = d['count']

    return Response({
        'hours': hours,
        'counts': counts
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def sessions_today_detail(request):
    """Obtiene el detalle de todas las sesiones iniciadas en una fecha específica."""
    # Usar la misma lógica que session_metrics para "hoy"
    ahora = timezone.now()
    inicio_hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Obtener todas las sesiones desde el inicio del día de hoy
    sesiones = RegistroSesion.objects.filter(
        inicio_sesion__gte=inicio_hoy
    ).select_related('usuario', 'cliente').values(
        'id',
        'usuario__username',
        'usuario__first_name',
        'usuario__last_name',
        'cliente__nombre',
        'cliente__numero_cliente',
        'inicio_sesion',
        'fin_sesion',
        'duracion',
        'ip_address'
    ).order_by('-inicio_sesion')
    
    print(f"🔍 Sesiones hoy (desde {inicio_hoy}): {sesiones.count()} encontradas")
    
    return Response(list(sesiones))



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tracking_campaigns(request):
    """Devuelve la lista de campañas registradas y su cantidad de aperturas.

    Requiere que el usuario sea `is_staff`.
    """
    if not request.user.is_staff:
        return Response({'error': 'No autorizado'}, status=403)

    qs = LinkOpen.objects.values('campaign').annotate(count=Count('id')).order_by('-count')
    data = [{'campaign': entry['campaign'] or 'unknown', 'count': entry['count']} for entry in qs]
    return Response(data)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tracking_kpis(request):
    """KPIs básicos para una campaña: total opens, unique emails, unique ips, opens por día (últimos 14 días)."""
    campaign = request.query_params.get('campaign')
    if not campaign:
        return Response({'error': 'campaign parameter required'}, status=400)

    if not request.user.is_staff:
        return Response({'error': 'No autorizado'}, status=403)

    base_qs = LinkOpen.objects.filter(campaign=campaign)
    total_opens = base_qs.count()
    unique_emails = base_qs.exclude(recipient_email__isnull=True).exclude(recipient_email='').values('recipient_email').distinct().count()
    unique_ips = base_qs.values('ip_address').distinct().count()

    # Clasificación simple por user-agent para distinguir celular vs escritorio.
    mobile_keywords = ('android', 'iphone', 'ipad', 'ipod', 'mobile', 'windows phone')
    desktop_keywords = ('windows nt', 'macintosh', 'x11', 'linux x86_64', 'cros')

    device_mobile = 0
    device_desktop = 0
    device_unknown = 0
    for ua in base_qs.values_list('user_agent', flat=True):
        text = (ua or '').lower()
        if any(k in text for k in mobile_keywords):
            device_mobile += 1
        elif any(k in text for k in desktop_keywords):
            device_desktop += 1
        else:
            device_unknown += 1

    # Abrimos una ventana de 14 días usando fecha local para evitar desfasajes de timezone.
    end = timezone.localdate()
    start = end - timedelta(days=13)

    def build_daily_counts(window_start, window_end):
        days_list = [(window_start + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(14)]
        index_by_day = {day_key: idx for idx, day_key in enumerate(days_list)}
        counts_list = [0] * 14

        # Bucket en Python para evitar inconsistencias de timezone/DB.
        tz = timezone.get_current_timezone()
        opened_at_values = base_qs.values_list('opened_at', flat=True)

        for opened_at in opened_at_values:
            if not opened_at:
                continue
            local_dt = timezone.localtime(opened_at, tz) if timezone.is_aware(opened_at) else opened_at
            local_date = local_dt.date()
            if not (window_start <= local_date <= window_end):
                continue
            day_key = local_date.strftime('%Y-%m-%d')
            idx = index_by_day.get(day_key)
            if idx is not None:
                counts_list[idx] += 1

        return days_list, counts_list

    days, counts = build_daily_counts(start, end)

    # Fallback: si no hay datos en esta ventana pero sí en la campaña, usar una ventana
    # que termine en el último evento para mostrar actividad histórica reciente.
    if total_opens > 0 and sum(counts) == 0:
        last_open = base_qs.order_by('-opened_at').values_list('opened_at', flat=True).first()
        if last_open:
            end = timezone.localtime(last_open).date() if timezone.is_aware(last_open) else last_open.date()
            start = end - timedelta(days=13)
            days, counts = build_daily_counts(start, end)

    day_map = {day: count for day, count in zip(days, counts)}

    # Log data useful para debugging del gráfico
    try:
        logger.debug('tracking_kpis: campaign=%s total_opens=%s unique_emails=%s unique_ips=%s day_map=%s days=%s counts=%s',
                 campaign, total_opens, unique_emails, unique_ips, day_map, days, counts)
    except Exception:
        # A veces el logger está configurado para no mostrar DEBUG en dev; usar print para asegurar salida
        print(f"[tracking_kpis] campaign={campaign} total_opens={total_opens} unique_emails={unique_emails} unique_ips={unique_ips} days={days} counts={counts}")

    return Response({
        'campaign': campaign,
        'total_opens': total_opens,
        'unique_emails': unique_emails,
        'unique_ips': unique_ips,
        'days': days,
        'counts': counts,
        'device_counts': {
            'mobile': device_mobile,
            'desktop': device_desktop,
            'unknown': device_unknown,
        },
    })



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def tracking_opens(request):
    """Lista de aperturas para una campaña (paginated)."""
    campaign = request.query_params.get('campaign')

    def _safe_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    page = max(1, _safe_int(request.query_params.get('page', 1), 1))
    page_size = _safe_int(request.query_params.get('page_size', 50), 50)
    page_size = min(max(1, page_size), 200)

    if not campaign:
        return Response({'error': 'campaign parameter required'}, status=400)

    if not request.user.is_staff:
        return Response({'error': 'No autorizado'}, status=403)

    qs = LinkOpen.objects.filter(campaign=campaign).order_by('-opened_at')

    from django.core.paginator import Paginator
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page)

    items = []
    for o in page_obj.object_list:
        items.append({
            'id': o.id,
            'recipient_email': o.recipient_email,
            'ip_address': o.ip_address,
            'user_agent': o.user_agent,
            'referer': o.referer,
            'opened_at': o.opened_at,
            'target_url': o.target_url,
        })

    return Response({
        'results': items,
        'pagination': {
            'current_page': page_obj.number,
            'total_pages': paginator.num_pages,
            'total_items': paginator.count,
            'page_size': page_size
        }
    })


# === GESTIÓN DE PEDIDOS PARA STAFF ===

class StaffPedidosView(APIView):
    """Vista para que el staff gestione todos los pedidos."""
    permission_classes = [IsAdminUser]

    def get(self, request, format=None):
        """Obtener todos los pedidos con filtros opcionales y paginación."""
        pedidos = Pedido.objects.all().order_by('-fecha_creacion')
        
        # Aplicar filtros si se proporcionan
        estado = request.query_params.get('estado', None)
        if estado:
            pedidos = pedidos.filter(estado=estado)
            
        usuario = request.query_params.get('usuario', None)
        if usuario:
            pedidos = pedidos.filter(user__username__icontains=usuario)
            
        fecha_desde = request.query_params.get('fecha_desde', None)
        if fecha_desde:
            try:
                from datetime import datetime
                fecha = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
                pedidos = pedidos.filter(fecha_creacion__date__gte=fecha)
            except ValueError:
                pass  # Ignorar fecha mal formateada
        
        # Paginación
        from django.core.paginator import Paginator
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        
        paginator = Paginator(pedidos, page_size)
        page_obj = paginator.get_page(page)
        
        # Serializar con el contexto de la request para URLs absolutas
        from .serializers import PedidoSerializer
        serializer = PedidoSerializer(page_obj.object_list, many=True, context={'request': request})
        
        return Response({
            'results': serializer.data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'page_size': page_size
            }
        })

    def patch(self, request, pk, format=None):
        """Actualizar un pedido específico (cambiar estado, email, teléfono, etc.)."""
        try:
            pedido = Pedido.objects.get(pk=pk)
        except Pedido.DoesNotExist:
            return Response({'error': 'Pedido no encontrado'}, status=404)
        
        # Campos que se pueden actualizar
        campos_actualizables = ['estado', 'email', 'telefono', 'direccion', 'notas']
        cambios_realizados = []
        
        for campo in campos_actualizables:
            if campo in request.data:
                valor_anterior = getattr(pedido, campo, None)
                nuevo_valor = request.data[campo]
                
                # Validación específica para estado
                if campo == 'estado':
                    estados_validos = [choice[0] for choice in Pedido.ESTADO_PEDIDO]
                    if nuevo_valor not in estados_validos:
                        return Response({'error': 'Estado no válido'}, status=400)
                
                # Aplicar el cambio
                setattr(pedido, campo, nuevo_valor)
                cambios_realizados.append(f"{campo}: {valor_anterior} → {nuevo_valor}")
        
        # Guardar los cambios
        if cambios_realizados:
            pedido.save()
            
            # Log de los cambios para auditoría
            cambios_str = ', '.join(cambios_realizados)
            print(f"🔄 Staff {request.user.username} actualizó pedido {pk}: {cambios_str}")
        
        # Serializar y devolver el pedido actualizado
        from .serializers import PedidoSerializer
        serializer = PedidoSerializer(pedido, context={'request': request})
        return Response(serializer.data)


@api_view(['POST'])
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


@api_view(['GET'])
@permission_classes([IsAdminUser])
def resumen_pedidos_staff(request):
    """Obtener resumen estadístico de pedidos para el dashboard del staff."""
    try:
        resumen = {
            'total_pedidos': Pedido.objects.count(),
            'pendientes': Pedido.objects.filter(estado='PENDIENTE').count(),
            'confirmados': Pedido.objects.filter(estado='CONFIRMADO').count(),
            'en_proceso': Pedido.objects.filter(estado='EN_PROCESO').count(),
            'preparados': Pedido.objects.filter(estado='PREPARADO').count(),
            'enviados': Pedido.objects.filter(estado='ENVIADO').count(),
            'entregados': Pedido.objects.filter(estado='ENTREGADO').count(),
            'cancelados': Pedido.objects.filter(estado='CANCELADO').count(),
        }
        
        # Estadísticas adicionales
        from django.db.models import Sum, Avg
        total_ventas = Pedido.objects.aggregate(total=Sum('total'))['total'] or 0
        promedio_pedido = Pedido.objects.aggregate(promedio=Avg('total'))['promedio'] or 0
        
        resumen.update({
            'total_ventas': float(total_ventas),
            'promedio_pedido': float(promedio_pedido),
        })
        
        return Response(resumen)
        
    except Exception as e:
        print(f"❌ Error al obtener resumen de pedidos: {e}")
        return Response({'error': 'Error al obtener resumen'}, status=500)    


# === GESTIÓN DE CLIENTES PARA STAFF ===

class StaffClientesView(APIView):
    """Vista para que el staff gestione clientes."""
    permission_classes = [IsAdminUser]

    def get(self, request, pk=None, format=None):
        """Obtener clientes (lista o individual)."""
        if pk:
            return self.get_single(request, pk, format)
        else:
            return self.get_list(request, format)

    def get_list(self, request, format=None):
        """Obtener todos los clientes con paginación y filtros."""
        
        clientes = Cliente.objects.all().select_related('user', 'codigo_localidad', 'condicion_pago').order_by('-id')
        
        # Aplicar filtros si se proporcionan
        nombre = request.query_params.get('nombre', None)
        if nombre:
            clientes = clientes.filter(
                models.Q(nombre__icontains=nombre) | 
                models.Q(user__first_name__icontains=nombre) |
                models.Q(user__last_name__icontains=nombre) |
                models.Q(user__username__icontains=nombre)
            )
            
        numero_cliente = request.query_params.get('numero_cliente', None)
        if numero_cliente:
            clientes = clientes.filter(numero_cliente__icontains=numero_cliente)
            
        lista_precio = request.query_params.get('lista_precio', None)
        if lista_precio:
            clientes = clientes.filter(lista_precio=lista_precio)
            
        # Filtro específico por usuario (para filtro global)
        usuario = request.query_params.get('usuario', None)
        if usuario:
            clientes = clientes.filter(user__username=usuario)
        
        # Paginación
        from django.core.paginator import Paginator
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        paginator = Paginator(clientes, page_size)
        page_obj = paginator.get_page(page)
        
        # Serializar datos
        clientes_data = []
        for cliente in page_obj.object_list:
            clientes_data.append({
                'id': cliente.id,
                'numero_cliente': cliente.numero_cliente,
                'nombre': cliente.nombre,
                'username': cliente.user.username,
                'email': cliente.user.email,
                'first_name': cliente.user.first_name,
                'last_name': cliente.user.last_name,
                'lista_precio': cliente.lista_precio,
                'localidad': cliente.codigo_localidad.nombre if cliente.codigo_localidad else None,
                'condicion_pago': cliente.condicion_pago.nombre if cliente.condicion_pago else None,
                'tipo_responsable_iva': cliente.get_tipo_responsable_iva_display(),
                'cuit': cliente.cuit,
                'direccion': cliente.direccion,
                'is_active': cliente.user.is_active,
                'date_joined': cliente.user.date_joined.isoformat(),
                'last_login': cliente.user.last_login.isoformat() if cliente.user.last_login else None,
            })
        
        return Response({
            'results': clientes_data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'page_size': page_size
            }
        })

    def post(self, request, format=None):
        """Crear un nuevo cliente con su usuario."""
        
        try:
            with transaction.atomic():
                # Validar datos requeridos
                required_fields = ['username', 'email', 'password', 'first_name', 'last_name', 
                                 'numero_cliente', 'nombre', 'lista_precio', 'codigo_localidad', 
                                 'condicion_pago', 'tipo_responsable_iva']
                
                for field in required_fields:
                    if not request.data.get(field):
                        return Response({'error': f'El campo {field} es requerido'}, status=400)
                
                # Verificar que el username no exista
                if User.objects.filter(username=request.data['username']).exists():
                    return Response({'error': 'El nombre de usuario ya existe'}, status=400)
                
                # Verificar que el email no exista
                if User.objects.filter(email=request.data['email']).exists():
                    return Response({'error': 'El email ya está registrado'}, status=400)
                
                # Verificar que el número de cliente no exista
                if Cliente.objects.filter(numero_cliente=request.data['numero_cliente']).exists():
                    return Response({'error': 'El número de cliente ya existe'}, status=400)
                
                # Crear el usuario
                user = User.objects.create_user(
                    username=request.data['username'],
                    email=request.data['email'],
                    password=request.data['password'],
                    first_name=request.data['first_name'],
                    last_name=request.data['last_name'],
                    is_active=request.data.get('is_active', True)
                )
                
                # Obtener referencias a localidad y forma de pago
                try:
                    localidad = Localidades.objects.get(codigo=request.data['codigo_localidad'])
                except Localidades.DoesNotExist:
                    return Response({'error': 'Localidad no encontrada'}, status=400)
                
                try:
                    forma_pago = FormaPago.objects.get(id=request.data['condicion_pago'])
                except FormaPago.DoesNotExist:
                    return Response({'error': 'Forma de pago no encontrada'}, status=400)
                
                # Crear el cliente
                cliente = Cliente.objects.create(
                    user=user,
                    numero_cliente=request.data['numero_cliente'],
                    nombre=request.data['nombre'],
                    lista_precio=request.data['lista_precio'],
                    codigo_localidad=localidad,
                    condicion_pago=forma_pago,
                    tipo_responsable_iva=request.data['tipo_responsable_iva'],
                    regimen_percepcion=request.data.get('regimen_percepcion', ''),
                    cuit=request.data.get('cuit', ''),
                    direccion=request.data.get('direccion', '')
                )
                
                # Log para auditoría
                print(f"✅ Staff {request.user.username} creó cliente {cliente.numero_cliente} - {cliente.nombre}")
                
                return Response({
                    'success': True,
                    'message': f'Cliente {cliente.numero_cliente} creado exitosamente',
                    'cliente_id': cliente.id
                }, status=201)
                
        except Exception as e:
            print(f"❌ Error al crear cliente: {e}")
            return Response({'error': f'Error al crear cliente: {str(e)}'}, status=500)

    def get_object(self, pk):
        """Obtener una instancia específica de cliente."""
        try:
            return Cliente.objects.select_related('user', 'codigo_localidad', 'condicion_pago').get(pk=pk)
        except Cliente.DoesNotExist:
            return None

    def get_single(self, request, pk, format=None):
        """Obtener un cliente específico por ID."""
        cliente = self.get_object(pk)
        if not cliente:
            return Response({'error': 'Cliente no encontrado'}, status=404)
        
        # Obtener bonificaciones del cliente
        from .models import BonificacionCliente
        bonificaciones = BonificacionCliente.objects.filter(cliente=cliente).values(
            'id', 'desde_articulo', 'hasta_articulo', 'bonificacion'
        )
        
        # Serializar datos del cliente individual
        cliente_data = {
            'id': cliente.id,
            'numero_cliente': cliente.numero_cliente,
            'nombre': cliente.nombre,
            'username': cliente.user.username,
            'email': cliente.user.email,
            'first_name': cliente.user.first_name,
            'last_name': cliente.user.last_name,
            'lista_precio': cliente.lista_precio,
            'localidad': {
                'codigo': cliente.codigo_localidad.codigo,
                'nombre': cliente.codigo_localidad.nombre
            } if cliente.codigo_localidad else None,
            'condicion_pago': {
                'id': cliente.condicion_pago.id,
                'nombre': cliente.condicion_pago.nombre
            } if cliente.condicion_pago else None,
            'tipo_responsable_iva': cliente.tipo_responsable_iva,
            'tipo_responsable_iva_display': cliente.get_tipo_responsable_iva_display(),
            'regimen_percepcion': cliente.regimen_percepcion,
            'cuit': cliente.cuit,
            'direccion': cliente.direccion,
            'is_active': cliente.user.is_active,
            'date_joined': cliente.user.date_joined.isoformat(),
            'last_login': cliente.user.last_login.isoformat() if cliente.user.last_login else None,
            'bonificaciones': list(bonificaciones)  # Agregar bonificaciones
        }
        
        return Response(cliente_data)

    def put(self, request, pk, format=None):
        """Actualizar un cliente específico."""
        
        cliente = self.get_object(pk)
        if not cliente:
            return Response({'error': 'Cliente no encontrado'}, status=404)
        
        try:
            with transaction.atomic():
                # Campos que se pueden actualizar del usuario
                user = cliente.user
                user_updated = False
                
                if 'email' in request.data and request.data['email'] != user.email:
                    # Verificar que el email no esté en uso por otro usuario
                    if User.objects.filter(email=request.data['email']).exclude(pk=user.pk).exists():
                        return Response({'error': 'El email ya está registrado'}, status=400)
                    user.email = request.data['email']
                    user_updated = True
                
                if 'first_name' in request.data:
                    user.first_name = request.data['first_name']
                    user_updated = True
                
                if 'last_name' in request.data:
                    user.last_name = request.data['last_name']
                    user_updated = True
                
                if 'is_active' in request.data:
                    user.is_active = request.data['is_active']
                    user_updated = True
                
                # Cambiar contraseña si se proporciona
                if 'password' in request.data and request.data['password']:
                    user.set_password(request.data['password'])
                    user_updated = True
                
                if user_updated:
                    user.save()
                
                # Campos que se pueden actualizar del cliente
                cliente_updated = False
                cambios_cliente = []
                
                if 'numero_cliente' in request.data and request.data['numero_cliente'] != cliente.numero_cliente:
                    # Verificar que el número de cliente no esté en uso
                    if Cliente.objects.filter(numero_cliente=request.data['numero_cliente']).exclude(pk=cliente.pk).exists():
                        return Response({'error': 'El número de cliente ya existe'}, status=400)
                    cambios_cliente.append(f"numero_cliente: {cliente.numero_cliente} → {request.data['numero_cliente']}")
                    cliente.numero_cliente = request.data['numero_cliente']
                    cliente_updated = True
                
                if 'nombre' in request.data:
                    cambios_cliente.append(f"nombre: {cliente.nombre} → {request.data['nombre']}")
                    cliente.nombre = request.data['nombre']
                    cliente_updated = True
                
                if 'lista_precio' in request.data:
                    cambios_cliente.append(f"lista_precio: {cliente.lista_precio} → {request.data['lista_precio']}")
                    cliente.lista_precio = request.data['lista_precio']
                    cliente_updated = True
                
                if 'codigo_localidad' in request.data:
                    try:
                        localidad = Localidades.objects.get(codigo=request.data['codigo_localidad'])
                        cambios_cliente.append(f"localidad: {cliente.codigo_localidad.nombre if cliente.codigo_localidad else 'None'} → {localidad.nombre}")
                        cliente.codigo_localidad = localidad
                        cliente_updated = True
                    except Localidades.DoesNotExist:
                        return Response({'error': 'Localidad no encontrada'}, status=400)
                
                if 'condicion_pago' in request.data:
                    try:
                        forma_pago = FormaPago.objects.get(id=request.data['condicion_pago'])
                        cambios_cliente.append(f"condicion_pago: {cliente.condicion_pago.nombre if cliente.condicion_pago else 'None'} → {forma_pago.nombre}")
                        cliente.condicion_pago = forma_pago
                        cliente_updated = True
                    except FormaPago.DoesNotExist:
                        return Response({'error': 'Forma de pago no encontrada'}, status=400)
                
                if 'tipo_responsable_iva' in request.data:
                    cambios_cliente.append(f"tipo_responsable_iva: {cliente.tipo_responsable_iva} → {request.data['tipo_responsable_iva']}")
                    cliente.tipo_responsable_iva = request.data['tipo_responsable_iva']
                    cliente_updated = True
                
                if 'regimen_percepcion' in request.data:
                    cambios_cliente.append(f"regimen_percepcion: {cliente.regimen_percepcion} → {request.data['regimen_percepcion']}")
                    cliente.regimen_percepcion = request.data['regimen_percepcion']
                    cliente_updated = True
                
                if 'cuit' in request.data:
                    cambios_cliente.append(f"cuit: {cliente.cuit} → {request.data['cuit']}")
                    cliente.cuit = request.data['cuit']
                    cliente_updated = True
                
                if 'direccion' in request.data:
                    cambios_cliente.append(f"direccion: {cliente.direccion} → {request.data['direccion']}")
                    cliente.direccion = request.data['direccion']
                    cliente_updated = True
                
                if cliente_updated:
                    cliente.save()
                
                # Log para auditoría
                if user_updated or cliente_updated:
                    cambios_str = ', '.join(cambios_cliente) if cambios_cliente else 'datos de usuario'
                    print(f"🔄 Staff {request.user.username} actualizó cliente {cliente.numero_cliente}: {cambios_str}")
                
                return Response({
                    'success': True,
                    'message': f'Cliente {cliente.numero_cliente} actualizado exitosamente'
                })
                
        except Exception as e:
            print(f"❌ Error al actualizar cliente: {e}")
            return Response({'error': f'Error al actualizar cliente: {str(e)}'}, status=500)

    def delete(self, request, pk, format=None):
        """Eliminar (desactivar) un cliente."""
        cliente = self.get_object(pk)
        if not cliente:
            return Response({'error': 'Cliente no encontrado'}, status=404)
        
        try:
            # En lugar de eliminar, desactivamos el usuario
            cliente.user.is_active = False
            cliente.user.save()
            
            # Log para auditoría
            print(f"🗑️ Staff {request.user.username} desactivó cliente {cliente.numero_cliente} - {cliente.nombre}")
            
            return Response({
                'success': True,
                'message': f'Cliente {cliente.numero_cliente} desactivado exitosamente'
            })
            
        except Exception as e:
            print(f"❌ Error al desactivar cliente: {e}")
            return Response({'error': f'Error al desactivar cliente: {str(e)}'}, status=500)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def obtener_datos_auxiliares_cliente(request):
    """Obtener datos auxiliares para el formulario de clientes."""
    from .models import Localidades, FormaPago
    
    try:
        # Obtener localidades
        localidades = list(Localidades.objects.all().values('codigo', 'nombre').order_by('nombre'))
        
        # Obtener formas de pago
        formas_pago = list(FormaPago.objects.all().values('id', 'nombre').order_by('nombre'))
        
        # Opciones estáticas
        listas_precio = [
            {'value': '1', 'label': 'Lista 1'},
            {'value': '4', 'label': 'Lista 4'}
        ]
        
        tipos_responsable_iva = [
            {'value': 'C', 'label': 'Responsable Inscripto'},
            {'value': 'F', 'label': 'Consumidor Final'},
            {'value': 'M', 'label': 'Monotributista'},
            {'value': 'E', 'label': 'Exento'},
        ]
        
        regimenes_percepcion = [
            {'value': '', 'label': 'No alcanzado'},
            {'value': '60', 'label': 'Régimen de IIBB'},
        ]
        
        return Response({
            'localidades': localidades,
            'formas_pago': formas_pago,
            'listas_precio': listas_precio,
            'tipos_responsable_iva': tipos_responsable_iva,
            'regimenes_percepcion': regimenes_percepcion
        })
        
    except Exception as e:
        print(f"❌ Error al obtener datos auxiliares: {e}")
        return Response({'error': 'Error al obtener datos auxiliares'}, status=500)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def articulos_mas_consultados(request):
    """Obtener top 10 de artículos más consultados por precio."""
    from .models import ConsultaPrecio
    
    try:
        # Obtener filtro de usuario si está presente
        filtro_usuario = request.query_params.get('usuario')
        
        # Query base para consultas de precio
        consultas_query = ConsultaPrecio.objects.select_related('articulo', 'usuario')
        
        # Aplicar filtro de usuario si está presente
        if filtro_usuario:
            consultas_query = consultas_query.filter(usuario__username=filtro_usuario)
        
        # Agrupar por artículo y contar consultas
        articulos_consultados = consultas_query.values(
            'articulo__clave',
            'articulo__nombre'
        ).annotate(
            total_consultas=Count('id')
        ).order_by('-total_consultas')[:10]
        
        # Formatear los datos para la respuesta
        datos_respuesta = []
        for item in articulos_consultados:
            datos_respuesta.append({
                'articulo_clave': item['articulo__clave'],
                'articulo_nombre': item['articulo__nombre'],
                'total_consultas': item['total_consultas']
            })
        
        print(f"📊 Artículos más consultados: {len(datos_respuesta)} registros")
        if filtro_usuario:
            print(f"🔍 Filtrado por usuario: {filtro_usuario}")
            
        return Response(datos_respuesta)
        
    except Exception as e:
        print(f"❌ Error al obtener artículos más consultados: {e}")
        return Response({'error': 'Error al obtener consultas de precios'}, status=500)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def obtener_usuarios(request):
    """Obtener lista de usuarios para filtros con búsqueda."""
    try:
        # Obtener parámetro de búsqueda
        search = request.query_params.get('search', '').strip()
        
        # Query base para usuarios con clientes asociados
        usuarios_query = User.objects.filter(
            cliente__isnull=False
        ).select_related('cliente')
        
        # Aplicar filtro de búsqueda si existe
        if search:
            usuarios_query = usuarios_query.filter(
                models.Q(username__icontains=search) |
                models.Q(first_name__icontains=search) |
                models.Q(last_name__icontains=search) |
                models.Q(cliente__nombre__icontains=search) |
                models.Q(email__icontains=search)
            )
        
        # Limitar resultados para búsqueda interactiva
        limit = int(request.query_params.get('limit', 10))
        usuarios = usuarios_query[:limit]
        
        usuarios_lista = []
        for usuario in usuarios:
            usuario_data = {
                'id': usuario.id,
                'username': usuario.username,
                'first_name': usuario.first_name,
                'last_name': usuario.last_name,
                'email': usuario.email,
                'nombre_completo': f"{usuario.first_name} {usuario.last_name}".strip(),
            }
            
            # Agregar información del cliente si existe
            if hasattr(usuario, 'cliente') and usuario.cliente:
                usuario_data['cliente_nombre'] = usuario.cliente.nombre
                usuario_data['numero_cliente'] = usuario.cliente.numero_cliente
                
            usuarios_lista.append(usuario_data)
        
        print(f"👥 Búsqueda de usuarios: '{search}' -> {len(usuarios_lista)} resultados")
        
        return Response(usuarios_lista)
        
    except Exception as e:
        print(f"❌ Error al obtener usuarios: {e}")
        return Response({'error': 'Error al obtener lista de usuarios'}, status=500)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def obtener_carritos_clientes(request):
    """
    Obtener todos los carritos activos de los clientes desde la base de datos.
    """
    try:
        from .models import CarritoTemporal
        from .serializers import ArticuloSerializer
        from django.db.models import Sum, Count
        
        # Obtener todos los usuarios que tienen items en el carrito
        usuarios_con_carrito = User.objects.filter(
            carrito_temporal__isnull=False
        ).distinct().select_related('cliente')
        
        carritos_activos = []
        
        for usuario in usuarios_con_carrito:
            # Obtener items del carrito de este usuario
            items_carrito = CarritoTemporal.objects.filter(
                user=usuario
            ).select_related('articulo').order_by('-fecha_modificado')
            
            if items_carrito.count() == 0:
                continue
            
            # Construir lista de items
            items_lista = []
            total = 0
            peso_total = 0
            
            for item in items_carrito:
                item_data = {
                    'articulo': {
                        'clave': item.articulo.clave,
                        'nombre': item.articulo.nombre,
                        'unidad': item.articulo.unidad,
                        'peso': float(item.articulo.peso),
                        'mts2': float(item.articulo.mts2),
                        'campoa1': item.articulo.campoa1,
                        'imagen': request.build_absolute_uri(item.articulo.imagen.url) if item.articulo.imagen else None,
                    },
                    'cantidad': float(item.cantidad),
                    'precio_unitario': float(item.precio_unitario),
                    'subtotal': float(item.subtotal),
                }
                items_lista.append(item_data)
                total += float(item.subtotal)
                peso_total += item.calcular_peso()
            
            # Información del usuario/cliente
            numero_cliente = 'N/A'
            if hasattr(usuario, 'cliente') and usuario.cliente:
                numero_cliente = usuario.cliente.numero_cliente
            
            carritos_activos.append({
                'usuario': usuario.username,
                'usuario_nombre': f"{usuario.first_name} {usuario.last_name}".strip() or usuario.username,
                'numero_cliente': numero_cliente,
                'items': items_lista,
                'total': round(total, 2),
                'peso_total': round(peso_total, 3),
                'ultima_modificacion': items_carrito.first().fecha_modificado.isoformat() if items_carrito.exists() else None
            })
        
        print(f"📦 Carritos activos: {len(carritos_activos)}")
        
        return Response(carritos_activos)
        
    except Exception as e:
        print(f"❌ Error al obtener carritos: {e}")
        import traceback
        traceback.print_exc()
        return Response({'error': 'Error al obtener carritos de clientes'}, status=500)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def exports_list(request):
    """Listado de eventos de exportación para el dashboard del staff.
    Permite filtrar por usuario, tipo y rango de fechas: start_date, end_date (YYYY-MM-DD).
    """
    try:
        filtro_usuario = request.query_params.get('usuario')
        filtro_tipo = request.query_params.get('tipo')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        qs = ExportEvent.objects.select_related('usuario').all()

        if filtro_usuario:
            qs = qs.filter(usuario__username__icontains=filtro_usuario)
        if filtro_tipo:
            qs = qs.filter(tipo=filtro_tipo)
        if start_date:
            try:
                from datetime import datetime
                sd = datetime.strptime(start_date, '%Y-%m-%d')
                qs = qs.filter(fecha_hora__date__gte=sd.date())
            except ValueError:
                pass
        if end_date:
            try:
                from datetime import datetime
                ed = datetime.strptime(end_date, '%Y-%m-%d')
                qs = qs.filter(fecha_hora__date__lte=ed.date())
            except ValueError:
                pass

        # Paginación simple
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 50))
        from django.core.paginator import Paginator
        paginator = Paginator(qs.order_by('-fecha_hora'), page_size)
        page_obj = paginator.get_page(page)

        serializer = ExportEventSerializer(page_obj.object_list, many=True, context={'request': request})

        return Response({
            'results': serializer.data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            }
        })

    except Exception as e:
        print(f"❌ Error al obtener eventos de exportación: {e}")
        return Response({'error': 'Error al obtener eventos de exportación'}, status=500)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def exports_summary(request):
    """Resumen agregado: cuántas exportaciones hizo cada usuario.
    Devuelve lista de usuarios con total de exportaciones y la fecha del último export.
    Permite filtrar por usuario (username parcial) y limitar resultados.
    """
    try:
        filtro_usuario = request.query_params.get('usuario')
        limit = int(request.query_params.get('limit', 50))

        from django.db.models import Count, Max

        qs = ExportEvent.objects.select_related('usuario')

        if filtro_usuario:
            qs = qs.filter(usuario__username__icontains=filtro_usuario)

        agg = qs.values(
            'usuario__id', 'usuario__username', 'usuario__first_name', 'usuario__last_name'
        ).annotate(
            total_exports=Count('id'),
            last_export=Max('fecha_hora')
        ).order_by('-total_exports')[:limit]

        # Añadir número de cliente si existe
        usuarios_ids = [item['usuario__id'] for item in agg]
        usuarios_map = {}
        if usuarios_ids:
            users = User.objects.filter(id__in=usuarios_ids).select_related('cliente')
            for u in users:
                usuarios_map[u.id] = getattr(u, 'cliente', None)

        results = []
        for item in agg:
            uid = item['usuario__id']
            cliente = usuarios_map.get(uid)
            numero_cliente = cliente.numero_cliente if cliente else None
            nombre_cliente = cliente.nombre if cliente else None
            results.append({
                'usuario_id': uid,
                'username': item.get('usuario__username'),
                'first_name': item.get('usuario__first_name'),
                'last_name': item.get('usuario__last_name'),
                'numero_cliente': numero_cliente,
                'nombre_cliente': nombre_cliente,
                'total_exports': item.get('total_exports', 0),
                'last_export': item.get('last_export')
            })

        return Response(results)

    except Exception as e:
        print(f"❌ Error al obtener resumen de exportaciones: {e}")
        return Response({'error': 'Error al obtener resumen de exportaciones'}, status=500)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def articulos_vistas_summary(request):
    """Resumen agregado: vistas de ofertas y discontinuados por usuario."""
    try:
        filtro_usuario = request.query_params.get('usuario')
        limit = int(request.query_params.get('limit', 50))

        qs = ArticuloVista.objects.select_related('usuario', 'cliente')

        if filtro_usuario:
            qs = qs.filter(usuario__username__icontains=filtro_usuario)

        agg = qs.values(
            'usuario__id', 'usuario__username', 'usuario__first_name', 'usuario__last_name'
        ).annotate(
            ofertas=Count('id', filter=Q(tipo='oferta')),
            discontinuados=Count('id', filter=Q(tipo='discontinuado')),
            last_oferta=Max('fecha_hora', filter=Q(tipo='oferta')),
            last_discontinuado=Max('fecha_hora', filter=Q(tipo='discontinuado'))
        ).order_by('-ofertas', '-discontinuados')[:limit]

        usuarios_ids = [item['usuario__id'] for item in agg]
        usuarios_map = {}
        if usuarios_ids:
            users = User.objects.filter(id__in=usuarios_ids).select_related('cliente')
            for u in users:
                usuarios_map[u.id] = getattr(u, 'cliente', None)

        results = []
        for item in agg:
            uid = item['usuario__id']
            cliente = usuarios_map.get(uid)
            numero_cliente = cliente.numero_cliente if cliente else None
            nombre_cliente = cliente.nombre if cliente else None
            results.append({
                'usuario_id': uid,
                'username': item.get('usuario__username'),
                'first_name': item.get('usuario__first_name'),
                'last_name': item.get('usuario__last_name'),
                'numero_cliente': numero_cliente,
                'nombre_cliente': nombre_cliente,
                'total_ofertas': item.get('ofertas', 0),
                'total_discontinuados': item.get('discontinuados', 0),
                'last_oferta': item.get('last_oferta'),
                'last_discontinuado': item.get('last_discontinuado')
            })

        return Response(results)
    except Exception as e:
        print(f"❌ Error al obtener resumen de vistas de articulos: {e}")
        return Response({'error': 'Error al obtener resumen de vistas de articulos'}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sincronizar_carrito(request):
    """
    Sincronizar el carrito del cliente con el backend.
    Recibe todos los items del carrito y actualiza la base de datos.
    """
    try:
        from .models import CarritoTemporal
        
        items = request.data.get('items', [])
        
        print(f"🔄 Sincronizando carrito para {request.user.username}: {len(items)} items")
        
        # Limpiar carrito existente
        CarritoTemporal.objects.filter(user=request.user).delete()
        
        # Agregar nuevos items
        for item_data in items:
            try:
                articulo_clave = item_data.get('articulo', {}).get('clave')
                cantidad = item_data.get('cantidad', 0)
                precio_unitario = item_data.get('precio_unitario', 0)
                subtotal = item_data.get('subtotal', 0)
                
                if not articulo_clave:
                    continue
                
                articulo = Articulos.objects.get(clave=articulo_clave)
                
                CarritoTemporal.objects.create(
                    user=request.user,
                    articulo=articulo,
                    cantidad=cantidad,
                    precio_unitario=precio_unitario,
                    subtotal=subtotal
                )
                
            except Articulos.DoesNotExist:
                print(f"⚠️ Artículo {articulo_clave} no encontrado")
                continue
            except Exception as e:
                print(f"❌ Error al crear item de carrito: {e}")
                continue
        
        print(f"✅ Carrito sincronizado: {len(items)} items guardados")
        
        return Response({
            'success': True,
            'message': f'Carrito sincronizado: {len(items)} items',
            'items_guardados': len(items)
        })
        
    except Exception as e:
        print(f"❌ Error al sincronizar carrito: {e}")
        import traceback
        traceback.print_exc()
        return Response({'error': 'Error al sincronizar carrito'}, status=500)

