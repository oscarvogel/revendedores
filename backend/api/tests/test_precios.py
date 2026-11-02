from decimal import Decimal

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIRequestFactory, force_authenticate

from api.models import Articulos, BonificacionCliente, Cliente, Favorito, FormaPago, Localidades
from api.services.precios import calcular_precio_articulo
from api.views import consultar_precio, exportar_favoritos


class PrecioServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cliente", password="test")
        self.forma_pago = FormaPago.objects.create(
            id="00",
            nombre="Contado",
            lista="1",
            descuento=Decimal("10.00"),
            punitorio=Decimal("0.00"),
        )
        self.localidad = Localidades.objects.create(
            codigo="0001",
            nombre="Posadas",
            fletep1=Decimal("5.00"),
            fletetn1=Decimal("1000.00"),
            fletep4=Decimal("8.00"),
            fletetn4=Decimal("1500.00"),
        )
        self.cliente = Cliente.objects.create(
            user=self.user,
            numero_cliente="00001",
            lista_precio="1",
            nombre="Cliente Test",
            codigo_localidad=self.localidad,
            condicion_pago=self.forma_pago,
            tipo_responsable_iva="C",
        )
        self.articulo = Articulos.objects.create(
            clave="001.001",
            unidad="UN",
            nombre="Articulo Test",
            peso=Decimal("10.00"),
            espesor=Decimal("0.00"),
            iva=Decimal("21.00"),
            mts2=Decimal("0.00"),
            precio1=Decimal("100.00"),
            precio4=Decimal("120.00"),
            reparto="",
            redferre="",
            tiporeparto="P",
            campoa1="",
            reducida="",
            preciopub=Decimal("0.00"),
            recargo=Decimal("0.00"),
            estado="",
            pblret1=Decimal("100.00"),
            pblrep1=Decimal("110.00"),
            pblret4=Decimal("130.00"),
            pblrep4=Decimal("140.00"),
            ultact="2026-05-21",
            visible="S",
            grupo="001",
            stock=Decimal("5.00"),
            formula="",
            descripcion="Articulo de prueba",
            discontinuado="",
            oferta="",
            empresa_id=1,
        )

    def test_calcular_precio_articulo_uses_existing_business_rules(self):
        precio = calcular_precio_articulo(
            articulo=self.articulo,
            cliente=self.cliente,
            modalidad="reparto",
            con_impuestos=True,
            condicion_pago_id="00",
        )

        self.assertEqual(precio, Decimal("125.78"))

    def test_consultar_precio_endpoint_keeps_existing_response_shape(self):
        request = APIRequestFactory().post(
            "/api/consultar-precio/",
            {
                "articulo_clave": self.articulo.clave,
                "modalidad": "retira",
                "con_impuestos": True,
                "condicion_pago": "00",
            },
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = consultar_precio(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["articulo"]["clave"], self.articulo.clave)
        self.assertEqual(response.data["articulo"]["precio_lista"], Decimal("108.90"))

    def test_exportar_favoritos_does_not_query_per_favorite(self):
        BonificacionCliente.objects.create(
            cliente=self.cliente,
            desde_articulo="001.000",
            hasta_articulo="001.999",
            bonificacion=Decimal("5.00"),
        )
        favoritos = [
            Favorito(user=self.user, articulo=self.articulo),
        ]

        for idx in range(2, 32):
            articulo = Articulos.objects.create(
                clave=f"001.{idx:03d}",
                unidad="UN",
                nombre=f"Articulo Test {idx}",
                peso=Decimal("10.00"),
                espesor=Decimal("0.00"),
                iva=Decimal("21.00"),
                mts2=Decimal("0.00"),
                precio1=Decimal("100.00"),
                precio4=Decimal("120.00"),
                reparto="",
                redferre="",
                tiporeparto="P",
                campoa1="",
                reducida="",
                preciopub=Decimal("0.00"),
                recargo=Decimal("0.00"),
                estado="",
                pblret1=Decimal("100.00"),
                pblrep1=Decimal("110.00"),
                pblret4=Decimal("130.00"),
                pblrep4=Decimal("140.00"),
                ultact="2026-05-21",
                visible="S",
                grupo="001",
                stock=Decimal("5.00"),
                formula="",
                descripcion="Articulo de prueba",
                discontinuado="",
                oferta="",
                empresa_id=1,
            )
            favoritos.append(Favorito(user=self.user, articulo=articulo))

        Favorito.objects.bulk_create(favoritos)

        request = APIRequestFactory().get(
            "/api/exportar-favoritos/",
            {
                "modalidad": "reparto",
                "con_impuestos": "true",
                "condicion_pago": "00",
            },
        )
        force_authenticate(request, user=self.user)

        with CaptureQueriesContext(connection) as captured_queries:
            response = exportar_favoritos(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["total_articulos"], 31)
        self.assertLessEqual(len(captured_queries), 6)
