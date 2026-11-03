from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from api.models import Articulos, Cliente, FormaPago, Localidades, Pedido

class FlujoPedidosTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='pedido-cliente')
        self.staff = User.objects.create_user(username='ventas', is_staff=True)
        localidad = Localidades.objects.create(codigo='8899', nombre='Localidad')
        pago = FormaPago.objects.create(id='00', nombre='Contado', descuento=0, punitorio=0)
        Cliente.objects.create(user=self.user, numero_cliente='8899', nombre='Cliente', lista_precio='1', codigo_localidad=localidad, condicion_pago=pago, tipo_responsable_iva='C')
        self.articulo = Articulos.objects.create(clave='889.001', nombre='Producto', unidad='UN', peso=1, pblret1=Decimal('10'), pblrep1=Decimal('20'), pblret4=Decimal('10'), pblrep4=Decimal('20'), ultact=date.today(), visible='S', descripcion='Producto')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.payload = {'modalidad': 'reparto', 'con_impuestos': False, 'items': [{'articulo': self.articulo.clave, 'cantidad': '2', 'precio_unitario': '1'}]}

    @patch('api.services.notificaciones_pedido.enviar_notificaciones_pedido', return_value={})
    def test_checkout_pendiente_y_precio_reparto(self, _notificar):
        response = self.client.post('/api/pedidos/checkout/', self.payload, format='json', HTTP_IDEMPOTENCY_KEY='flujo-1')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['estado'], 'PENDIENTE')
        self.assertEqual(Decimal(response.data['total']), Decimal('40'))

    @patch('api.services.notificaciones_pedido.enviar_notificaciones_pedido', return_value={})
    def test_pedido_vacio_rechazado(self, _notificar):
        self.payload['items'] = []
        response = self.client.post('/api/pedidos/checkout/', self.payload, format='json', HTTP_IDEMPOTENCY_KEY='flujo-vacio')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Pedido.objects.exists())

    def test_ventas_marca_cargado_en_erp_y_cliente_lo_ve(self):
        pedido = Pedido.objects.create(user=self.user)
        self.client.force_authenticate(self.staff)
        response = self.client.patch(f'/api/staff/pedidos/{pedido.pk}/', {'estado': 'CARGADO_ERP'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.client.force_authenticate(self.user)
        response = self.client.get(f'/api/pedidos/{pedido.pk}/')
        self.assertEqual(response.data['estado'], 'CARGADO_ERP')
        self.assertEqual(response.data['estado_display'], 'Cargado en ERP')

    @patch('api.services.notificaciones_pedido.enviar_notificaciones_pedido', return_value={})
    def test_rechaza_articulo_de_otra_empresa(self, _notificar):
        self.articulo.empresa_id = 999
        self.articulo.save(update_fields=['empresa_id'])
        response = self.client.post('/api/pedidos/checkout/', self.payload, format='json', HTTP_IDEMPOTENCY_KEY='otra-empresa')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Pedido.objects.exists())

    def test_consulta_detalle_con_clave_que_contiene_punto(self):
        response = self.client.get('/api/articulos/889.001/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['clave'], '889.001')

    @patch('api.services.notificaciones_pedido.enviar_notificaciones_pedido', return_value={})
    def test_rechaza_condicion_de_otra_lista(self, _notificar):
        FormaPago.objects.create(id='04', nombre='Otra lista', lista='4', descuento=50, punitorio=0)
        self.payload['condicion_pago'] = '04'
        response = self.client.post('/api/pedidos/checkout/', self.payload, format='json', HTTP_IDEMPOTENCY_KEY='otra-lista')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Pedido.objects.exists())
