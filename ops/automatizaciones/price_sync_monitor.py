"""Read-only price comparison primitives for the Revendedores sync monitor."""

from __future__ import annotations

import hashlib
import importlib
from contextlib import redirect_stdout
import json
import os
import re
import sys
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

PRICE_FIELDS = ("pblret1", "pblrep1", "pblret4", "pblrep4")
CENT = Decimal("0.01")
MILLI = Decimal("0.001")
ZERO = Decimal("0")
STATE_PATH = Path("/data/price_sync_monitor/state.json")
SYNC_LOCK_PATH = Path("/data/locks/actualiza_lista_reventa_cron.lock")
SYNC_LOG_DIR = Path("/data/logs/linux/actualiza_lista_reventa")
MAX_SYNC_LOG_AGE_SECONDS = 90 * 60
DEFAULT_FULL_SCAN_SECONDS = 45 * 60
DEFAULT_BATCH_SIZE = 50
LEGACY_PATH = "/var/www/html/utiles"
PERSISTENT_JOBS_PATH = "/data/jobs"


def _get(row: Any, name: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(name, default)
    return getattr(row, name, default)


def _decimal(value: Any, *, default: Decimal | None = None) -> Decimal:
    if value is None:
        if default is not None:
            return default
        raise ValueError("missing decimal value")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("invalid decimal value") from exc


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def compare_price(actual: Decimal, expected: Decimal, tolerance: Decimal) -> bool:
    """Return true only when the absolute price delta exceeds tolerance."""
    tolerance_value = abs(_decimal(tolerance))
    return abs(_decimal(actual) - _decimal(expected)) > tolerance_value


def compare_synced_article(article: Any, reference: Any) -> list[dict[str, Any]]:
    """Compare Revendedores' four persisted list/mode prices with reference values."""
    key = str(_get(article, "clave", "")).strip()
    differences: list[dict[str, Any]] = []
    for field in PRICE_FIELDS:
        actual_raw = _get(article, field)
        expected_raw = _get(reference, field)
        if actual_raw is None or expected_raw is None:
            differences.append(
                {
                    "key": f"{key}|{field}",
                    "articulo": key,
                    "campo": field,
                    "actual": None if actual_raw is None else str(actual_raw),
                    "esperado": None if expected_raw is None else str(expected_raw),
                    "motivo": "dato_faltante",
                }
            )
            continue
        actual = _decimal(actual_raw)
        expected = _decimal(expected_raw)
        if compare_price(actual, expected, CENT):
            differences.append(
                {
                    "key": f"{key}|{field}",
                    "articulo": key,
                    "campo": field,
                    "actual": str(actual),
                    "esperado": str(expected),
                    "diferencia": str(actual - expected),
                }
            )
    return differences


def calculate_portal_price(
    article: Any,
    customer: Any,
    location: Any,
    payment: Any,
    modality: str,
) -> Decimal:
    """Pure mirror of the portal's customer-facing price calculation."""
    list_code = str(_get(customer, "lista_precio", "1") or "1").strip()
    if list_code not in {"1", "4"}:
        list_code = "1"
    mode = "reparto" if modality == "reparto" else "retira"
    price_mode = "rep" if mode == "reparto" else "ret"
    base = _decimal(_get(article, f"pbl{price_mode}{list_code}"))

    additional_tax = ZERO if str(_get(article, "clave", "")).startswith("F") else _decimal(
        _get(article, "impuesto_adicional"), default=ZERO
    )
    price = (base * (Decimal("1") + additional_tax / 100)).quantize(
        MILLI, rounding=ROUND_HALF_UP
    )

    freight = ZERO
    if mode == "reparto":
        freight_type = str(_get(article, "tiporeparto", "")).strip().upper()
        weight = _decimal(_get(article, "peso"), default=ZERO)
        if freight_type == "T":
            freight = _decimal(_get(location, f"fletetn{list_code}"), default=ZERO)
            freight = freight / Decimal("1000") * weight
        elif freight_type == "P":
            freight_rate = _decimal(_get(location, f"fletep{list_code}"), default=ZERO)
            freight = price * freight_rate / 100

    bonus = _decimal(_get(customer, "bonificacion"), default=ZERO)
    if bonus:
        price *= Decimal("1") - bonus / 100

    payment_modifier = _decimal(_get(payment, "punitorio"), default=ZERO) - _decimal(
        _get(payment, "descuento"), default=ZERO
    )
    price += price * payment_modifier / 100

    if bool(_get(customer, "con_impuestos", True)):
        vat = _decimal(_get(article, "iva"), default=ZERO) / 100
        price *= Decimal("1") + vat
        freight *= Decimal("1") + vat

    return _money(price + freight)


def calculate_vfp_price(
    calculator: Any,
    article: Any,
    customer: Any,
    location: Any,
    payment: Any,
    modality: str,
    *,
    base_price: Any = None,
) -> Decimal:
    """Call the local VFP PrecioBase/PrecioPublico Python reference."""
    list_code = str(_get(customer, "lista_precio", "1") or "1").strip()
    is_delivery = modality == "reparto"
    article_key = str(_get(article, "clave", "")).strip()
    if base_price is None:
        base = calculator.PrecioBase(
            nPrecio=0.0,
            lReparto=is_delivery,
            clave=article_key,
            cLista=list_code,
        )
    else:
        base = base_price
    base = _decimal(base)
    bonus = _decimal(_get(customer, "bonificacion"), default=ZERO)
    if bonus:
        base *= Decimal("1") - bonus / 100
    if hasattr(calculator, "flete_reparto"):
        calculator.flete_reparto = ZERO
    if is_delivery and hasattr(calculator, "Reparto"):
        original_reparto = calculator.Reparto

        def reparto_decimal(*args: Any, **kwargs: Any) -> Decimal:
            result = original_reparto(*args, **kwargs)
            freight = _decimal(
                getattr(calculator, "flete_reparto", result), default=ZERO
            )
            calculator.flete_reparto = freight
            return freight

        calculator.Reparto = reparto_decimal
    result = calculator.PrecioPublico(
        nPrecio=base,
        pago=str(_get(payment, "id", _get(customer, "condicion_pago_id", ""))),
        cuotapago=_get(payment, "cuota_id", 0),
        cLista=list_code,
        lReparto=is_delivery,
        localidad=str(_get(location, "codigo", "0001")),
        tipo_reparto=str(_get(article, "tiporeparto", "")),
        peso=_decimal(_get(article, "peso"), default=ZERO),
        articulo=article_key,
    )
    return _money(_decimal(result))


def _alert_key(alert: dict[str, Any]) -> str:
    supplied = alert.get("key")
    if supplied:
        return str(supplied)
    identity = {
        field: alert.get(field)
        for field in ("articulo", "cliente", "condicion", "campo", "modalidad")
    }
    packed = json.dumps(identity, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()


def _alert_signature(alert: dict[str, Any]) -> str:
    packed = json.dumps(alert, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()


def update_alert_state(
    previous: dict[str, Any],
    current: list[dict[str, Any]],
    *,
    preserve_missing: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return active discrepancy state and newly observed/changed alerts."""
    previous_active = previous.get("active", {}) if isinstance(previous, dict) else {}
    next_active: dict[str, dict[str, Any]] = dict(previous_active) if preserve_missing else {}
    to_send: list[dict[str, Any]] = []

    for alert in current:
        if alert.get("tipo") == "price_mismatch" and isinstance(
            alert.get("case_signatures"), dict
        ):
            changed_keys: list[str] = []
            changed_kinds: list[str] = []
            case_signatures = alert["case_signatures"]
            for case_key, case_data in case_signatures.items():
                state_key = f"case:{case_key}"
                signature = str(case_data["signature"])
                old = previous_active.get(state_key, {})
                unchanged = old.get("signature") == signature
                notified = bool(old.get("notified")) if unchanged else False
                next_active[state_key] = {
                    "signature": signature,
                    "alert": {"key": case_key, "tipo": case_data["tipo"]},
                    "notified": notified,
                }
                if not unchanged or not notified:
                    changed_keys.append(case_key)
                    changed_kinds.append(str(case_data["tipo"]))
            if changed_keys:
                to_send.append(
                    {
                        **alert,
                        "cantidad": len(changed_keys),
                        "bases": sum(kind == "base_price_mismatch" for kind in changed_kinds),
                        "finales": sum(kind == "customer_price_mismatch" for kind in changed_kinds),
                        "fuentes_faltantes": sum(kind == "source_article_missing" for kind in changed_kinds),
                        "muestras": [
                            case_signatures[key]["sample"]
                            for key in changed_keys
                            if case_signatures[key].get("sample")
                        ][:5],
                        "_state_keys": [f"case:{key}" for key in changed_keys],
                    }
                )
            continue

        key = _alert_key(alert)
        signature = _alert_signature(alert)
        old = previous_active.get(key, {}) if isinstance(previous_active, dict) else {}
        unchanged = old.get("signature") == signature
        notified = bool(old.get("notified")) if unchanged else False
        next_active[key] = {"signature": signature, "alert": alert, "notified": notified}
        if not unchanged or not notified:
            to_send.append(alert)

    return {"version": 1, "active": next_active}, to_send


def mark_alert_notified(state: dict[str, Any], key: str) -> dict[str, Any]:
    """Copy state and mark one alert delivered after WhatsApp confirms it."""
    active = dict(state.get("active", {}))
    if key in active:
        active[key] = {**active[key], "notified": True}
    return {**state, "active": active}


def _is_lock_held(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        import fcntl

        with path.open("a+") as lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return True
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            return False
    except OSError:
        return True


def check_sync_status(now: float | None = None) -> dict[str, Any]:
    """Fail closed unless the latest hourly update completed cleanly and recently."""
    if _is_lock_held(SYNC_LOCK_PATH):
        return {"ok": False, "running": True, "reason": "sync_running"}

    try:
        logs = sorted(
            SYNC_LOG_DIR.glob("actualiza_lista_reventa-*.log"),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        logs = []
    if not logs:
        return {"ok": False, "running": False, "reason": "sync_log_missing"}

    latest = logs[0]
    current_time = time.time() if now is None else now
    try:
        age = max(0.0, current_time - latest.stat().st_mtime)
    except OSError:
        return {"ok": False, "running": False, "reason": "sync_log_unreadable"}
    if age > MAX_SYNC_LOG_AGE_SECONDS:
        return {"ok": False, "running": False, "reason": "sync_log_stale"}

    try:
        content = latest.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"ok": False, "running": False, "reason": "sync_log_unreadable"}
    lines = content.splitlines()
    error_lines = [line for line in lines if "ERROR:" in line or "CRITICAL:" in line]
    traceback_lines = [line for line in lines if "Traceback (most recent call last):" in line]
    operational_lines = [line for line in lines if "OperationalError" in line]
    completed_bonifications = "Actualización de bonificaciones completada" in content
    clean_summary = bool(re.search(r"Resumen: \d+ actualizados, \d+ creados, 0 errores", content))
    clean_exit = bool(re.search(r"END exit_code=0\s*$", content))
    expected_caught_connection_warning = (
        len(error_lines) == 1
        and "Error al conectar a la base de datos: Connection already opened." in error_lines[0]
        and len(traceback_lines) == 1
        and 1 <= len(operational_lines) <= 2
        and all("Connection already opened" in line for line in operational_lines)
        and completed_bonifications
        and clean_summary
        and clean_exit
    )
    if expected_caught_connection_warning:
        return {
            "ok": True,
            "running": False,
            "log_age_seconds": int(age),
            "log_mtime": latest.stat().st_mtime,
            "warning": "connection_already_opened_but_job_completed",
        }
    if error_lines or traceback_lines or operational_lines:
        error_text = " ".join(error_lines + traceback_lines + operational_lines).casefold()
        return {
            "ok": False,
            "running": False,
            "reason": "database_error" if "operationalerror" in error_text else "traceback",
            "error_class": "OperationalError" if "operationalerror" in error_text else "Traceback",
        }
    return {
        "ok": True,
        "running": False,
        "log_age_seconds": int(age),
        "log_mtime": latest.stat().st_mtime,
    }


def _cache_model_lookups(models: list[Any]) -> None:
    """Cache successful ORM get_by_id lookups for this short-lived monitor process."""
    for model in models:
        if model is None or getattr(model, "_price_monitor_lookup_cached", False):
            continue
        original = model.get_by_id
        cache: dict[Any, Any] = {}

        def cached_get_by_id(*args: Any, __original=original, __cache=cache, **kwargs: Any) -> Any:
            try:
                key = (args, tuple(sorted(kwargs.items())))
                cached = __cache.get(key)
            except TypeError:
                return __original(*args, **kwargs)
            if key not in __cache:
                cached = __original(*args, **kwargs)
                __cache[key] = cached
            return cached

        model.get_by_id = staticmethod(cached_get_by_id)
        model._price_monitor_lookup_cached = True


def _load_runtime() -> dict[str, Any]:
    """Load the legacy ERP models and the scheduler's existing WhatsApp sender."""
    jobs_path = str(Path(__file__).resolve().parent)
    for path in (LEGACY_PATH, jobs_path, PERSISTENT_JOBS_PATH):
        if path not in sys.path:
            sys.path.insert(0, path)

    original_argv = sys.argv
    original_cwd = os.getcwd()
    sys.argv = [original_argv[0] if original_argv else "price_sync_monitor.py"]
    try:
        # Legacy libs.utiles parses its own -i/-a options at import time and
        # resolves fasa.ini relative to the updater's working directory.
        os.chdir(LEGACY_PATH)
        updater = importlib.import_module("ActualizaListaReventa")
        whatsapp = importlib.import_module("resumen_dashboard_whatsapp")
        calculator_module_name = getattr(updater.Calculaprecio, "__module__", "builtins")
        if calculator_module_name != "builtins":
            calculator_module = importlib.import_module(calculator_module_name)
            stock_module = importlib.import_module(calculator_module.Stock.__module__)
            _cache_model_lookups(
                [
                    calculator_module.FormaPago,
                    calculator_module.Cuotaspago,
                    calculator_module.Localidad,
                    calculator_module.Stock,
                    stock_module.Tipoiva,
                ]
            )
        env = whatsapp.leer_env(
            os.environ.get("WA_ENV_FILE") or "/data/env/alertas-whatsapp.env"
        )
        recipients = whatsapp.destinatarios(env)
    finally:
        sys.argv = original_argv
        os.chdir(original_cwd)

    def load_data() -> dict[str, Any]:
        def rows(model: Any) -> list[Any]:
            return list(model.select().iterator())

        return {
            "articles": rows(updater.ArticulosReventa),
            "customers": rows(updater.ClienteReventa),
            "payments": {str(row.id): row for row in rows(updater.FormaPagoReventa)},
            "locations": {str(row.codigo): row for row in rows(updater.Localidades)},
            "bonifications": rows(updater.BonificacionCliente),
        }

    def send_alert(message: str, dry_run: bool) -> bool:
        if not recipients:
            return False
        delivered = True
        for recipient in recipients:
            try:
                response = whatsapp.enviar(message, recipient, env, dry_run=dry_run)
            except (Exception, SystemExit):
                delivered = False
                continue
            if not dry_run and not response.get("messageId"):
                delivered = False
        return delivered

    return {
        "load_data": load_data,
        "calculator_factory": updater.Calculaprecio,
        "send_alert": send_alert,
        "state_path": STATE_PATH,
    }


def _read_state(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as source:
            value = json.load(source)
        if isinstance(value, dict) and isinstance(value.get("active"), dict):
            return value
    except FileNotFoundError:
        pass
    except (OSError, json.JSONDecodeError):
        pass
    return {"version": 1, "active": {}}


def _write_state(path: Path, state: dict[str, Any]) -> None:
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    try:
        with handle:
            json.dump(state, handle, ensure_ascii=False, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(handle.name, path)
    finally:
        if os.path.exists(handle.name):
            os.unlink(handle.name)


def _field(article: Any, field: str) -> Decimal:
    return _decimal(_get(article, field))


def _reference_base_prices(article: Any, calculator: Any) -> dict[str, Decimal]:
    key = str(_get(article, "clave", "")).strip()
    reference: dict[str, Decimal] = {}
    with open(os.devnull, "w", encoding="utf-8") as sink, redirect_stdout(sink):
        for list_code in ("1", "4"):
            for mode in ("retira", "reparto"):
                price = calculator.PrecioBase(
                    nPrecio=0.0,
                    lReparto=(mode == "reparto"),
                    clave=key,
                    cLista=list_code,
                )
                price_mode = "rep" if mode == "reparto" else "ret"
                reference[f"pbl{price_mode}{list_code}"] = _decimal(price)
    return reference


def _bonus_for(client: Any, article: Any, bonuses: list[Any]) -> Decimal:
    client_id = _get(client, "id")
    article_key = str(_get(article, "clave", "")).strip()
    for item in bonuses:
        if _get(item, "cliente_id") != client_id:
            continue
        if str(_get(item, "desde_articulo", "")) <= article_key <= str(
            _get(item, "hasta_articulo", "")
        ):
            return _decimal(_get(item, "bonificacion"), default=ZERO)
    return ZERO


def _profile_key(client: Any, bonuses: list[Any]) -> tuple[Any, ...]:
    client_id = _get(client, "id")
    client_bonuses = tuple(
        sorted(
            (
                str(_get(item, "desde_articulo", "")),
                str(_get(item, "hasta_articulo", "")),
                str(_get(item, "bonificacion", "0")),
            )
            for item in bonuses
            if _get(item, "cliente_id") == client_id
        )
    )
    return (
        str(_get(client, "lista_precio", "1")),
        str(_get(client, "condicion_pago_id", "")),
        str(_get(client, "codigo_localidad_id", "")),
        client_bonuses,
    )


def _distinct_profiles(clients: list[Any], bonuses: list[Any]) -> list[Any]:
    unique: dict[tuple[Any, ...], Any] = {}
    for client in clients:
        unique.setdefault(_profile_key(client, bonuses), client)
    return list(unique.values())


def _canary_selection(
    articles: list[Any], clients: list[Any], rotation_bucket: int
) -> tuple[list[Any], list[Any]]:
    ordered_articles = sorted(articles, key=lambda row: str(_get(row, "clave", "")))
    ordered_clients = sorted(clients, key=lambda row: str(_get(row, "numero_cliente", "")))
    if not ordered_articles or not ordered_clients:
        return [], []

    selected_articles: dict[str, Any] = {}
    for row in ordered_articles:
        key = str(_get(row, "clave", "")).strip().lstrip(".")
        if key in {"030011", "050003", "060003"}:
            selected_articles[str(_get(row, "clave", ""))] = row
    article_width = min(8, len(ordered_articles))
    article_start = (rotation_bucket * article_width) % len(ordered_articles)
    for offset in range(article_width):
        row = ordered_articles[(article_start + offset) % len(ordered_articles)]
        selected_articles[str(_get(row, "clave", ""))] = row

    selected_clients: dict[str, Any] = {}
    for row in ordered_clients:
        if str(_get(row, "numero_cliente", "")).strip().zfill(5) == "00591" and str(
            _get(row, "condicion_pago_id", "")
        ) == "53":
            selected_clients[str(_get(row, "id"))] = row
    client_width = min(4, len(ordered_clients))
    client_start = (rotation_bucket * client_width) % len(ordered_clients)
    for offset in range(client_width):
        row = ordered_clients[(client_start + offset) % len(ordered_clients)]
        selected_clients[str(_get(row, "id"))] = row
    return list(selected_articles.values()), list(selected_clients.values())


def _aggregate_discrepancies(discrepancies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not discrepancies:
        return []
    normalized = sorted(discrepancies, key=lambda item: str(item.get("key", "")))
    digest = hashlib.sha256()
    for item in normalized:
        digest.update(_alert_signature(item).encode("ascii"))
    case_signatures = {
        _alert_key(item): {
            "signature": _alert_signature(item),
            "tipo": str(item.get("tipo", "")),
            "sample": item,
        }
        for item in normalized
    }
    return [
        {
            "key": "price_mismatch",
            "tipo": "price_mismatch",
            "cantidad": len(normalized),
            "bases": sum(item.get("tipo") == "base_price_mismatch" for item in normalized),
            "finales": sum(item.get("tipo") == "customer_price_mismatch" for item in normalized),
            "fuentes_faltantes": sum(item.get("tipo") == "source_article_missing" for item in normalized),
            "fingerprint": digest.hexdigest(),
            "case_signatures": case_signatures,
            "muestras": normalized[:5],
        }
    ]


def _scan(
    mode: str,
    runtime: dict[str, Any],
    data: dict[str, Any],
) -> dict[str, Any]:
    articles = data["articles"]
    clients = data["customers"]
    bonuses = data.get("bonifications", [])
    calculator_factory = runtime["calculator_factory"]
    is_lock_held = runtime.get("is_lock_held", _is_lock_held)
    batch_size = max(1, int(runtime.get("batch_size", DEFAULT_BATCH_SIZE)))
    if not articles:
        return {"complete": False, "reason": "no_articles", "base_fields_checked": 0, "price_cases_checked": 0, "alerts": []}
    if not clients:
        return {"complete": False, "reason": "no_customers", "base_fields_checked": 0, "price_cases_checked": 0, "alerts": []}

    if mode == "canary":
        rotation = int(runtime.get("rotation_bucket", time.time() // (2 * 60 * 60)))
        chosen_articles, chosen_clients = _canary_selection(articles, clients, rotation)
        required_client_present = any(
            str(_get(client, "numero_cliente", "")).strip().zfill(5) == "00591"
            and str(_get(client, "condicion_pago_id", "")) == "53"
            for client in chosen_clients
        )
        if not required_client_present:
            return {
                "complete": False,
                "reason": "canary_fixture_missing",
                "base_fields_checked": 0,
                "price_cases_checked": 0,
                "alerts": [],
            }
    else:
        chosen_articles = articles
        chosen_clients = []

    base_issues: list[dict[str, Any]] = []
    reference_bases: dict[str, dict[str, Decimal]] = {}
    started = time.monotonic()
    limit = float(runtime.get("max_scan_seconds", DEFAULT_FULL_SCAN_SECONDS))
    for index, article in enumerate(chosen_articles):
        if time.monotonic() - started > limit:
            return {
                "complete": False,
                "reason": "time_limit",
                "base_fields_checked": len(reference_bases) * len(PRICE_FIELDS),
                "price_cases_checked": 0,
                "alerts": _aggregate_discrepancies(base_issues),
            }
        if index and index % batch_size == 0 and is_lock_held(SYNC_LOCK_PATH):
            return {
                "complete": False,
                "reason": "sync_started",
                "base_fields_checked": len(reference_bases) * len(PRICE_FIELDS),
                "price_cases_checked": 0,
                "alerts": _aggregate_discrepancies(base_issues),
            }
        reference = _reference_base_prices(article, calculator_factory())
        article_key = str(_get(article, "clave", "")).strip()
        reference_bases[article_key] = reference
        for issue in compare_synced_article(article, reference):
            issue["tipo"] = "base_price_mismatch"
            base_issues.append(issue)

    if mode == "canary":
        profiles = chosen_clients
    else:
        profiles = _distinct_profiles(clients, bonuses)
    locations = data["locations"]
    payments = data["payments"]
    price_issues: list[dict[str, Any]] = []
    checked = 0
    missing_source_articles: set[str] = set()

    for article in chosen_articles:
        article_key = str(_get(article, "clave", "")).strip()
        if article_key in missing_source_articles:
            continue
        base_reference = reference_bases[article_key]
        article_missing = False
        for client in profiles:
            client_id = str(_get(client, "id", ""))
            location_key = str(_get(client, "codigo_localidad_id", ""))
            payment_key = str(_get(client, "condicion_pago_id", ""))
            location = locations.get(location_key)
            payment = payments.get(payment_key)
            if location is None or payment is None:
                return {
                    "complete": False,
                    "reason": "customer_reference_missing",
                    "base_fields_checked": len(reference_bases) * len(PRICE_FIELDS),
                    "price_cases_checked": checked,
                    "alerts": _aggregate_discrepancies(base_issues + price_issues),
                }
            customer = {
                "id": _get(client, "id"),
                "numero_cliente": str(_get(client, "numero_cliente", "")).strip(),
                "lista_precio": str(_get(client, "lista_precio", "1")),
                "condicion_pago_id": payment_key,
                "bonificacion": _bonus_for(client, article, bonuses),
                "con_impuestos": True,
            }
            for modality in ("retira", "reparto"):
                if checked % batch_size == 0 and is_lock_held(SYNC_LOCK_PATH):
                    return {
                        "complete": False,
                        "reason": "sync_started",
                        "base_fields_checked": len(reference_bases) * len(PRICE_FIELDS),
                        "price_cases_checked": checked,
                        "alerts": _aggregate_discrepancies(base_issues + price_issues),
                    }
                if time.monotonic() - started > limit:
                    return {
                        "complete": False,
                        "reason": "time_limit",
                        "base_fields_checked": len(reference_bases) * len(PRICE_FIELDS),
                        "price_cases_checked": checked,
                        "alerts": _aggregate_discrepancies(base_issues + price_issues),
                    }
                try:
                    portal_price = calculate_portal_price(
                        article, customer, location, payment, modality
                    )
                except Exception as exc:
                    if type(exc).__name__ == "StockDoesNotExist":
                        if article_key not in missing_source_articles:
                            missing_source_articles.add(article_key)
                            price_issues.append(
                                {
                                    "key": f"source|{article_key}",
                                    "tipo": "source_article_missing",
                                    "articulo": article_key,
                                }
                            )
                        article_missing = True
                        break
                    return {
                        "complete": False,
                        "reason": f"portal_calculation_error:{type(exc).__name__}",
                        "detail_reason": _calculation_error_detail(exc, article_key, customer, payment_key, modality),
                        "base_fields_checked": len(reference_bases) * len(PRICE_FIELDS),
                        "price_cases_checked": checked,
                        "alerts": _aggregate_discrepancies(base_issues + price_issues),
                    }
                field = (
                    f"pbl{'ret' if modality == 'retira' else 'rep'}"
                    f"{customer['lista_precio']}"
                )
                try:
                    vfp_price = calculate_vfp_price(
                        calculator_factory(),
                        article,
                        customer,
                        location,
                        payment,
                        modality,
                        base_price=base_reference[field],
                    )
                except Exception as exc:
                    if type(exc).__name__ == "StockDoesNotExist":
                        if article_key not in missing_source_articles:
                            missing_source_articles.add(article_key)
                            price_issues.append(
                                {
                                    "key": f"source|{article_key}",
                                    "tipo": "source_article_missing",
                                    "articulo": article_key,
                                }
                            )
                        article_missing = True
                        break
                    return {
                        "complete": False,
                        "reason": f"vfp_calculation_error:{type(exc).__name__}",
                        "detail_reason": _calculation_error_detail(exc, article_key, customer, payment_key, modality),
                        "base_fields_checked": len(reference_bases) * len(PRICE_FIELDS),
                        "price_cases_checked": checked,
                        "alerts": _aggregate_discrepancies(base_issues + price_issues),
                    }
                checked += 1
                if compare_price(portal_price, vfp_price, CENT):
                    customer_number = customer["numero_cliente"]
                    price_issues.append(
                        {
                            "key": f"{customer_number}|{article_key}|{modality}",
                            "tipo": "customer_price_mismatch",
                            "cliente": customer_number,
                            "condicion": payment_key,
                            "articulo": article_key,
                            "detalle": str(_get(article, "nombre", "")),
                            "modalidad": modality,
                            "portal": str(portal_price),
                            "vfp": str(vfp_price),
                            "diferencia": str(portal_price - vfp_price),
                        }
                    )
            if article_missing:
                break

    all_issues = base_issues + price_issues
    complete = not missing_source_articles
    return {
        "complete": complete,
        "reason": "source_article_missing" if missing_source_articles else "",
        "source_articles_missing": len(missing_source_articles),
        "base_fields_checked": len(reference_bases) * len(PRICE_FIELDS),
        "price_cases_checked": checked,
        "alerts": _aggregate_discrepancies(all_issues),
    }


def _calculation_error_detail(
    exc: Exception,
    article_key: str,
    customer: dict[str, Any],
    payment_key: str,
    modality: str,
) -> str:
    message = str(exc).replace("\n", " ").strip()[:160]
    return (
        f"{type(exc).__name__}: {message}; articulo={article_key}; "
        f"lista={customer['lista_precio']}; condicion={payment_key}; modalidad={modality}"
    )


def _format_alert(alert: dict[str, Any]) -> str:
    kind = alert.get("tipo")
    count = int(alert.get("cantidad", 1))
    lines = [f"Alerta de precios Revendedores: {count} diferencia(s)."]
    if kind == "price_mismatch":
        lines = [
            f"Alerta de precios Revendedores: {count} diferencia(s) "
            f"(bases: {int(alert.get('bases', 0))}; finales cliente: {int(alert.get('finales', 0))}; "
            f"fuentes faltantes: {int(alert.get('fuentes_faltantes', 0))})."
        ]
    for item in alert.get("muestras", []):
        if item.get("tipo") == "customer_price_mismatch":
            lines.append(
                "Cliente {cliente} cond. {condicion}, art. {articulo} {modalidad}: "
                "portal ${portal}; ERP ${vfp}.".format(**item)
            )
        elif item.get("campo"):
            lines.append(
                "Art. {articulo} {campo}: base ${actual}; ERP ${esperado}.".format(**item)
            )
        elif item.get("tipo") == "source_article_missing":
            lines.append(f"Artículo {item.get('articulo', '?')} no existe en Stock ERP.")
    if kind == "sync_failure":
        reason = str(alert.get("motivo", "sync_failed"))[:80]
        lines = [
            "Alerta Revendedores: falló o quedó incompleta la sincronización horaria de precios.",
            f"Motivo: {reason}.",
        ]
    elif kind == "database_error":
        lines = ["Alerta Revendedores: no se pudo leer la base después de la sincronización."]
    elif kind == "audit_incomplete":
        lines = ["Alerta Revendedores: el control de precios quedó incompleto; revisar logs del scheduler."]
    return "\n".join(lines)[:1200]


def _deliver_alert(alert: dict[str, Any], runtime: dict[str, Any], dry_run: bool) -> bool:
    sender = runtime.get("send_alert")
    if not callable(sender):
        return False
    try:
        return bool(sender(_format_alert(alert), dry_run))
    except (Exception, SystemExit):
        return False


def run_monitor(
    mode: str,
    *,
    dry_run: bool = False,
    runtime: dict[str, Any] | None = None,
    sync_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify synced price rows, compare customer prices, and send deduplicated alerts."""
    if mode not in {"canary", "full"}:
        raise ValueError("mode must be 'canary' or 'full'")
    runtime = runtime or _load_runtime()
    sync_status_supplied = sync_status is not None
    sync_status = check_sync_status() if sync_status is None else sync_status
    if sync_status.get("running"):
        return {"status": "sync_running", "complete": False, "alerts": 0}

    state_path = Path(runtime.get("state_path", STATE_PATH))
    state = _read_state(state_path)
    scan: dict[str, Any] = {
        "complete": False,
        "base_fields_checked": 0,
        "price_cases_checked": 0,
        "alerts": [],
    }
    current_alerts: list[dict[str, Any]]
    status = "ok"

    if not sync_status.get("ok"):
        status = "sync_error"
        reason = str(sync_status.get("error_class") or sync_status.get("reason") or "sync_failed")
        current_alerts = [{"key": "sync_failure", "tipo": "sync_failure", "motivo": reason}]
    else:
        current_alerts = []

    try:
        data = runtime["load_data"]()
        scan = _scan(mode, runtime, data)
        post_sync_check = runtime.get("post_sync_status")
        if callable(post_sync_check):
            post_status = post_sync_check()
        elif sync_status_supplied:
            post_status = None
        else:
            post_status = check_sync_status()
        sync_changed_during_scan = bool(
            post_status
            and sync_status.get("log_mtime") is not None
            and post_status.get("log_mtime") != sync_status.get("log_mtime")
        )
        if post_status and (
            post_status.get("running")
            or not post_status.get("ok")
            or sync_changed_during_scan
        ):
            if scan.get("reason"):
                scan["detail_reason"] = scan["reason"]
            scan["complete"] = False
            if post_status.get("running"):
                scan["reason"] = "sync_started_during_scan"
            elif sync_changed_during_scan:
                scan["reason"] = "sync_changed_during_scan"
            else:
                scan["reason"] = "sync_health_failed_during_scan"
        current_alerts.extend(scan.get("alerts", []))
        if not scan.get("complete"):
            if sync_status.get("ok"):
                status = "incomplete"
            current_alerts.append(
                {
                    "key": "audit_incomplete",
                    "tipo": "audit_incomplete",
                    "motivo": str(scan.get("reason") or "unknown"),
                }
            )
        elif sync_status.get("ok") and current_alerts:
            status = "mismatch"
    except Exception:
        if sync_status.get("ok"):
            status = "database_error"
            current_alerts = []
        current_alerts.append(
            {"key": "database_error", "tipo": "database_error", "motivo": "database_read_failed"}
        )

    next_state, to_send = update_alert_state(
        state, current_alerts, preserve_missing=(mode == "canary")
    )
    _write_state(state_path, next_state)
    notification_failures = 0
    notified = 0
    for alert in to_send:
        key = _alert_key(alert)
        if _deliver_alert(alert, runtime, dry_run):
            notified += 1
            if not dry_run:
                for state_key in alert.get("_state_keys", [key]):
                    next_state = mark_alert_notified(next_state, state_key)
                _write_state(state_path, next_state)
        else:
            notification_failures += 1

    if dry_run and to_send:
        status = "dry_run"
    complete = bool(scan.get("complete")) if sync_status.get("ok") else False
    return {
        "status": status,
        "complete": complete,
        "reason": str(scan.get("reason") or ""),
        "detail_reason": str(scan.get("detail_reason") or ""),
        "sync_reason": (
            str(sync_status.get("error_class") or sync_status.get("reason") or "")
            if not sync_status.get("ok")
            else ""
        ),
        "base_fields_checked": int(scan.get("base_fields_checked", 0)),
        "price_cases_checked": int(scan.get("price_cases_checked", 0)),
        "source_articles_missing": int(scan.get("source_articles_missing", 0)),
        "discrepancy_groups": len(scan.get("alerts", [])),
        "alerts_to_send": len(to_send),
        "notifications_sent": notified if not dry_run else 0,
        "notification_failures": notification_failures,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Audita la sincronización de precios Revendedores")
    parser.add_argument("--mode", choices=("canary", "full"), required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    result = run_monitor(args.mode, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["complete"] or result["status"] == "sync_running" else 1


if __name__ == "__main__":
    raise SystemExit(main())
