from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from ops.automatizaciones.oportunidades_miro_no_compro import (
    _to_local_date,
    encolar_mails_clientes,
    fasa_table,
    fe_table,
    fetch_oportunidades,
    format_html,
    format_text,
    mail_cliente,
    plan_mails_clientes,
    sanitizar_latin1,
)

ARG = ZoneInfo("America/Argentina/Buenos_Aires")
START = datetime(2026, 11, 12, 0, 0, tzinfo=ARG)
END = datetime(2026, 11, 19, 8, 0, tzinfo=ARG)

# numero, nombre, clave, articulo, veces, primera, ultima,
# cliente_id, email, recibe, stock, discontinuado
MIRADAS = [
    # Miró y no compró nunca -> oportunidad, con stock -> mail
    ("00040", "Corralon Uno", "CEM001", "CEMENTO 50KG", 3,
     datetime(2026, 11, 14, 13, 0), datetime(2026, 11, 18, 21, 40),
     10, "uno@ejemplo.com", 1, 50, ""),
    # Compró antes de mirar -> oportunidad con historial, sin stock -> sin mail
    ("00040", "Corralon Uno", "CAL002", "CAL 25KG", 2,
     datetime(2026, 11, 15, 13, 0), datetime(2026, 11, 15, 14, 0),
     10, "uno@ejemplo.com", 1, 0, ""),
    # Compró después de mirar -> conversión
    ("00077", "Ferreteria Dos", "HIE003", "HIERRO 8", 2,
     datetime(2026, 11, 13, 12, 0), datetime(2026, 11, 13, 12, 5),
     20, "dos@ejemplo.com", 1, 10, ""),
    # Pidió la baja -> oportunidad sin mail
    ("00099", "Cliente Baja", "CEM001", "CEMENTO 50KG", 4,
     datetime(2026, 11, 16, 12, 0), datetime(2026, 11, 17, 12, 0),
     30, "baja@ejemplo.com", 0, 50, ""),
]


def _runtime(previas=(), executed=None, fail_execute=False):
    def query(sql, params):
        if "FROM api_consultaprecio" in sql:
            assert params[-1] == 2  # min_consultas
            return list(MIRADAS)
        if "MAX(fecha)" in sql:
            assert "`fasa`.`facturas`" in sql and "codigo = 'F'" in sql
            return [("00040", "CAL002", date(2026, 10, 1)),
                    ("00077", "HIE003", date(2026, 11, 14))]
        if "NOM_VEN" in sql:
            return [("00040", "03", "PEREZ", date(2026, 11, 1)),
                    ("00040", "05", "OTRO", date(2026, 9, 1)),
                    ("00077", "07", "GOMEZ", date(2026, 11, 14))]
        if "FROM api_ofertaenviada" in sql:
            return list(previas)
        raise AssertionError(sql)

    def execute_batch(stmts):
        if fail_execute:
            raise RuntimeError("sin permiso en fe")
        executed.append(stmts)

    return {"query": query, "execute_batch": execute_batch}


def test_table_names_validan_identificador(monkeypatch):
    assert fasa_table() == "`fasa`.`facturas`"
    assert fe_table() == "`fe`.`emails_pendientes`"
    monkeypatch.setenv("FASA_DB_NAME", "fasa; DROP")
    with pytest.raises(ValueError):
        fasa_table()


def test_to_local_date_convierte_utc_y_centinela():
    assert _to_local_date(datetime(2026, 11, 15, 2, 0)) == date(2026, 11, 14)
    assert _to_local_date("0000-00-00") is None
    assert _to_local_date(date(2026, 1, 2)) == date(2026, 1, 2)


def test_fetch_clasifica_miro_compro_y_vendedor():
    report = fetch_oportunidades(START, END, runtime=_runtime())
    no_compro = {(i["numero"], i["clave"]): i for i in report["no_compro"]}
    assert set(no_compro) == {("00040", "CEM001"), ("00040", "CAL002"), ("00099", "CEM001")}
    assert no_compro[("00040", "CEM001")]["ultima_compra"] is None
    assert no_compro[("00040", "CAL002")]["dias_sin_comprar"] == 49
    assert no_compro[("00040", "CEM001")]["vendedor"] == "03 PEREZ"
    assert no_compro[("00099", "CEM001")]["vendedor"] == "Sin vendedor"
    assert [(i["numero"], i["clave"]) for i in report["compro"]] == [("00077", "HIE003")]
    text = format_text(report)
    assert "VENDEDOR 03 PEREZ" in text and "NUNCA lo compró" in text
    assert "MIRARON Y COMPRARON" in text
    assert "CEM001" in format_html(report)


def test_plan_mails_respeta_stock_baja_y_cooldown():
    report = fetch_oportunidades(START, END, runtime=_runtime())
    mails = plan_mails_clientes(report, runtime=_runtime(), now=END)
    assert [(m["numero"], [a["clave"] for a in m["articulos"]]) for m in mails] == [
        ("00040", ["CEM001"])
    ]
    # Ya se le ofreció CEM001 hace 20 días -> no se repite
    previas = [(10, "CEM001", datetime(2026, 10, 30, 12, 0))]
    assert plan_mails_clientes(report, runtime=_runtime(previas), now=END) == []
    # Recibió otro mail hace 2 días -> cooldown del cliente
    previas = [(10, "OTRO", datetime(2026, 11, 17, 12, 0))]
    assert plan_mails_clientes(report, runtime=_runtime(previas), now=END) == []


def test_mail_cliente_y_encolado_registra_oferta():
    report = fetch_oportunidades(START, END, runtime=_runtime())
    mails = plan_mails_clientes(report, runtime=_runtime(), now=END)
    asunto, texto, html = mail_cliente(mails[0])
    assert "CEMENTO 50KG" in asunto
    assert "BAJA" in texto and "Corralon Uno" in html
    assert sanitizar_latin1(html) == html  # sin emojis: entra en latin1

    executed = []
    assert encolar_mails_clientes(mails, runtime=_runtime(executed=executed), now=END) == 1
    (stmts,) = executed
    assert "`fe`.`emails_pendientes`" in stmts[0][0]
    assert stmts[0][1][0] == "uno@ejemplo.com"
    assert "api_ofertaenviada" in stmts[1][0] and stmts[1][1][:2] == (10, "CEM001")
    assert "[se le envió mail]" in format_text(report)


def test_encolado_fallido_no_marca_enviado(capsys):
    report = fetch_oportunidades(START, END, runtime=_runtime())
    mails = plan_mails_clientes(report, runtime=_runtime(), now=END)
    assert encolar_mails_clientes(mails, runtime=_runtime(fail_execute=True), now=END) == 0
    assert "ERROR encolando" in capsys.readouterr().out
    assert "[se le envió mail]" not in format_text(report)
