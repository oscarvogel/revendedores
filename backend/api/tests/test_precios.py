from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIRequestFactory, force_authenticate

from api.models import Articulos, BonificacionCliente, Cliente, Favorito, FormaPago, Localidades
from api.services.precios import (
    _aplicar_formula_precio,
    _precios_base_erp,
    calcular_precio_articulo,
)
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

        self.assertEqual(precio, Decimal("126.45"))

    def test_calcular_precio_reparto_matches_vfp_impuesto_discount_and_freight_order(self):
        self.cliente.lista_precio = "4"
        self.cliente.save(update_fields=["lista_precio"])
        self.localidad.fletetn4 = Decimal("11978.40")
        self.localidad.save(update_fields=["fletetn4"])
        self.articulo.pblret4 = Decimal("7967.08128")
        self.articulo.pblrep4 = Decimal("7967.08128")
        self.articulo.tiporeparto = "T"
        self.articulo.peso = Decimal("25.00")
        forma_pago = FormaPago.objects.create(
            id="53",
            nombre="14 dias neto",
            lista="4",
            descuento=Decimal("12.00"),
            punitorio=Decimal("0.00"),
        )

        with patch(
            "api.services.precios._precios_base_erp",
            return_value={
                "001.001": {
                    "bases": {"4": Decimal("7967.08128")},
                    "impuesto": Decimal("5.70"),
                }
            },
        ):
            precio = calcular_precio_articulo(
                articulo=self.articulo,
                cliente=self.cliente,
                modalidad="reparto",
                con_impuestos=True,
                forma_pago=forma_pago,
            )

        self.assertEqual(precio, Decimal("9329.25"))

    def test_calcular_precio_reparto_rebuilds_base_when_fixed_component_rows_exist(self):
        self.cliente.lista_precio = "4"
        self.cliente.save(update_fields=["lista_precio"])
        self.localidad.fletetn4 = Decimal("11978.40")
        self.localidad.save(update_fields=["fletetn4"])
        articulo = self.articulo
        articulo.clave = ".060003"
        articulo.pblret4 = Decimal("9669.57")
        articulo.pblrep4 = Decimal("9669.57")
        articulo.tiporeparto = "T"
        articulo.peso = Decimal("25.00")
        articulo.save()
        forma_pago = FormaPago.objects.create(
            id="53",
            nombre="14 dias neto",
            lista="4",
            descuento=Decimal("12.00"),
            punitorio=Decimal("0.00"),
        )

        cursor = MagicMock()
        cursor.fetchall.return_value = [
            (
                ".060003",
                Decimal("4685.000"),
                Decimal("0.000"),
                "  ",
                "  ",
                "07",
                "  ",
                "        ",
                Decimal("28.00"),
                Decimal("28.00"),
                Decimal("25.000000"),
                "01",
                Decimal("5.700"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("128.57408"),
                Decimal("128.57408"),
                Decimal("0"),
                Decimal("4685.000"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("5.00"),
            ),
            (
                ".0600031",
                Decimal("4685.000"),
                Decimal("0.000"),
                "01",
                "  ",
                "  ",
                "  ",
                "/2.000",
                Decimal("28.00"),
                Decimal("28.00"),
                Decimal("25.000000"),
                "01",
                Decimal("5.700"),
                Decimal("5.00"),
                Decimal("10.00"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("4685.000"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
            )
        ]
        erp_connection = MagicMock()
        erp_connection.vendor = "mysql"
        erp_connection.cursor.return_value.__enter__.return_value = cursor

        with (
            patch("api.services.precios.connections", {"fasa": erp_connection}),
            patch(
                "api.services.precios.cache.get_or_set",
                side_effect=lambda _key, loader, timeout: loader(),
            ),
        ):
            erp_precios = _precios_base_erp()

        self.assertEqual(
            erp_precios[".060003"]["bases"]["4"]["reparto"],
            Decimal("10111.17056"),
        )
        self.assertEqual(
            erp_precios[".060003"]["bases"]["4"]["reparto_discontinuado"],
            Decimal("7899.352") * Decimal("1.23"),
        )
        self.assertEqual(
            erp_precios[".0600031"]["bases"]["4"]["reparto"],
            Decimal("3298.24000"),
        )

        with patch("api.services.precios._precios_base_erp", return_value=erp_precios):
            precio = calcular_precio_articulo(
                articulo=articulo,
                cliente=self.cliente,
                modalidad="reparto",
                con_impuestos=True,
                forma_pago=forma_pago,
            )

        self.assertEqual(precio, Decimal("11742.40"))

    def test_aplicar_formula_precio_applies_erp_arithmetic_suffix(self):
        self.assertEqual(
            _aplicar_formula_precio(Decimal("100.00"), "/2.000"),
            Decimal("50.00"),
        )

        self.assertEqual(
            _aplicar_formula_precio(Decimal("100.00"), "*1.25"),
            Decimal("125.0000"),
        )
        self.assertIsNone(_aplicar_formula_precio(Decimal("100.00"), "/0"))

    def test_calcular_precio_articulo_rebuilds_variant_from_erp_root_and_formula(self):
        self.cliente.lista_precio = "4"
        self.cliente.save(update_fields=["lista_precio"])
        self.articulo.clave = "08001171"
        self.articulo.formula = "*4.50"
        self.articulo.pblret4 = Decimal("254268.84")
        self.articulo.pblrep4 = Decimal("254268.84")
        self.articulo.tiporeparto = ""
        self.articulo.save()
        fuente_erp = {
            "precio_pro": Decimal("100.00"),
            "precio_prod": Decimal("0.00"),
            "fporcen": "",
            "fsuma": "",
            "fmulti": "",
            "fpbulto": "",
            "formula": "",
            "incre1": Decimal("15.00"),
            "incre4": Decimal("25.00"),
            "peso": Decimal("1.00"),
            "porcentaje1": Decimal("0.00"),
            "porcentaje4": Decimal("0.00"),
            "fsum1": Decimal("0.00"),
            "fsum4": Decimal("0.00"),
            "fmulti1": Decimal("0.00"),
            "fmulti4": Decimal("0.00"),
            "fpbulto_precio": Decimal("0.00"),
            "precio_stock": Decimal("100.00"),
            "fijo_retira_costo": Decimal("0.00"),
            "fijo_retira_porcentaje": Decimal("0.00"),
            "fijo_reparto_costo": Decimal("0.00"),
            "fijo_reparto_porcentaje": Decimal("0.00"),
            "descdiscont1": Decimal("0.00"),
            "descdiscont4": Decimal("0.00"),
            "impuesto": Decimal("0.00"),
        }
        erp_precios = {
            "0800117": {
                "bases": {"4": {"retira": Decimal("125.00"), "reparto": Decimal("125.00")}},
                "impuesto": Decimal("0.00"),
                "fuente": fuente_erp,
            }
        }

        with patch("api.services.precios._precios_base_erp", return_value=erp_precios):
            precio = calcular_precio_articulo(
                articulo=self.articulo,
                cliente=self.cliente,
                modalidad="retira",
                con_impuestos=False,
            )

        self.assertEqual(precio, Decimal("562.50"))

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
        self.cliente.puede_descargar_lista = True
        self.cliente.save(update_fields=["puede_descargar_lista"])

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
