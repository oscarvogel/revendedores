from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from api.models import Articulos, Cliente, FormaPago, Localidades
from api.serializers import PedidoSerializer


class PedidoDecimalQuantityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='decimal', email='decimal@example.com')
        self.localidad = Localidades.objects.create(codigo='0002', nombre='Capiovi', distancia=0, reparto='S')
        self.forma = FormaPago.objects.create(id='00', nombre='Contado', descuento=0, punitorio=0)
        Cliente.objects.create(
            user=self.user, numero_cliente='126', lista_precio='1', nombre='Cliente Decimal',
            codigo_localidad=self.localidad, condicion_pago=self.forma, tipo_responsable_iva='C'
        )
        self.caja = Articulos.objects.create(
            clave='002.001', unidad='M2', nombre='Ceramico', peso=Decimal('20'), mts2=Decimal('1.500'),
            campoa1='a', pblret1=Decimal('100'), pblrep1=Decimal('100'),
            pblret4=Decimal('100'), pblrep4=Decimal('100'), ultact=date.today(),
            visible='S', descripcion='Ceramico', iva=0,
        )
        self.unidad = Articulos.objects.create(
            clave='002.002', unidad='UN', nombre='Unidad', peso=Decimal('2'),
            pblret1=Decimal('50'), pblrep1=Decimal('50'), pblret4=Decimal('50'), pblrep4=Decimal('50'),
            ultact=date.today(), visible='S', descripcion='Unidad', iva=0,
        )

    def _serializer(self, articulo, cantidad):
        request = APIRequestFactory().post('/api/pedidos/')
        request.user = self.user
        return PedidoSerializer(
            data={
                'modalidad': 'retira', 'con_impuestos': False, 'condicion_pago': '00',
                'items': [{'articulo': articulo.clave, 'cantidad': cantidad, 'precio_unitario': '1.00'}],
            },
            context={'request': request},
        )

    def test_metros_cuadrados_decimal_se_persisten_sin_perdida(self):
        serializer = self._serializer(self.caja, '3.000')
        serializer.is_valid(raise_exception=True)
        pedido = serializer.save(user=self.user)
        item = pedido.items.get()
        self.assertEqual(item.cantidad, Decimal('3.000'))
        self.assertEqual(item.subtotal, Decimal('300.00'))
        self.assertEqual(item.calcular_peso(), Decimal('40.000'))

    def test_rechaza_cantidad_que_no_es_multiplo_de_caja(self):
        serializer = self._serializer(self.caja, '2.000')
        self.assertFalse(serializer.is_valid())
        self.assertIn('items', serializer.errors)

    def test_cantidad_entera_sigue_funcionando(self):
        serializer = self._serializer(self.unidad, '2')
        serializer.is_valid(raise_exception=True)
        pedido = serializer.save(user=self.user)
        self.assertEqual(pedido.items.get().cantidad, Decimal('2.000'))
