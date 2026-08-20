from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenRefreshView
from decimal import Decimal, ROUND_HALF_UP
from rest_framework.response import Response
from rest_framework import status

# app/serializers/base_serializers.py

from rest_framework import serializers
from django.db.models import Count

from .models import Articulos, BonificacionCliente, Cliente, FormaPago, Favorito, Busqueda, Pedido, PedidoItem, ExportEvent
from .constants import CLAVE_LEN_THRESHOLD
from .services.cantidades import validar_cantidad_articulo
from django.conf import settings

class PedidoItemSerializer(serializers.ModelSerializer):
    articulo_detalle = serializers.SerializerMethodField()
    
    class Meta:
        model = PedidoItem
        fields = ['id', 'articulo', 'articulo_detalle', 'cantidad', 'precio_unitario', 'subtotal']
        read_only_fields = ('subtotal',)
    
    def validate(self, attrs):
        articulo = attrs.get('articulo')
        cantidad = attrs.get('cantidad')
        if articulo is not None and cantidad is not None:
            try:
                attrs['cantidad'] = validar_cantidad_articulo(articulo, cantidad)
            except serializers.ValidationError as exc:
                raise serializers.ValidationError({'cantidad': exc.detail}) from exc
        return attrs

    def get_articulo_detalle(self, obj):
        """Devuelve información detallada del artículo."""
        return {
            'clave': obj.articulo.clave,
            'nombre': obj.articulo.nombre,
            'imagen': self.get_imagen_url(obj.articulo),
            'unidad': obj.articulo.unidad,
        }
    
    def get_imagen_url(self, articulo):
        """Devuelve la URL completa de la imagen del artículo."""
        if not articulo.imagen:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(articulo.imagen.url)
        return articulo.imagen.url

class PedidoSerializer(serializers.ModelSerializer):
    items = PedidoItemSerializer(many=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    usuario_nombre = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Pedido
        fields = ['id', 'user', 'usuario_nombre', 'fecha_creacion', 'estado', 'estado_display', 'total', 'modalidad', 'con_impuestos', 'condicion_pago', 'cliente_snapshot', 'idempotency_key', 'email_cliente_estado', 'email_cliente_intentos', 'email_cliente_enviado_at', 'email_cliente_ultimo_error', 'email_ventas_estado', 'email_ventas_intentos', 'email_ventas_enviado_at', 'email_ventas_ultimo_error', 'items']
        read_only_fields = ('user', 'fecha_creacion', 'total', 'estado_display', 'usuario_nombre', 'cliente_snapshot', 'idempotency_key', 'email_cliente_estado', 'email_cliente_intentos', 'email_cliente_enviado_at', 'email_cliente_ultimo_error', 'email_ventas_estado', 'email_ventas_intentos', 'email_ventas_enviado_at', 'email_ventas_ultimo_error')

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        user = validated_data.get('user')

        try:
            cliente = user.cliente
        except (AttributeError, Cliente.DoesNotExist) as exc:
            raise serializers.ValidationError(
                {'detail': 'El usuario no tiene un cliente asociado.'}
            ) from exc

        condicion_pago = validated_data.get('condicion_pago') or cliente.condicion_pago
        validated_data['condicion_pago'] = condicion_pago
        validated_data['cliente_snapshot'] = {
            'numero_cliente': cliente.numero_cliente,
            'nombre': cliente.nombre,
            'email': user.email,
            'localidad': cliente.codigo_localidad.nombre if cliente.codigo_localidad_id else '',
            'direccion': cliente.direccion,
            'cuit': cliente.cuit or '',
            'lista_precio': cliente.lista_precio,
            'condicion_pago_id': condicion_pago.id if condicion_pago else '',
            'condicion_pago_nombre': condicion_pago.nombre if condicion_pago else '',
        }

        pedido = Pedido.objects.create(**validated_data)
        total_pedido = 0

        for item_data in items_data:
            # Redondear precio_unitario a 2 decimales
            precio = item_data['precio_unitario']
            if isinstance(precio, float):
                precio = Decimal(str(precio)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            else:
                precio = precio.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            item_data['precio_unitario'] = precio

            item = PedidoItem.objects.create(pedido=pedido, **item_data)
            total_pedido += item.subtotal

        pedido.total = total_pedido
        pedido.save()
        return pedido


class BusquedaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Busqueda
        fields = ['id', 'user', 'query', 'timestamp']
        read_only_fields = ('user', 'timestamp',)


class ExportEventSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source='usuario.username', read_only=True)

    class Meta:
        model = ExportEvent
        fields = ['id', 'usuario', 'usuario_nombre', 'tipo', 'parametros', 'total_items', 'ip_address', 'user_agent', 'fecha_hora']
        read_only_fields = ('usuario', 'fecha_hora')

# New serializer for aggregated search terms
class BusquedaCountSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=255)
    count = serializers.IntegerField()

class FavoritoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorito
        fields = ['id', 'user', 'articulo', 'fecha_creacion']
        read_only_fields = ('user', 'fecha_creacion')


class BaseSerializer(serializers.ModelSerializer):
    """
    Serializer base común para todos los modelos.
    Puedes agregar comportamientos globales aquí.
    """
    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)
    

class CookieTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')

        if not refresh_token:
            return Response(
                {'detail': 'Refresh token not found in cookies.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        request.data['refresh'] = refresh_token
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            access_token = response.data['access']
            response.set_cookie(
                key='access_token',
                value=access_token,
                httponly=True,
                secure=False,
                samesite='Lax',
                path='/',
                max_age=60 * 15
            )
        return response
        

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
        request = self.context['request']
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')

        user_agent = request.META.get('HTTP_USER_AGENT', '')
        cliente = None
        try:
            cliente = user.cliente
        except:
            cliente = None

        from .models import RegistroSesion
        sesion = RegistroSesion.objects.create(
            usuario=user,
            cliente=cliente,
            ip_address=ip,
            user_agent=user_agent
        )

        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
        }
        data['session_id'] = sesion.id
        return data

class ArticuloSerializer(BaseSerializer):
    precio_lista = serializers.SerializerMethodField()
    mostrar_precio = serializers.SerializerMethodField()
    imagen = serializers.SerializerMethodField()

    class Meta:
        model = Articulos
        fields = '__all__'

    def get_imagen(self, obj):
        request = self.context.get('request')
        if obj.imagen:
            return request.build_absolute_uri(obj.imagen.url) if request else obj.imagen.url
        clave = obj.clave
        if len(clave) > CLAVE_LEN_THRESHOLD:
            clave_padre = clave[:CLAVE_LEN_THRESHOLD]
            try:
                articulo_padre = Articulos.objects.get(clave=clave_padre, empresa_id=settings.EMPRESA_ID)
                if articulo_padre.imagen:
                    return request.build_absolute_uri(articulo_padre.imagen.url) if request else articulo_padre.imagen.url
            except Articulos.DoesNotExist:
                pass
        if len(clave) > 4:
            clave_base = clave[:-1]
            try:
                articulo_padre = Articulos.objects.filter(
                    empresa_id=settings.EMPRESA_ID,
                    clave__startswith=clave_base[:CLAVE_LEN_THRESHOLD] if len(clave_base) > CLAVE_LEN_THRESHOLD else clave_base,
                    imagen__isnull=False
                ).exclude(imagen='').first()
                if articulo_padre and articulo_padre.imagen:
                    return request.build_absolute_uri(articulo_padre.imagen.url) if request else articulo_padre.imagen.url
            except Exception:
                pass
        return None
    
    def get_mostrar_precio(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        return Favorito.objects.filter(user=request.user, articulo=obj).exists()
        
    def get_precio_lista(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        if not self.get_mostrar_precio(obj):
            return None
        flete = 0
        try:
            cliente = request.user.cliente
            lista_precio = cliente.lista_precio
            modalidad = self.context.get('modalidad', 'retira')
            con_impuestos = self.context.get('con_impuestos', True)
            if lista_precio == '1':
                precio_base = obj.pblret1 if modalidad == 'retira' else obj.pblrep1
            elif lista_precio == '4':
                precio_base = obj.pblret4 if modalidad == 'retira' else obj.pblrep4
            else:
                precio_base = obj.pblret1
            precio_final = precio_base
            if modalidad == 'reparto':
                if obj.tiporeparto == 'T':
                    flete = cliente.codigo_localidad.fletetn1 if cliente.lista_precio == '1' else cliente.codigo_localidad.fletetn4
                    flete = flete / 1000 * obj.peso if flete else 0
                elif obj.tiporeparto == 'P':
                    flete = cliente.codigo_localidad.fletep1 if cliente.lista_precio == '1' else cliente.codigo_localidad.fletep4
                    flete = precio_final * flete / 100
            forma_pago_id = self.context.get('condicion_pago') or '00'
            forma_pago = FormaPago.objects.get(id=forma_pago_id)
            bonificacion = BonificacionCliente.objects.filter(cliente=cliente, desde_articulo__lte=obj.clave, hasta_articulo__gte=obj.clave).first()
            if bonificacion:
                precio_final *= (1 - bonificacion.bonificacion / 100)
            if forma_pago.descuento > 0:
                precio_final *= (1 - forma_pago.descuento / 100)
            if forma_pago.punitorio > 0:
                precio_final *= (1 + forma_pago.punitorio / 100)
            precio_final += flete if flete else 0
            if con_impuestos:
                precio_final *= (1 + obj.iva / 100)
            return round(precio_final, 2)
        except (Cliente.DoesNotExist, FormaPago.DoesNotExist):
            if request.user.is_staff:
                return obj.pblret1
            return None

class ArticuloStaffSerializer(serializers.ModelSerializer):
    favoritos_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Articulos
        fields = '__all__'

class FormaPagoSerializer(serializers.ModelSerializer):
    class Meta:
        model = FormaPago
        fields = ['id', 'nombre', 'lista', 'punitorio', 'descuento']
