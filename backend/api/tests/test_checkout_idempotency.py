from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import Articulos, Cliente, FormaPago, Localidades, Pedido


# El checkout debe ser seguro ante doble envío y reintentos con la misma clave.
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
