from decimal import Decimal
import os
import sys
from types import SimpleNamespace
from unittest.mock import Mock
import importlib

import pytest

from ops.automatizaciones.price_sync_monitor import (
    calculate_portal_price,
    calculate_vfp_price,
    check_sync_status,
    compare_price,
    compare_synced_article,
    _aggregate_discrepancies,
    _cache_model_lookups,
    _load_runtime,
    mark_alert_notified,
    run_monitor,
    update_alert_state,
)


FIELDS = ("pblret1", "pblrep1", "pblret4", "pblrep4")


def test_cache_model_lookups_queries_each_model_key_once():
    class Model:
        calls = []

        @classmethod
        def get_by_id(cls, key):
            cls.calls.append(key)
            return {"key": key}

    _cache_model_lookups([Model])

    assert Model.get_by_id("53") == {"key": "53"}
    assert Model.get_by_id("53") == {"key": "53"}
    assert Model.get_by_id("54") == {"key": "54"}
    assert Model.calls == ["53", "54"]


def test_compare_price_uses_decimal_tolerance_boundary():
    assert compare_price(Decimal("100.00"), Decimal("100.00"), Decimal("0.01")) is False
    assert compare_price(Decimal("100.01"), Decimal("100.00"), Decimal("0.01")) is False
    assert compare_price(Decimal("100.02"), Decimal("100.00"), Decimal("0.01")) is True


def test_load_runtime_uses_persistent_whatsapp_module_and_default_env(monkeypatch, tmp_path):
    updater = SimpleNamespace(Calculaprecio=object)
    whatsapp = SimpleNamespace(
        leer_env=Mock(return_value={"configured": "yes"}),
        destinatarios=Mock(return_value=["5491100000000"]),
        enviar=Mock(return_value={"dryRun": True}),
    )
    loaded = {"ActualizaListaReventa": updater, "resumen_dashboard_whatsapp": whatsapp}
    observed_imports = {}

    def fake_import(name):
        observed_imports[name] = (sys.argv[:], os.getcwd())
        return loaded[name]

    monkeypatch.setattr(importlib, "import_module", fake_import)
    monkeypatch.setattr("ops.automatizaciones.price_sync_monitor.LEGACY_PATH", str(tmp_path))
    monkeypatch.setattr("ops.automatizaciones.price_sync_monitor.PERSISTENT_JOBS_PATH", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["price_sync_monitor.py", "--mode", "canary", "--dry-run"])
    monkeypatch.delenv("WA_ENV_FILE", raising=False)

    runtime = _load_runtime()

    whatsapp.leer_env.assert_called_once_with("/data/env/alertas-whatsapp.env")
    whatsapp.destinatarios.assert_called_once_with({"configured": "yes"})
    assert callable(runtime["send_alert"])
    assert observed_imports["ActualizaListaReventa"] == (["price_sync_monitor.py"], str(tmp_path))
    assert sys.argv == ["price_sync_monitor.py", "--mode", "canary", "--dry-run"]
    assert os.getcwd() == str(tmp_path)


@pytest.mark.parametrize("field", FIELDS)
def test_compare_synced_article_checks_each_persisted_mode(field):
    article = {"clave": "005.003", **{name: Decimal("100.00") for name in FIELDS}}
    reference = {name: Decimal("100.00") for name in FIELDS}
    reference[field] = Decimal("101.00")

    differences = compare_synced_article(article, reference)

    assert len(differences) == 1
    assert differences[0]["campo"] == field
    assert differences[0]["articulo"] == "005.003"


def test_compare_synced_article_preserves_legitimate_zero_prices():
    article = {"clave": "005.003", **{name: Decimal("0.00") for name in FIELDS}}
    reference = {name: Decimal("0.00") for name in FIELDS}

    assert compare_synced_article(article, reference) == []


def test_calculate_portal_price_applies_payment_before_freight_and_iva():
    article = {
        "clave": "005.003",
        "iva": Decimal("21"),
        "impuesto_adicional": Decimal("10"),
        "pblret1": Decimal("100"),
        "pblrep1": Decimal("100"),
        "pblret4": Decimal("100"),
        "pblrep4": Decimal("100"),
        "tiporeparto": "P",
        "peso": Decimal("25"),
    }
    customer = {"lista_precio": "4"}
    location = {"fletep1": Decimal("0"), "fletep4": Decimal("5")}
    payment = {"punitorio": Decimal("0"), "descuento": Decimal("12")}

    result = calculate_portal_price(article, customer, location, payment, "reparto")

    assert result == Decimal("123.78")


def test_calculate_vfp_price_calls_the_local_vfp_reference_methods():
    calculator = SimpleNamespace(
        PrecioBase=Mock(return_value=Decimal("100.00")),
        PrecioPublico=Mock(return_value=Decimal("121.00")),
    )
    article = {"clave": "005.003", "tiporeparto": "T", "peso": Decimal("25")}
    customer = {"lista_precio": "4", "condicion_pago_id": "53"}
    location = {"codigo": "0001"}
    payment = {"id": "53"}

    result = calculate_vfp_price(calculator, article, customer, location, payment, "reparto")

    assert result == Decimal("121.00")
    calculator.PrecioBase.assert_called_once_with(
        nPrecio=0.0,
        lReparto=True,
        clave="005.003",
        cLista="4",
    )
    calculator.PrecioPublico.assert_called_once()
    kwargs = calculator.PrecioPublico.call_args.kwargs
    assert kwargs["pago"] == "53"
    assert kwargs["lReparto"] is True
    assert kwargs["localidad"] == "0001"
    assert isinstance(kwargs["peso"], Decimal)
    assert kwargs["peso"] == Decimal("25")


def test_calculate_vfp_price_normalizes_float_freight_before_vfp_iva_math():
    class FloatFreightCalculator:
        flete_reparto = Decimal("0")

        def Reparto(self, *args, **kwargs):
            self.flete_reparto = 0.00
            return 0.00

        def PrecioPublico(self, **kwargs):
            self.Reparto()
            return Decimal("100") + self.flete_reparto * Decimal("21") / 100

    result = calculate_vfp_price(
        FloatFreightCalculator(),
        {"clave": "7820034", "tiporeparto": "", "peso": Decimal("0")},
        {"lista_precio": "1", "condicion_pago_id": "50"},
        {"codigo": "0005"},
        {"id": "50"},
        "reparto",
        base_price=Decimal("100"),
    )

    assert result == Decimal("100.00")


def test_reference_base_prices_suppresses_legacy_per_article_console_warnings(capsys):
    class NoisyCalculator:
        def PrecioBase(self, **kwargs):
            print("legacy calculation warning")
            return Decimal("100.00")

    article = {"clave": "005.003"}

    from ops.automatizaciones.price_sync_monitor import _reference_base_prices
    _reference_base_prices(article, NoisyCalculator())

    assert capsys.readouterr().out == ""


def test_update_alert_state_sends_new_or_changed_issues_once_and_clears_resolved():
    first = {"key": "005.003|4|reparto", "actual": "100.00", "expected": "101.00"}

    state, alerts = update_alert_state({}, [first])
    assert alerts == [first]

    state = mark_alert_notified(state, first["key"])
    state, alerts = update_alert_state(state, [first])
    assert alerts == []

    changed = {**first, "expected": "102.00"}
    state, alerts = update_alert_state(state, [changed])
    assert alerts == [changed]

    state, alerts = update_alert_state(state, [])
    assert alerts == []
    assert state["active"] == {}


def test_grouped_price_alerts_deduplicate_cases_across_rotating_canaries():
    first_case = {
        "key": "00040|005.003|reparto",
        "tipo": "customer_price_mismatch",
        "cliente": "00040",
        "articulo": "005.003",
        "modalidad": "reparto",
        "portal": "100.00",
        "vfp": "101.00",
    }
    second_case = {
        "key": "00041|006.003|reparto",
        "tipo": "customer_price_mismatch",
        "cliente": "00041",
        "articulo": "006.003",
        "modalidad": "reparto",
        "portal": "200.00",
        "vfp": "201.00",
    }

    state, alerts = update_alert_state({}, [_aggregate_discrepancies([first_case, second_case])[0]])
    assert len(alerts) == 1
    assert alerts[0]["cantidad"] == 2
    for key in alerts[0]["_state_keys"]:
        state = mark_alert_notified(state, key)

    state, alerts = update_alert_state(
        state, [_aggregate_discrepancies([first_case])[0]], preserve_missing=True
    )

    assert alerts == []
    assert "case:" + second_case["key"] in state["active"]

    changed_case = {**first_case, "vfp": "102.00"}
    state, alerts = update_alert_state(
        state, [_aggregate_discrepancies([changed_case])[0]], preserve_missing=True
    )

    assert len(alerts) == 1
    assert alerts[0]["cantidad"] == 1
    assert alerts[0]["muestras"] == [changed_case]


class _ReferenceCalculator:
    def PrecioBase(self, **kwargs):
        return Decimal("100.00")

    def PrecioPublico(self, **kwargs):
        return Decimal("121.00")


def _monitor_runtime(state_path, send_alert, *, load_data=None, max_scan_seconds=60):
    article = {
        "clave": "005.003",
        "nombre": "Cal viva",
        "iva": Decimal("21"),
        "tiporeparto": "",
        "peso": Decimal("25"),
        **{field: Decimal("100.00") for field in FIELDS},
    }
    customer = {
        "id": 1,
        "numero_cliente": "00591",
        "lista_precio": "4",
        "condicion_pago_id": "53",
        "codigo_localidad_id": "0001",
        "bonificacion": Decimal("0"),
    }
    data = {
        "articles": [article],
        "customers": [customer],
        "payments": {"53": {"id": "53", "punitorio": Decimal("0"), "descuento": Decimal("0")}},
        "locations": {"0001": {"codigo": "0001", "fletep1": 0, "fletep4": 0, "fletetn1": 0, "fletetn4": 0}},
        "bonifications": [],
    }
    return {
        "load_data": load_data or (lambda: data),
        "calculator_factory": _ReferenceCalculator,
        "send_alert": send_alert,
        "state_path": state_path,
        "rotation_bucket": 0,
        "max_scan_seconds": max_scan_seconds,
    }


def test_monitor_defers_while_hourly_sync_lock_is_held(tmp_path):
    runtime = _monitor_runtime(tmp_path / "state.json", lambda *args: True)
    runtime["load_data"] = Mock(side_effect=AssertionError("must not read during sync"))

    result = run_monitor("canary", runtime=runtime, sync_status={"ok": False, "running": True})

    assert result["status"] == "sync_running"
    runtime["load_data"].assert_not_called()


def test_monitor_reports_operational_error_without_claiming_sync_success(tmp_path):
    sent = []
    runtime = _monitor_runtime(tmp_path / "state.json", lambda message, dry_run: sent.append(message) or True)

    result = run_monitor(
        "canary",
        runtime=runtime,
        sync_status={"ok": False, "running": False, "reason": "OperationalError"},
    )

    assert result["status"] == "sync_error"
    assert result["complete"] is False
    assert len(sent) == 1
    assert "OperationalError" in sent[0]


def test_monitor_checks_persisted_prices_after_sync_error_but_stays_incomplete(tmp_path):
    sent = []
    runtime = _monitor_runtime(tmp_path / "state.json", lambda message, dry_run: sent.append(message) or True)
    original_load = runtime["load_data"]
    runtime["load_data"] = lambda: {
        **original_load(),
        "articles": [
            {
                "clave": "005.003",
                "nombre": "Cal viva",
                "iva": Decimal("21"),
                "tiporeparto": "",
                "peso": Decimal("25"),
                "pblret1": Decimal("100"),
                "pblrep1": Decimal("100"),
                "pblret4": Decimal("100"),
                "pblrep4": Decimal("99"),
            }
        ],
    }

    result = run_monitor(
        "canary",
        runtime=runtime,
        sync_status={"ok": False, "running": False, "reason": "OperationalError"},
    )

    assert result["status"] == "sync_error"
    assert result["complete"] is False
    assert result["price_cases_checked"] == 2
    assert len(sent) == 2
    assert any("OperationalError" in message for message in sent)
    assert any("art. 005.003" in message for message in sent)


def test_monitor_reports_database_read_error(tmp_path):
    sent = []
    runtime = _monitor_runtime(
        tmp_path / "state.json",
        lambda message, dry_run: sent.append(message) or True,
        load_data=Mock(side_effect=OSError("database read failed")),
    )

    result = run_monitor("canary", runtime=runtime, sync_status={"ok": True, "running": False})

    assert result["status"] == "database_error"
    assert result["complete"] is False
    assert len(sent) == 1


def test_monitor_exposes_calculation_error_class_for_diagnosis(tmp_path):
    class BrokenCalculator(_ReferenceCalculator):
        def PrecioPublico(self, **kwargs):
            raise ValueError("bad test value")

    runtime = _monitor_runtime(tmp_path / "state.json", lambda *args: True)
    runtime["calculator_factory"] = BrokenCalculator

    result = run_monitor("canary", runtime=runtime, sync_status={"ok": True, "running": False})

    assert result["complete"] is False
    assert result["reason"] == "vfp_calculation_error:ValueError"
    assert "bad test value" in result["detail_reason"]


def test_monitor_preserves_calculation_error_when_sync_changes_mid_scan(tmp_path):
    class BrokenCalculator(_ReferenceCalculator):
        def PrecioPublico(self, **kwargs):
            raise ValueError("bad test value")

    runtime = _monitor_runtime(tmp_path / "state.json", lambda *args: True)
    runtime["calculator_factory"] = BrokenCalculator
    runtime["post_sync_status"] = lambda: {"ok": False, "running": True}

    result = run_monitor(
        "canary",
        runtime=runtime,
        sync_status={"ok": True, "running": False},
    )

    assert result["reason"] == "sync_started_during_scan"
    assert result["detail_reason"] == "vfp_calculation_error:ValueError"


def test_monitor_reports_missing_erp_article_and_continues_as_incomplete(tmp_path):
    class StockDoesNotExist(Exception):
        pass

    class MissingStockCalculator(_ReferenceCalculator):
        def PrecioPublico(self, **kwargs):
            if kwargs["articulo"] == "005.003":
                raise StockDoesNotExist()
            return Decimal("121.00")

    sent = []
    runtime = _monitor_runtime(tmp_path / "state.json", lambda message, dry_run: sent.append(message) or True)
    original_load = runtime["load_data"]
    runtime["load_data"] = lambda: {
        **original_load(),
        "articles": original_load()["articles"]
        + [
            {
                "clave": "006.003",
                "nombre": "Otro artículo",
                "iva": Decimal("21"),
                "tiporeparto": "",
                "peso": Decimal("10"),
                **{field: Decimal("100.00") for field in FIELDS},
            }
        ],
    }
    runtime["calculator_factory"] = MissingStockCalculator

    result = run_monitor("canary", runtime=runtime, sync_status={"ok": True, "running": False})

    assert result["status"] == "incomplete"
    assert result["complete"] is False
    assert result["reason"] == "source_article_missing"
    assert result["price_cases_checked"] == 2
    assert result["source_articles_missing"] == 1
    assert any("no existe en Stock ERP" in message for message in sent)


def test_monitor_completes_after_reading_back_all_base_fields(tmp_path):
    sent = []
    runtime = _monitor_runtime(tmp_path / "state.json", lambda message, dry_run: sent.append(message) or True)

    result = run_monitor("canary", runtime=runtime, sync_status={"ok": True, "running": False})

    assert result["status"] == "ok"
    assert result["complete"] is True
    assert result["base_fields_checked"] == 4
    assert result["price_cases_checked"] == 2
    assert sent == []


def test_monitor_marks_full_scan_incomplete_when_time_budget_expires(tmp_path):
    sent = []
    runtime = _monitor_runtime(
        tmp_path / "state.json",
        lambda message, dry_run: sent.append(message) or True,
        max_scan_seconds=0,
    )

    result = run_monitor("full", runtime=runtime, sync_status={"ok": True, "running": False})

    assert result["status"] == "incomplete"
    assert result["complete"] is False
    assert len(sent) == 1
    assert "incompleto" in sent[0]


def test_full_scan_is_incomplete_when_no_customer_profiles_are_loaded(tmp_path):
    sent = []
    runtime = _monitor_runtime(tmp_path / "state.json", lambda message, dry_run: sent.append(message) or True)
    original_load = runtime["load_data"]
    runtime["load_data"] = lambda: {**original_load(), "customers": []}

    result = run_monitor("full", runtime=runtime, sync_status={"ok": True, "running": False})

    assert result["status"] == "incomplete"
    assert result["complete"] is False
    assert len(sent) == 1


def test_canary_is_incomplete_when_required_00591_condition_53_fixture_is_missing(tmp_path):
    sent = []
    runtime = _monitor_runtime(tmp_path / "state.json", lambda message, dry_run: sent.append(message) or True)
    original_load = runtime["load_data"]
    runtime["load_data"] = lambda: {
        **original_load(),
        "customers": [
            {
                "id": 2,
                "numero_cliente": "00002",
                "lista_precio": "1",
                "condicion_pago_id": "01",
                "codigo_localidad_id": "0001",
                "bonificacion": Decimal("0"),
            }
        ],
        "payments": {"01": {"id": "01", "punitorio": Decimal("0"), "descuento": Decimal("0")}},
    }

    result = run_monitor("canary", runtime=runtime, sync_status={"ok": True, "running": False})

    assert result["status"] == "incomplete"
    assert result["complete"] is False
    assert "00591" not in sent[0]


def test_canary_checks_only_bounded_article_sample_for_base_prices(tmp_path):
    runtime = _monitor_runtime(tmp_path / "state.json", lambda *args: True)
    original_load = runtime["load_data"]

    def load_many():
        data = original_load()
        data["articles"] = [
            {
                "clave": f"{index:06d}",
                "nombre": "Cal viva",
                "iva": Decimal("21"),
                "tiporeparto": "",
                "peso": Decimal("25"),
                **{field: Decimal("100.00") for field in FIELDS},
            }
            for index in range(20)
        ]
        return data

    runtime["load_data"] = load_many
    result = run_monitor("canary", runtime=runtime, sync_status={"ok": True, "running": False})

    assert result["status"] == "ok"
    assert result["base_fields_checked"] == 32
    assert result["price_cases_checked"] == 16


def test_monitor_does_not_claim_green_if_updater_starts_during_scan(tmp_path):
    runtime = _monitor_runtime(tmp_path / "state.json", lambda *args: True)
    runtime["post_sync_status"] = lambda: {"ok": False, "running": True, "reason": "sync_running"}

    result = run_monitor("canary", runtime=runtime, sync_status={"ok": True, "running": False})

    assert result["status"] == "incomplete"
    assert result["complete"] is False


def test_monitor_stops_customer_price_scan_when_updater_lock_appears(tmp_path):
    runtime = _monitor_runtime(tmp_path / "state.json", lambda *args: True)
    lock_checks = 0

    def lock_appears_during_pricing(_path):
        nonlocal lock_checks
        lock_checks += 1
        return lock_checks > 1

    runtime["is_lock_held"] = lock_appears_during_pricing
    runtime["batch_size"] = 1

    result = run_monitor("canary", runtime=runtime, sync_status={"ok": True, "running": False})

    assert result["status"] == "incomplete"
    assert result["complete"] is False
    assert result["reason"] == "sync_started"
    assert result["price_cases_checked"] == 1


def test_monitor_detects_updater_that_started_and_finished_during_scan(tmp_path):
    runtime = _monitor_runtime(tmp_path / "state.json", lambda *args: True)
    runtime["post_sync_status"] = lambda: {
        "ok": True,
        "running": False,
        "log_mtime": 200,
    }

    result = run_monitor(
        "canary",
        runtime=runtime,
        sync_status={"ok": True, "running": False, "log_mtime": 100},
    )

    assert result["status"] == "incomplete"
    assert result["complete"] is False


def test_monitor_dry_run_does_not_mark_pending_alert_as_sent(tmp_path):
    attempts = []
    runtime = _monitor_runtime(
        tmp_path / "state.json",
        lambda message, dry_run: attempts.append(dry_run) or True,
    )
    original_load = runtime["load_data"]
    runtime["load_data"] = lambda: {
        **original_load(),
        "articles": [
            {
                "clave": "005.003",
                "nombre": "Cal viva",
                "iva": Decimal("21"),
                "tiporeparto": "",
                "peso": Decimal("25"),
                "pblret1": Decimal("100"),
                "pblrep1": Decimal("100"),
                "pblret4": Decimal("100"),
                "pblrep4": Decimal("99"),
            }
        ],
    }
    good_sync = {"ok": True, "running": False}

    preview = run_monitor("canary", dry_run=True, runtime=runtime, sync_status=good_sync)
    actual = run_monitor("canary", runtime=runtime, sync_status=good_sync)

    assert preview["status"] == "dry_run"
    assert actual["notifications_sent"] == 1
    assert attempts == [True, False]


def test_sync_health_rejects_latest_hourly_log_with_operational_error(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    latest_log = log_dir / "actualiza_lista_reventa-20261102-180001.log"
    latest_log.write_text("OperationalError\n", encoding="utf-8")
    monkeypatch.setattr("ops.automatizaciones.price_sync_monitor.SYNC_LOCK_PATH", tmp_path / "not-held.lock")
    monkeypatch.setattr("ops.automatizaciones.price_sync_monitor.SYNC_LOG_DIR", log_dir)

    result = check_sync_status(now=latest_log.stat().st_mtime)

    assert result["ok"] is False
    assert result["reason"] == "database_error"


def test_sync_health_accepts_caught_already_open_connection_when_job_finishes_cleanly(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    latest_log = log_dir / "actualiza_lista_reventa-20261102-190001.log"
    latest_log.write_text(
        "ERROR: Error al conectar a la base de datos: Connection already opened.\n"
        "Traceback (most recent call last):\n"
        "peewee.OperationalError: Connection already opened.\n"
        "INFO: Actualización de bonificaciones completada\n"
        "Resumen: 10369 actualizados, 0 creados, 0 errores\n"
        "2026-11-02T19:06:26+00:00 END exit_code=0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("ops.automatizaciones.price_sync_monitor.SYNC_LOCK_PATH", tmp_path / "not-held.lock")
    monkeypatch.setattr("ops.automatizaciones.price_sync_monitor.SYNC_LOG_DIR", log_dir)

    result = check_sync_status(now=latest_log.stat().st_mtime)

    assert result["ok"] is True
    assert result["warning"] == "connection_already_opened_but_job_completed"


def test_failed_whatsapp_send_is_retried_without_deduping_pending_alert(tmp_path):
    attempts = []
    runtime = _monitor_runtime(
        tmp_path / "state.json",
        lambda message, dry_run: attempts.append(message) and False,
    )
    original_load = runtime["load_data"]
    runtime["load_data"] = lambda: {
        **original_load(),
        "articles": [
            {
                "clave": "005.003",
                "nombre": "Cal viva",
                "iva": Decimal("21"),
                "tiporeparto": "",
                "peso": Decimal("25"),
                "pblret1": Decimal("100"),
                "pblrep1": Decimal("100"),
                "pblret4": Decimal("100"),
                "pblrep4": Decimal("99"),
            }
        ],
    }
    good_sync = {"ok": True, "running": False}

    first = run_monitor("canary", runtime=runtime, sync_status=good_sync)
    second = run_monitor("canary", runtime=runtime, sync_status=good_sync)

    assert first["notification_failures"] == 1
    assert second["notification_failures"] == 1
    assert len(attempts) == 2
