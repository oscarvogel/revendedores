import io
import json
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from api.services.erp_documents import ReceiptApplicationMismatch, download_receipt_pdf
from api.views import descargar_comprobante_pdf


class InvoiceDownloadTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = SimpleNamespace(is_authenticated=True)
        self.customer = type("Customer", (), {"numero_cliente": "00591"})()
        self.pdf = b"%PDF-1.4 synthetic"
        self.erp_response = io.BytesIO(self.pdf)
        self.erp_response.status = 200
        self.erp_response.headers = {"Content-Type": "application/pdf"}

    def _get(self, tipo="F", numero="000100000001", authenticated=True):
        request = self.factory.get(f"/api/comprobantes/{tipo}/{numero}/pdf/")
        if authenticated:
            force_authenticate(request, user=self.user)
        return descargar_comprobante_pdf(request, tipo, numero)

    @override_settings(
        EMPRESA_ID=2,
        ACCOUNTING_DB_ALIAS="default",
        ERP_DOCUMENT_RENDER_URL="https://erp.example/api/v1/documents/invoices/by-reference",
        ERP_DOCUMENT_API_TOKEN="integration-secret",
        ERP_DOCUMENT_TIMEOUT=8,
    )
    @patch("api.views.Cliente.objects.get")
    @patch("api.services.erp_documents.CuentaCorrienteCliente.objects.using")
    @patch("api.services.erp_documents.urlopen")
    def test_descarga_pdf_autenticada_con_referencia_comercial_y_headers_privados(
        self, urlopen, account_using, customer_get
    ):
        customer_get.return_value = self.customer
        account_using.return_value.filter.return_value.count.return_value = 1
        urlopen.return_value.__enter__.return_value = self.erp_response

        response = self._get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response["Cache-Control"].startswith("private, no-store"))
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response.content, self.pdf)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer integration-secret")
        self.assertNotIn(b"idmovi", request.data)
        self.assertNotIn(b"integration-secret", response.content)
        self.assertEqual(
            json.loads(request.data),
            {
                "company_id": 2,
                "customer_code": "00591",
                "document_type": "F",
                "invoice_number": "000100000001",
            },
        )
        customer_get.assert_called_once_with(user=self.user)
        account_using.assert_called_once_with("default")

    @override_settings(
        EMPRESA_ID=2,
        ERP_DOCUMENT_RENDER_URL="https://erp.example/api/v1/documents/invoices/by-reference",
        ERP_DOCUMENT_API_TOKEN="integration-secret",
        ERP_DOCUMENT_TIMEOUT=8,
    )
    @patch("api.views.Cliente.objects.get")
    @patch("api.services.erp_documents.CuentaCorrienteCliente.objects.using")
    @patch("api.services.erp_documents.urlopen")
    def test_no_consulta_erp_si_el_comprobante_no_pertenece_al_cliente(
        self, urlopen, account_using, customer_get
    ):
        customer_get.return_value = self.customer
        account_using.return_value.filter.return_value.count.return_value = 0

        response = self._get()

        self.assertEqual(response.status_code, 404)
        urlopen.assert_not_called()

    def test_requiere_jwt(self):
        request = self.factory.get("/api/comprobantes/F/000100000001/pdf/")
        response = descargar_comprobante_pdf(request, "F", "000100000001")
        self.assertEqual(response.status_code, 401)

    @override_settings(
        EMPRESA_ID=2,
        ERP_DOCUMENT_RENDER_URL="https://erp.example/api/v1/documents/invoices/by-reference",
        ERP_DOCUMENT_API_TOKEN="integration-secret",
        ERP_DOCUMENT_TIMEOUT=8,
    )
    @patch("api.views.Cliente.objects.get")
    @patch("api.services.erp_documents.CuentaCorrienteCliente.objects.using")
    @patch("api.services.erp_documents.urlopen")
    def test_erp_fiscalmente_rechazado_se_devuelve_como_error_seguro(
        self, urlopen, account_using, customer_get
    ):
        customer_get.return_value = self.customer
        account_using.return_value.filter.return_value.count.return_value = 1
        urlopen.side_effect = HTTPError("https://erp.example", 422, "invalid fiscal data", {}, None)

        response = self._get()

        self.assertEqual(response.status_code, 422)
        self.assertNotIn("invalid fiscal data", str(response.data))

    @override_settings(
        EMPRESA_ID=2,
        ERP_DOCUMENT_RENDER_URL="https://erp.example/api/v1/documents/invoices/by-reference",
        ERP_DOCUMENT_API_TOKEN="integration-secret",
        ERP_DOCUMENT_TIMEOUT=8,
    )
    @patch("api.views.Cliente.objects.get")
    @patch("api.services.erp_documents.CuentaCorrienteCliente.objects.using")
    @patch("api.services.erp_documents.urlopen")
    def test_erp_no_disponible_se_devuelve_como_503(
        self, urlopen, account_using, customer_get
    ):
        customer_get.return_value = self.customer
        account_using.return_value.filter.return_value.count.return_value = 1
        urlopen.side_effect = URLError("internal integration secret")

        response = self._get()

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("internal integration secret", str(response.data))

    @override_settings(
        EMPRESA_ID=2,
        ERP_DOCUMENT_RENDER_URL="https://erp.example/api/v1/documents/invoices/by-reference",
        ERP_DOCUMENT_API_TOKEN="integration-secret",
        ERP_DOCUMENT_TIMEOUT=8,
    )
    @patch("api.views.Cliente.objects.get")
    @patch("api.services.erp_documents.CuentaCorrienteCliente.objects.using")
    @patch("api.services.erp_documents.urlopen")
    def test_rechaza_referencias_ambiguas_sin_consultar_al_erp(
        self, urlopen, account_using, customer_get
    ):
        customer_get.return_value = self.customer
        account_using.return_value.filter.return_value.count.return_value = 2

        response = self._get()

        self.assertEqual(response.status_code, 404)
        urlopen.assert_not_called()

    @override_settings(
        EMPRESA_ID=2,
        ERP_DOCUMENT_RENDER_URL="",
        ERP_DOCUMENT_API_TOKEN="",
        ERP_DOCUMENT_TIMEOUT=8,
    )
    @patch("api.views.Cliente.objects.get")
    @patch("api.services.erp_documents.CuentaCorrienteCliente.objects.using")
    @patch("api.services.erp_documents.urlopen")
    def test_falla_con_mensaje_seguro_si_la_integracion_no_esta_configurada(
        self, urlopen, account_using, customer_get
    ):
        customer_get.return_value = self.customer
        account_using.return_value.filter.return_value.count.return_value = 1

        response = self._get()

        self.assertEqual(response.status_code, 503)
        urlopen.assert_not_called()

    @override_settings(
        EMPRESA_ID=2,
        ERP_DOCUMENT_RENDER_URL="https://erp.example/api/v1/documents/invoices/by-reference",
        ERP_DOCUMENT_API_TOKEN="integration-secret",
        ERP_DOCUMENT_TIMEOUT=8,
    )
    @patch("api.views.Cliente.objects.get")
    @patch("api.services.erp_documents.CuentaCorrienteCliente.objects.using")
    @patch("api.services.erp_documents.urlopen")
    def test_erp_404_por_cliente_o_empresa_no_expone_que_existe_el_comprobante(
        self, urlopen, account_using, customer_get
    ):
        customer_get.return_value = self.customer
        account_using.return_value.filter.return_value.count.return_value = 1
        urlopen.side_effect = HTTPError("https://erp.example", 404, "private data", {}, None)

        response = self._get()

        self.assertEqual(response.status_code, 404)
        self.assertNotIn("private data", str(response.data))

    @override_settings(EMPRESA_ID=2, ACCOUNTING_DB_ALIAS="default")
    @patch("api.views.Cliente.objects.get")
    @patch("api.models.CuentaCorrienteCliente.objects.using")
    @patch("api.models.Cobranzas.objects.using")
    @patch("api.views.download_receipt_pdf")
    def test_recibo_autenticado_envia_medios_de_pago_al_renderizador(
        self, download_pdf, payments_using, account_using, customer_get
    ):
        customer_get.return_value = self.customer
        account_using.return_value.filter.return_value.exists.return_value = True
        payment = SimpleNamespace(
            monto=1250, tipo="R", codigo="F", detalle="Transferencia",
            banco="Banco", numero="ref-1", vence=None,
        )
        payments_using.return_value.filter.return_value.order_by.return_value = [payment]
        download_pdf.return_value = self.pdf

        response = self._get(tipo="R", numero="000100000001")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("recibo-R-000100000001.pdf", response["Content-Disposition"])
        self.assertEqual(
            download_pdf.call_args.kwargs["payments"],
            [{
                "amount": "1250.00",
                "method": "R · F · Transferencia",
                "bank": "Banco",
                "reference": "ref-1",
                "due_date": None,
            }],
        )

    @override_settings(EMPRESA_ID=2, ACCOUNTING_DB_ALIAS="default")
    @patch("api.views.Cliente.objects.get")
    @patch("api.models.CuentaCorrienteCliente.objects.using")
    @patch("api.views.download_receipt_pdf")
    def test_recibo_ajeno_no_se_envia_al_renderizador(self, download_pdf, account_using, customer_get):
        customer_get.return_value = self.customer
        account_using.return_value.filter.return_value.exists.return_value = False

        response = self._get(tipo="R", numero="000100000001")

        self.assertEqual(response.status_code, 404)
        download_pdf.assert_not_called()

    @override_settings(EMPRESA_ID=2, ACCOUNTING_DB_ALIAS="default")
    @patch("api.views.Cliente.objects.get")
    @patch("api.models.CuentaCorrienteCliente.objects.using")
    @patch("api.models.Cobranzas.objects.using")
    @patch("api.views.download_receipt_pdf", side_effect=ReceiptApplicationMismatch)
    def test_recibo_inconsistente_devuelve_mensaje_de_aplicaciones(self, download_pdf, payments_using, account_using, customer_get):
        customer_get.return_value = self.customer
        account_using.return_value.filter.return_value.exists.return_value = True
        payments_using.return_value.filter.return_value.order_by.return_value = []

        response = self._get(tipo="R", numero="000100000001")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["message"], "El recibo no coincide con las facturas aplicadas.")

    @override_settings(
        ERP_DOCUMENT_RENDER_URL="https://erp.example/api/v1/documents/invoices/by-reference",
        ERP_DOCUMENT_API_TOKEN="integration-secret",
        ERP_DOCUMENT_TIMEOUT=8,
    )
    @patch("api.services.erp_documents.urlopen")
    def test_erp_422_de_recibo_se_mapea_a_inconsistencia_de_aplicaciones(self, urlopen):
        urlopen.side_effect = HTTPError("https://erp.example", 422, "private validation", {}, None)

        with self.assertRaises(ReceiptApplicationMismatch):
            download_receipt_pdf(
                company_id=2,
                customer_code="00591",
                receipt_number="000100000001",
                payments=[{"amount": "1250.00", "method": "Transferencia"}],
            )
