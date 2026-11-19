"""Oportunidades de venta: clientes que miraron precios y no compraron.

Cruza lo que el cliente MIRA en el portal con lo que COMPRA en el ERP:

- ``api_consultaprecio`` (base ``revendedores``): cada clic en "Ver precio".
  Todos los usuarios del portal tienen ficha en ``api_cliente`` (no se
  pueden registrar sin código de cliente), así que se cruza por
  ``numero_cliente``.
- ``<FASA_DB_NAME>.facturas`` (vista del ERP VFP, se actualiza sola; mismo
  servidor MySQL): renglones facturados por cliente y ``clave``. Solo cuenta
  ``codigo = 'F'`` (facturas); notas de crédito/débito no son compras y los
  remitos viven en otra tabla.

Para cada par cliente + artículo con ``--min-consultas`` o más clics en la
ventana (default: últimos 7 días):

- **Miró y no compró**: no tiene factura de ese artículo desde el día de la
  primera consulta. Es la lista de llamados para ventas, agrupada por
  vendedor (el de la última factura del cliente).
- **Miró y compró**: sí tiene factura desde la primera consulta (conversión).

El ERP se consulta en dos pasos acotados (``cliente IN (...)``) en vez de un
JOIN entre bases, para no recorrer la vista completa de facturas.

Con ``--enviar-clientes`` además le escribe a cada cliente ofreciéndole lo que
miró y no compró, por la cola ``<FE_DB_NAME>.emails_pendientes`` (la manda
genera-fe-2025 desde ventas@, así las respuestas le llegan a Ventas). Reglas
para no saturar:

- solo artículos con stock y no discontinuados;
- solo clientes con email y ``recibe_ofertas_email`` (baja: responder BAJA y
  destildarlo en el admin);
- como máximo un mail por cliente cada ``CLIENTE_COOLDOWN_DIAS`` y el mismo
  artículo no se vuelve a ofrecer hasta ``ARTICULO_COOLDOWN_DIAS``;
- hasta ``MAX_ARTICULOS_MAIL`` artículos por mail.

Cada artículo ofrecido queda en ``api_ofertaenviada``.

Uso:
    oportunidades_miro_no_compro.py                    # últimos 7 días, envía
    oportunidades_miro_no_compro.py --dry-run          # imprime, no envía
    oportunidades_miro_no_compro.py --dias 14 --min-consultas 3 --dry-run
    oportunidades_miro_no_compro.py --to otro@ejemplo.com --dry-run
    oportunidades_miro_no_compro.py --enviar-clientes --dry-run   # muestra los mails
    oportunidades_miro_no_compro.py --enviar-clientes             # reporte + clientes
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

try:  # paquete (tests) o script suelto en /opt/automatizaciones/jobs
    from .resumen_busquedas_precios import (
        DEFAULT_TO,
        LOCAL_TZ,
        UTC,
        _cuantos,
        _load_runtime,
        send_mail,
    )
except ImportError:  # pragma: no cover - ejecución como script
    from resumen_busquedas_precios import (  # type: ignore[no-redef]
        DEFAULT_TO,
        LOCAL_TZ,
        UTC,
        _cuantos,
        _load_runtime,
        send_mail,
    )

DEFAULT_DIAS = 7
DEFAULT_MIN_CONSULTAS = 2
VENDEDOR_LOOKBACK_DIAS = 365
CLIENTE_COOLDOWN_DIAS = 7
ARTICULO_COOLDOWN_DIAS = 30
MAX_ARTICULOS_MAIL = 5
QUIEN_ENVIA = "ventas@ferreteriaavenida.com.ar"
PORTAL_URL = "https://ventas.ferreteriaavenida.com.ar/productos"
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_IDENT_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _qualified(env_var: str, default_db: str, name: str) -> str:
    db = os.environ.get(env_var, default_db).strip()
    if not _IDENT_RE.match(db) or not _IDENT_RE.match(name):
        raise ValueError(f"nombre de base/tabla inválido: {db!r}.{name!r}")
    return f"`{db}`.`{name}`"


def fasa_table(name: str = "facturas") -> str:
    """Nombre calificado de la tabla del ERP (``fasa.facturas`` por default)."""
    return _qualified("FASA_DB_NAME", "fasa", name)


def fe_table(name: str = "emails_pendientes") -> str:
    """Nombre calificado de la cola de mails (``fe.emails_pendientes``)."""
    return _qualified("FE_DB_NAME", "fe", name)


def sanitizar_latin1(texto: str) -> str:
    """La cola es latin1: normaliza y reemplaza lo que no entra (como el portal)."""
    normalizado = unicodedata.normalize("NFC", str(texto))
    return normalizado.encode("latin1", errors="replace").decode("latin1")


def _to_local_date(value: Any) -> date | None:
    """datetime UTC naive (Django) / aware / date / str -> fecha local."""
    if value is None:
        return None
    if isinstance(value, datetime):
        aware = value if value.tzinfo else value.replace(tzinfo=UTC)
        return aware.astimezone(LOCAL_TZ).date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text or text.startswith("0000"):
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _read_env(path: Path) -> dict[str, str]:
    """Lee un .env simple (KEY=VALUE, comentarios con #)."""
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def _load_runtime_local(env_path: Path) -> dict[str, Any]:
    """Conexión directa con las credenciales del backend (para probar desde una PC).

    Usa DB_* de ``backend/.env`` (base ``revendedores``); ``fasa`` y ``fe`` se
    consultan calificadas, así que ese usuario necesita permisos sobre ellas.
    """
    import pymysql  # dependencia del backend

    env = _read_env(env_path)
    for key in ("FASA_DB_NAME", "FE_DB_NAME"):
        if env.get(key) and key not in os.environ:
            os.environ[key] = env[key]
    conn = pymysql.connect(
        host=env.get("DB_HOST") or "localhost",
        port=int(env.get("DB_PORT") or 3306),
        user=env["DB_USER"],
        password=env.get("DB_PASSWORD", ""),
        database=env["DB_NAME"],
        charset="utf8mb4",
        autocommit=True,
    )

    def query(sql: str, params: tuple[Any, ...]) -> list[tuple[Any, ...]]:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    def execute_batch(statements: list[tuple[str, tuple[Any, ...]]]) -> None:
        conn.begin()
        try:
            with conn.cursor() as cur:
                for sql, params in statements:
                    cur.execute(sql, params)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return {"query": query, "execute_batch": execute_batch}


def _placeholders(n: int) -> str:
    return ", ".join(["%s"] * n)


def fetch_oportunidades(
    start: datetime,
    end: datetime,
    *,
    runtime: dict[str, Any],
    min_consultas: int = DEFAULT_MIN_CONSULTAS,
) -> dict[str, Any]:
    """Arma el reporte miró/compró para la ventana [start, end)."""
    q = runtime["query"]
    start_s = start.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
    end_s = end.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")

    def _miradas_sql(recibe_col: str, group_extra: str) -> str:
        return (
            "SELECT ac.numero_cliente, ac.nombre, cp.articulo_id, COALESCE(ar.nombre, ''), "
            "COUNT(*), MIN(cp.fecha_hora), MAX(cp.fecha_hora), "
            f"ac.id, COALESCE(au.email, ''), {recibe_col}, "
            "COALESCE(ar.stock_efectivo, ar.stock, 0), COALESCE(ar.discontinuado, '') "
            "FROM api_consultaprecio cp "
            "JOIN api_cliente ac ON ac.user_id = cp.usuario_id "
            "JOIN auth_user au ON au.id = cp.usuario_id "
            "LEFT JOIN api_articulos ar ON ar.clave = cp.articulo_id "
            "WHERE cp.fecha_hora >= %s AND cp.fecha_hora < %s "
            "GROUP BY ac.numero_cliente, ac.nombre, cp.articulo_id, ar.nombre, "
            f"ac.id, au.email, {group_extra}ar.stock_efectivo, ar.stock, "
            "ar.discontinuado "
            "HAVING COUNT(*) >= %s"
        )

    params = (start_s, end_s, int(min_consultas))
    try:
        miradas = q(_miradas_sql("ac.recibe_ofertas_email", "ac.recibe_ofertas_email, "), params)
    except Exception as exc:  # noqa: BLE001
        if "recibe_ofertas_email" not in str(exc):
            raise
        # Base sin la migración 0041: el reporte sale igual; nadie figura con
        # opt-in, así que no se le escribe a ningún cliente.
        print("AVISO: falta la migración 0041 (recibe_ofertas_email); "
              "no se enviarán mails a clientes.")
        miradas = q(_miradas_sql("0", ""), params)

    pares: list[dict[str, Any]] = []
    for (numero, cliente, clave, articulo, veces, primera, ultima,
         cliente_id, email, recibe, stock, discontinuado) in miradas:
        numero = str(numero or "").strip()
        clave = str(clave or "").strip()
        if not numero or not clave:
            continue
        pares.append({
            "numero": numero,
            "cliente": str(cliente or "").strip(),
            "clave": clave,
            "articulo": str(articulo or "").strip(),
            "consultas": int(veces),
            "primera": _to_local_date(primera),
            "ultima_consulta": ultima,
            "cliente_id": int(cliente_id),
            "email": str(email or "").strip(),
            "recibe_ofertas": bool(recibe),
            "con_stock": float(stock or 0) > 0,
            "discontinuado": str(discontinuado or "").strip().upper() == "S",
            "mail_cliente": False,
        })

    numeros = sorted({p["numero"] for p in pares})
    claves = sorted({p["clave"] for p in pares})
    ultima_compra: dict[tuple[str, str], date] = {}
    vendedores: dict[str, str] = {}

    if numeros:
        facturas = fasa_table("facturas")
        compras = q(
            f"SELECT cliente, clave, MAX(fecha) FROM {facturas} "
            f"WHERE codigo = 'F' AND cliente IN ({_placeholders(len(numeros))}) "
            f"AND clave IN ({_placeholders(len(claves))}) "
            "GROUP BY cliente, clave",
            (*numeros, *claves),
        )
        for cli, clave, fecha in compras:
            fecha_d = _to_local_date(fecha)
            if fecha_d is None:
                continue
            key = (str(cli or "").strip(), str(clave or "").strip())
            if key not in ultima_compra or fecha_d > ultima_compra[key]:
                ultima_compra[key] = fecha_d

        desde_vend = (end.astimezone(LOCAL_TZ).date()
                      - timedelta(days=VENDEDOR_LOOKBACK_DIAS)).isoformat()
        filas_vend = q(
            f"SELECT f.cliente, f.vendedor, COALESCE(v.NOM_VEN, ''), f.fecha "
            f"FROM {facturas} f LEFT JOIN {fasa_table('vendedor')} v "
            "ON v.VENDEDOR = f.vendedor "
            f"WHERE f.codigo = 'F' AND f.cliente IN ({_placeholders(len(numeros))}) "
            "AND f.fecha >= %s ORDER BY f.fecha DESC",
            (*numeros, desde_vend),
        )
        for cli, cod, nombre, _fecha in filas_vend:
            cli = str(cli or "").strip()
            if cli in vendedores:
                continue
            cod = str(cod or "").strip()
            nombre = str(nombre or "").strip()
            label = f"{cod} {nombre}".strip()
            if label:
                vendedores[cli] = label

    hoy = end.astimezone(LOCAL_TZ).date()
    no_compro: list[dict[str, Any]] = []
    compro: list[dict[str, Any]] = []
    for p in pares:
        ult = ultima_compra.get((p["numero"], p["clave"]))
        item = {
            **p,
            "ultima_consulta": _fmt_dt(p["ultima_consulta"]),
            "ultima_compra": ult.isoformat() if ult else None,
            "dias_sin_comprar": (hoy - ult).days if ult else None,
            "vendedor": vendedores.get(p["numero"], "Sin vendedor"),
        }
        if ult is not None and p["primera"] is not None and ult >= p["primera"]:
            compro.append(item)
        else:
            no_compro.append(item)

    no_compro.sort(key=lambda i: (i["vendedor"], -i["consultas"], i["cliente"]))
    compro.sort(key=lambda i: (-i["consultas"], i["cliente"]))

    por_vendedor: dict[str, list[dict[str, Any]]] = {}
    for item in no_compro:
        por_vendedor.setdefault(item["vendedor"], []).append(item)

    return {
        "inicio": _fmt_dt(start),
        "fin": _fmt_dt(end),
        "min_consultas": int(min_consultas),
        "no_compro": no_compro,
        "por_vendedor": por_vendedor,
        "compro": compro,
        "clientes": len(numeros),
    }


def _fmt_dt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        aware = value if value.tzinfo else value.replace(tzinfo=UTC)
        return aware.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M")
    return str(value)


def _historial(item: dict[str, Any]) -> str:
    if item["ultima_compra"] is None:
        return "NUNCA lo compró"
    return (f"última compra {item['ultima_compra']} "
            f"(hace {_cuantos(item['dias_sin_comprar'], 'día', 'días')})")


def format_text(report: dict[str, Any]) -> str:
    nc, c = report["no_compro"], report["compro"]
    lines = [
        f"Miraron y no compraron - {report['inicio']} a {report['fin']} (Arg)",
        "=" * 60,
        f"Pares cliente+artículo con {report['min_consultas']}+ clics en Ver precio. "
        f"{_cuantos(len(nc), 'oportunidad', 'oportunidades')}, "
        f"{_cuantos(len(c), 'conversión', 'conversiones')}.",
        "",
    ]
    if not nc:
        lines.append("Sin oportunidades pendientes en el período.")
    for vendedor, items in report["por_vendedor"].items():
        lines.append(f"VENDEDOR {vendedor}:")
        for i in items:
            lines.append(
                f"  - {i['numero']} {i['cliente']}: {i['clave']} {i['articulo']} — "
                f"{_cuantos(i['consultas'], 'vez', 'veces')} (última {i['ultima_consulta']}); "
                f"{_historial(i)}"
                + (" [se le envió mail]" if i.get("mail_cliente") else "")
            )
        lines.append("")
    if c:
        lines.append("MIRARON Y COMPRARON (conversión):")
        for i in c:
            lines.append(
                f"  - {i['numero']} {i['cliente']}: {i['clave']} {i['articulo']} — "
                f"facturado {i['ultima_compra']}"
            )
    return "\n".join(lines) + "\n"


def format_html(report: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return (str(value).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;"))

    th = 'style="text-align:left;background:#1565c0;color:#fff;padding:6px"'
    td = 'style="padding:6px;border-bottom:1px solid #eee"'
    head = (f"<tr><th {th}>Cliente</th><th {th}>Artículo</th><th {th}>Clics</th>"
            f"<th {th}>Última consulta</th><th {th}>Historial</th></tr>")

    bloques = []
    for vendedor, items in report["por_vendedor"].items():
        rows = "".join(
            f"<tr><td {td}>{esc(i['numero'])} {esc(i['cliente'])}</td>"
            f"<td {td}>{esc(i['clave'])} {esc(i['articulo'])}</td>"
            f"<td {td}>{i['consultas']}</td><td {td}>{esc(i['ultima_consulta'])}</td>"
            f"<td {td}>{'<strong>' + esc(_historial(i)) + '</strong>' if i['ultima_compra'] is None else esc(_historial(i))}"
            f"{' · mail enviado' if i.get('mail_cliente') else ''}</td></tr>"
            for i in items
        )
        bloques.append(
            f"<h3>Vendedor {esc(vendedor)} ({len(items)})</h3>"
            f"<table style=\"width:100%;border-collapse:collapse\">{head}{rows}</table>"
        )
    cuerpo = "".join(bloques) or "<p>Sin oportunidades pendientes en el período.</p>"

    conv = ""
    if report["compro"]:
        conv_rows = "".join(
            f"<li>{esc(i['numero'])} {esc(i['cliente'])}: {esc(i['clave'])} "
            f"{esc(i['articulo'])} — facturado {esc(i['ultima_compra'])}</li>"
            for i in report["compro"]
        )
        conv = f"<h3>✅ Miraron y compraron ({len(report['compro'])})</h3><ul>{conv_rows}</ul>"

    return f"""<html><body style="font-family:Arial,sans-serif;background:#f6f7f9;padding:20px">
<div style="max-width:860px;margin:auto;background:#fff;padding:24px;border-radius:8px">
<h2 style="color:#1565c0;margin-top:0">📞 Miraron y no compraron</h2>
<p><strong>{esc(report['inicio'])} a {esc(report['fin'])} (Arg)</strong> ·
{report['min_consultas']}+ clics en Ver precio ·
{len(report['no_compro'])} oportunidades · {len(report['compro'])} conversiones</p>
{cuerpo}
{conv}
<p style="color:#777;font-size:12px;margin-top:24px">Cruce portal (Ver precio) + facturas del ERP. Generado automáticamente por automatizaciones 189.</p>
</div></body></html>"""


def plan_mails_clientes(
    report: dict[str, Any],
    *,
    runtime: dict[str, Any],
    now: datetime | None = None,
    cliente_cooldown: int = CLIENTE_COOLDOWN_DIAS,
    articulo_cooldown: int = ARTICULO_COOLDOWN_DIAS,
    max_articulos: int = MAX_ARTICULOS_MAIL,
) -> list[dict[str, Any]]:
    """Qué mail le toca a cada cliente según las reglas anti-saturación."""
    now = now or datetime.now(LOCAL_TZ)
    elegibles = [
        i for i in report["no_compro"]
        if i["recibe_ofertas"] and i["con_stock"] and not i["discontinuado"]
        and _EMAIL_RE.match(i["email"] or "")
    ]
    if not elegibles:
        return []

    ids = sorted({i["cliente_id"] for i in elegibles})
    desde_art = (now - timedelta(days=articulo_cooldown)).astimezone(UTC)
    desde_cli = (now - timedelta(days=cliente_cooldown)).astimezone(UTC)
    previas = runtime["query"](
        "SELECT cliente_id, articulo_id, enviado_en FROM api_ofertaenviada "
        f"WHERE cliente_id IN ({_placeholders(len(ids))}) AND enviado_en >= %s",
        (*ids, desde_art.strftime("%Y-%m-%d %H:%M:%S")),
    )
    ya_ofrecido: set[tuple[int, str]] = set()
    con_mail_reciente: set[int] = set()
    for cli_id, art, enviado in previas:
        ya_ofrecido.add((int(cli_id), str(art or "").strip()))
        if isinstance(enviado, datetime):
            aware = enviado if enviado.tzinfo else enviado.replace(tzinfo=UTC)
            if aware >= desde_cli:
                con_mail_reciente.add(int(cli_id))

    por_cliente: dict[int, dict[str, Any]] = {}
    for i in sorted(elegibles, key=lambda x: -x["consultas"]):
        if i["cliente_id"] in con_mail_reciente:
            continue
        if (i["cliente_id"], i["clave"]) in ya_ofrecido:
            continue
        mail = por_cliente.setdefault(i["cliente_id"], {
            "cliente_id": i["cliente_id"],
            "numero": i["numero"],
            "cliente": i["cliente"],
            "email": i["email"],
            "articulos": [],
        })
        if len(mail["articulos"]) < max_articulos:
            mail["articulos"].append(i)
    return [m for m in por_cliente.values() if m["articulos"]]


def mail_cliente(mail: dict[str, Any]) -> tuple[str, str, str]:
    """(asunto, texto, html) del mail al cliente. Sin emojis: la cola es latin1."""
    def esc(value: Any) -> str:
        return (str(value).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;"))

    nombre = mail["cliente"] or "cliente"
    arts = mail["articulos"]
    if len(arts) == 1:
        asunto = f"{arts[0]['articulo'] or arts[0]['clave']}: lo tenemos disponible"
    else:
        asunto = "Los artículos que estuviste mirando están disponibles"

    lineas = [f"  - {a['articulo'] or a['clave']} (cód. {a['clave']})" for a in arts]
    texto = (
        f"Hola {nombre},\n\n"
        "Vimos que estuviste consultando estos artículos en el portal de "
        "Ferretería Avenida y te contamos que los tenemos en stock:\n\n"
        + "\n".join(lineas)
        + "\n\nSi querés que te los preparemos, o necesitás precio por cantidad, "
        "respondé este mail y te contactamos.\n"
        f"También podés verlos en {PORTAL_URL}\n\n"
        "Saludos,\nVentas - Ferretería Avenida\n\n"
        "Si no querés recibir estas sugerencias, respondé BAJA.\n"
    )
    filas = "".join(
        f"<li><strong>{esc(a['articulo'] or a['clave'])}</strong> "
        f"<span style=\"color:#777\">(cód. {esc(a['clave'])})</span></li>"
        for a in arts
    )
    html = f"""<html><body style="font-family:Arial,sans-serif;background:#f6f7f9;padding:20px">
<div style="max-width:600px;margin:auto;background:#fff;padding:24px;border-radius:8px">
<p>Hola {esc(nombre)},</p>
<p>Vimos que estuviste consultando estos artículos en el portal de Ferretería Avenida
y te contamos que <strong>los tenemos en stock</strong>:</p>
<ul>{filas}</ul>
<p>Si querés que te los preparemos, o necesitás precio por cantidad,
<strong>respondé este mail</strong> y te contactamos.</p>
<p><a href="{PORTAL_URL}" style="background:#1565c0;color:#fff;padding:10px 18px;border-radius:4px;text-decoration:none">Ver en el portal</a></p>
<p>Saludos,<br>Ventas - Ferretería Avenida</p>
<p style="color:#999;font-size:11px;margin-top:24px">Si no querés recibir estas sugerencias, respondé BAJA a este mail.</p>
</div></body></html>"""
    return asunto, texto, html


def encolar_mails_clientes(
    mails: list[dict[str, Any]],
    *,
    runtime: dict[str, Any],
    now: datetime | None = None,
) -> int:
    """Encola cada mail en la cola fe y registra lo ofrecido (una transacción por mail)."""
    now_utc = (now or datetime.now(LOCAL_TZ)).astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
    cola = fe_table("emails_pendientes")
    enviados = 0
    for mail in mails:
        asunto, texto, html = mail_cliente(mail)
        stmts: list[tuple[str, tuple[Any, ...]]] = [(
            f"INSERT INTO {cola} (destinatario, quien_envia, asunto, cuerpo_html, "
            "cuerpo_texto, intentos, estado, creado_en, empresa_id) "
            "VALUES (%s, %s, %s, %s, %s, 0, 'pendiente', %s, 1)",
            (mail["email"], QUIEN_ENVIA, sanitizar_latin1(asunto),
             sanitizar_latin1(html), sanitizar_latin1(texto), now_utc),
        )]
        for a in mail["articulos"]:
            stmts.append((
                "INSERT INTO api_ofertaenviada (cliente_id, articulo_id, enviado_en, "
                "consultas, email) VALUES (%s, %s, %s, %s, %s)",
                (mail["cliente_id"], a["clave"], now_utc, a["consultas"], mail["email"]),
            ))
        try:
            runtime["execute_batch"](stmts)
        except Exception as exc:  # noqa: BLE001 - sigue con los demás clientes
            print(f"ERROR encolando mail a {mail['numero']} {mail['email']}: {exc}")
            continue
        for a in mail["articulos"]:
            a["mail_cliente"] = True
        enviados += 1
    return enviados


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clientes que miraron precios y no compraron")
    parser.add_argument("--dias", type=int, default=DEFAULT_DIAS,
                        help=f"días hacia atrás de consultas (default {DEFAULT_DIAS})")
    parser.add_argument("--min-consultas", type=int, default=DEFAULT_MIN_CONSULTAS,
                        help=f"clics mínimos por artículo (default {DEFAULT_MIN_CONSULTAS})")
    parser.add_argument("--to", action="append", default=[],
                        help="destinatario (repite la opción)")
    parser.add_argument("--enviar-clientes", action="store_true",
                        help="además le escribe a cada cliente ofreciendo lo que miró")
    parser.add_argument("--env", default=None,
                        help="usar las credenciales de este .env (ej. backend/.env) "
                             "en vez de la conexión del legado; para probar desde una PC")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dias < 1 or args.min_consultas < 1:
        parser.error("--dias y --min-consultas deben ser >= 1")

    end = datetime.now(LOCAL_TZ)
    start = (end - timedelta(days=args.dias)).replace(hour=0, minute=0, second=0, microsecond=0)

    to = list(args.to) if args.to else [
        e.strip() for e in os.environ.get(
            "OPORTUNIDADES_TO", os.environ.get("RESUMEN_TO", ",".join(DEFAULT_TO))
        ).split(",") if e.strip()
    ]
    if not to:
        print("Sin destinatarios: definir OPORTUNIDADES_TO o --to", file=sys.stderr)
        return 2

    runtime = _load_runtime_local(Path(args.env)) if args.env else _load_runtime()
    report = fetch_oportunidades(start, end, runtime=runtime,
                                 min_consultas=args.min_consultas)
    mails: list[dict[str, Any]] = []
    if args.enviar_clientes:
        try:
            mails = plan_mails_clientes(report, runtime=runtime, now=end)
        except Exception as exc:  # noqa: BLE001
            if not args.dry_run:
                raise  # sin historial de ofertas no se envía nada (evita repetir)
            print(f"AVISO: no se pudo leer api_ofertaenviada ({exc}); "
                  "¿falta migrar 0041? Se simula sin historial de ofertas.")
            mails = plan_mails_clientes(
                report, runtime={**runtime, "query": lambda sql, params: []}, now=end)
    if args.dry_run and mails:
        print(f"=== {_cuantos(len(mails), 'mail', 'mails')} a clientes (NO se encolan) ===")
        for m in mails:
            asunto, texto, _html = mail_cliente(m)
            print(f"Para: {m['email']} | Asunto: {asunto}")
            print(texto)
    elif mails:
        n = encolar_mails_clientes(mails, runtime=runtime, now=end)
        print(f"MAILS A CLIENTES ENCOLADOS: {n}/{len(mails)}")
    subject =(f"Miraron y no compraron: {len(report['no_compro'])} oportunidades - "
               f"{end.strftime('%Y-%m-%d')}")
    text, html = format_text(report), format_html(report)
    if args.dry_run:
        print(f"Para: {', '.join(to)}")
        print(f"Asunto: {subject}")
        print(text)
        return 0
    try:
        send_mail(subject, text, html, to)
    except Exception as exc:  # noqa: BLE001 - queda en el log del job
        print(f"ERROR ENVIANDO OPORTUNIDADES: {exc}")
        print(text)
        return 1
    print(f"OPORTUNIDADES ENVIADAS OK a {', '.join(to)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
