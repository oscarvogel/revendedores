from pathlib import Path


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'No se encontró bloque para {label}')
    return text.replace(old, new, 1)


# Model
path = Path('backend/api/models.py')
text = path.read_text(encoding='utf-8')
needle = "    cliente_snapshot = models.JSONField(default=dict, blank=True)\n"
if 'idempotency_key = models.CharField' not in text:
    text = replace_once(
        text,
        needle,
        needle + "    idempotency_key = models.CharField(max_length=64, null=True, blank=True, unique=True)\n",
        'Pedido.idempotency_key',
    )
path.write_text(text, encoding='utf-8')

# Serializer
path = Path('backend/api/serializers.py')
text = path.read_text(encoding='utf-8')
if "'idempotency_key'" not in text:
    text = replace_once(
        text,
        "'condicion_pago', 'cliente_snapshot', 'items']",
        "'condicion_pago', 'cliente_snapshot', 'idempotency_key', 'items']",
        'fields PedidoSerializer',
    )
    text = replace_once(
        text,
        "'usuario_nombre', 'cliente_snapshot')",
        "'usuario_nombre', 'cliente_snapshot', 'idempotency_key')",
        'read_only PedidoSerializer',
    )
path.write_text(text, encoding='utf-8')

# Views
path = Path('backend/api/views.py')
text = path.read_text(encoding='utf-8')
text = text.replace('from django.db import models\n', 'from django.db import models, transaction, IntegrityError\n', 1)
standalone_start = "@action(detail=True, methods=['post'])\ndef confirmar_pedido(self, request, pk=None):\n"
class_marker = "\n\nclass PedidoViewSet(viewsets.ModelViewSet):\n"
if standalone_start in text:
    before, rest = text.split(standalone_start, 1)
    _old, after = rest.split(class_marker, 1)
    text = before + class_marker + after

class_start = text.index('class PedidoViewSet(viewsets.ModelViewSet):')
next_class = text.index('\nclass BusquedaViewSet', class_start)
new_class = """class PedidoViewSet(viewsets.ModelViewSet):
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

"""
text = text[:class_start] + new_class + text[next_class:]
path.write_text(text, encoding='utf-8')

# URL legacy
path = Path('backend/api/urls.py')
text = path.read_text(encoding='utf-8')
text = text.replace(
    "    path('pedido-confirmado/<int:pedido_id>/', views.confirmar_pedido, name='pedido_confirmado'),\n",
    '',
)
path.write_text(text, encoding='utf-8')

# Frontend cart
path = Path('frontend/src/services/cart.js')
text = path.read_text(encoding='utf-8')
start = text.index('    async checkout(onProgress = null) {')
end = text.index('\n    },\n});', start) + len('\n    },')
replacement = """    checkoutInProgress: false,
    checkoutIdempotencyKey: null,

    async checkout(onProgress = null) {
        if (this.items.length === 0) {
            throw new Error('El carrito está vacío');
        }
        if (this.checkoutInProgress) {
            return {
                success: false,
                message: 'El pedido ya se está enviando. Esperá un momento.',
                pedido: null,
            };
        }

        this.checkoutInProgress = true;
        if (!this.checkoutIdempotencyKey) {
            this.checkoutIdempotencyKey = globalThis.crypto?.randomUUID?.()
                || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        }

        try {
            if (onProgress) onProgress('Enviando pedido...');
            const modalidad = localStorage.getItem('articulos_modalidad') || 'retira';
            const savedImpuestos = localStorage.getItem('articulos_con_impuestos');
            const con_impuestos = savedImpuestos === null ? true : savedImpuestos === 'true';
            const condicion_pago = localStorage.getItem('condicion_pago');
            const pedidoData = {
                modalidad,
                con_impuestos,
                ...(condicion_pago ? { condicion_pago } : {}),
                items: this.items.map(item => ({
                    articulo: item.articulo.clave,
                    cantidad: item.cantidad,
                    precio_unitario: parseFloat(item.precio_unitario.toFixed(2)),
                })),
            };

            const response = await api.post('/api/pedidos/checkout/', pedidoData, {
                headers: { 'Idempotency-Key': this.checkoutIdempotencyKey },
            });
            const pedido = response.data;
            this.items = [];
            saveCartToStorage(this.items);
            this.checkoutIdempotencyKey = null;

            return {
                success: true,
                message: pedido.idempotent_replay
                    ? 'El pedido ya había sido enviado y fue recuperado correctamente.'
                    : 'Pedido enviado correctamente.',
                pedido,
            };
        } catch (error) {
            const errorMessage = error.response?.data?.error
                || error.response?.data?.detail
                || error.message
                || 'No se pudo procesar tu pedido. Intenta de nuevo.';
            return {
                success: false,
                message: errorMessage,
                pedido: null,
                error,
            };
        } finally {
            this.checkoutInProgress = false;
        }
    },"""
text = text[:start] + replacement + text[end:]
path.write_text(text, encoding='utf-8')

# Migration
Path('backend/api/migrations/0029_pedido_idempotency_key.py').write_text(
    """from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('api', '0028_alter_pedidoitem_cantidad_decimal')]

    operations = [
        migrations.AddField(
            model_name='pedido',
            name='idempotency_key',
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
    ]
""",
    encoding='utf-8',
)

# Tests
Path('backend/api/tests/test_checkout_idempotency.py').write_text(
    """from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import Articulos, Cliente, FormaPago, Localidades, Pedido


class CheckoutIdempotencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='checkout', password='test')
        localidad = Localidades.objects.create(codigo='0003', nombre='Garuhape', distancia=0, reparto='S')
        forma = FormaPago.objects.create(id='00', nombre='Contado', descuento=0, punitorio=0)
        Cliente.objects.create(
            user=self.user,
            numero_cliente='127',
            lista_precio='1',
            nombre='Cliente Checkout',
            codigo_localidad=localidad,
            condicion_pago=forma,
            tipo_responsable_iva='C',
        )
        self.articulo = Articulos.objects.create(
            clave='003.001', unidad='UN', nombre='Articulo checkout', peso=1,
            pblret1=Decimal('25'), pblrep1=Decimal('25'),
            pblret4=Decimal('25'), pblrep4=Decimal('25'),
            ultact=date.today(), visible='S', descripcion='Test', iva=0,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.payload = {
            'modalidad': 'retira',
            'con_impuestos': False,
            'condicion_pago': '00',
            'items': [{
                'articulo': self.articulo.clave,
                'cantidad': '2',
                'precio_unitario': '1.00',
            }],
        }

    @patch('api.views.threading.Thread')
    def test_repetir_misma_clave_devuelve_mismo_pedido(self, _thread):
        first = self.client.post(
            '/api/pedidos/checkout/', self.payload, format='json',
            HTTP_IDEMPOTENCY_KEY='pedido-abc',
        )
        second = self.client.post(
            '/api/pedidos/checkout/', self.payload, format='json',
            HTTP_IDEMPOTENCY_KEY='pedido-abc',
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertTrue(second.data['idempotent_replay'])
        self.assertEqual(Pedido.objects.count(), 1)

    @patch('api.views.threading.Thread')
    def test_claves_distintas_generan_pedidos_distintos(self, _thread):
        self.client.post(
            '/api/pedidos/checkout/', self.payload, format='json',
            HTTP_IDEMPOTENCY_KEY='pedido-1',
        )
        self.client.post(
            '/api/pedidos/checkout/', self.payload, format='json',
            HTTP_IDEMPOTENCY_KEY='pedido-2',
        )
        self.assertEqual(Pedido.objects.count(), 2)

    def test_sin_clave_idempotencia_es_rechazado(self):
        response = self.client.post('/api/pedidos/checkout/', self.payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Pedido.objects.count(), 0)

    def test_post_legacy_de_pedidos_esta_desactivado(self):
        response = self.client.post('/api/pedidos/', self.payload, format='json')
        self.assertEqual(response.status_code, 405)
        self.assertEqual(Pedido.objects.count(), 0)

    @patch('api.models.PedidoItem.save', side_effect=RuntimeError('fallo controlado'))
    def test_fallo_en_item_hace_rollback_completo(self, _save):
        self.client.raise_request_exception = True
        with self.assertRaises(RuntimeError):
            self.client.post(
                '/api/pedidos/checkout/', self.payload, format='json',
                HTTP_IDEMPOTENCY_KEY='rollback',
            )
        self.assertEqual(Pedido.objects.count(), 0)
""",
    encoding='utf-8',
)
