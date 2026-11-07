import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import DatabaseError

from api.models import CuentaCorrienteCliente


SUPPORTED_DOCUMENT_TYPES = frozenset({"F", "C", "D"})
MAX_PDF_BYTES = 20 * 1024 * 1024


class InvoiceNotFound(Exception):
    pass


class InvoiceFiscalError(Exception):
    pass


class InvoiceServiceUnavailable(Exception):
    pass


class ReceiptApplicationMismatch(Exception):
    pass


def download_invoice_pdf(*, company_id, customer_code, document_type, invoice_number):
    """Validate the portal account row and request canonical ERP rendering."""
    document_type = str(document_type or "").strip().upper()
    invoice_number = str(invoice_number or "").strip()
    if document_type not in SUPPORTED_DOCUMENT_TYPES:
        raise InvoiceNotFound
    if not re.fullmatch(r"\d{12}", invoice_number):
        raise InvoiceNotFound

    try:
        matches = (
            CuentaCorrienteCliente.objects.using(settings.ACCOUNTING_DB_ALIAS)
            .filter(
                cliente=customer_code,
                codigo=document_type,
                numero=invoice_number,
            )
            .count()
        )
    except DatabaseError as error:
        raise InvoiceServiceUnavailable from error
    if matches != 1:
        raise InvoiceNotFound

    endpoint = str(getattr(settings, "ERP_DOCUMENT_RENDER_URL", "") or "").strip()
    token = str(getattr(settings, "ERP_DOCUMENT_API_TOKEN", "") or "")
    timeout = int(getattr(settings, "ERP_DOCUMENT_TIMEOUT", 15))
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not token or not 1 <= timeout <= 60:
        raise InvoiceServiceUnavailable

    payload = json.dumps(
        {
            "company_id": int(company_id),
            "customer_code": str(customer_code),
            "document_type": document_type,
            "invoice_number": invoice_number,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    request = Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/pdf",
            "Cache-Control": "no-store",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            if getattr(response, "status", 200) != 200:
                raise InvoiceServiceUnavailable
            content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
            if content_type != "application/pdf":
                raise InvoiceServiceUnavailable
            content = response.read(MAX_PDF_BYTES + 1)
    except HTTPError as error:
        if error.code in {403, 404}:
            raise InvoiceNotFound from error
        if error.code == 422:
            raise InvoiceFiscalError from error
        raise InvoiceServiceUnavailable from error
    except (URLError, TimeoutError, OSError) as error:
        raise InvoiceServiceUnavailable from error

    if len(content) > MAX_PDF_BYTES or not content.startswith(b"%PDF-"):
        raise InvoiceServiceUnavailable
    return content


def download_receipt_pdf(*, company_id, customer_code, receipt_number, payments):
    """Send portal payment rows to the ERP renderer for a centrally resolved receipt."""
    if not re.fullmatch(r"\d{5}", str(customer_code or "")) or not re.fullmatch(r"\d{12}", str(receipt_number or "")):
        raise InvoiceNotFound
    endpoint = str(getattr(settings, "ERP_DOCUMENT_RENDER_URL", "") or "").strip()
    suffix = "/invoices/by-reference"
    if not endpoint.endswith(suffix):
        raise InvoiceServiceUnavailable
    endpoint = endpoint[:-len(suffix)] + "/receipts/by-reference"
    token = str(getattr(settings, "ERP_DOCUMENT_API_TOKEN", "") or "")
    timeout = int(getattr(settings, "ERP_DOCUMENT_TIMEOUT", 15))
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not token or not 1 <= timeout <= 60:
        raise InvoiceServiceUnavailable

    payload = json.dumps({
        "company_id": int(company_id),
        "customer_code": customer_code,
        "receipt_number": receipt_number,
        "payments": payments,
    }, separators=(",", ":")).encode("utf-8")
    request = Request(endpoint, data=payload, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/pdf",
        "Cache-Control": "no-store",
    }, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            if getattr(response, "status", 200) != 200:
                raise InvoiceServiceUnavailable
            content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
            if content_type != "application/pdf":
                raise InvoiceServiceUnavailable
            content = response.read(MAX_PDF_BYTES + 1)
    except HTTPError as error:
        if error.code in {403, 404}:
            raise InvoiceNotFound from error
        if error.code == 422:
            raise ReceiptApplicationMismatch from error
        raise InvoiceServiceUnavailable from error
    except (URLError, TimeoutError, OSError) as error:
        raise InvoiceServiceUnavailable from error
    if len(content) > MAX_PDF_BYTES or not content.startswith(b"%PDF-"):
        raise InvoiceServiceUnavailable
    return content
