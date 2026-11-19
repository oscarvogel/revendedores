"""Resumen diario de lo que buscan y miran los clientes de Revendedores.

Cubre las dos fuentes que genera el portal:

- ``api_busqueda``: lo que escriben en el buscador (solo usuarios
  autenticados; ver ``ArticulosViewSet.list``). Es el "que buscan".
- ``api_consultaprecio``: cada clic en "Ver precio" (solo usuarios
  autenticados; el precio viene oculto salvo favoritos/staff, ver
  ``ArticuloSerializer.get_mostrar_precio``). Es el "que precios
  estuvieron mirando". Incluye a los usuarios sin ficha de cliente,
  porque la consulta se registra antes de validar el ``Cliente``.

Corre dentro del scheduler (usa ``modelos.ModeloBase.db_reventa`` del
legado, igual que ``stock_minimum.py``) y manda el mail con el SMTP de
``/run/secrets/informes-diarios.env`` (igual que ``resumen_diario.py``).

Uso:
    resumen_busquedas_precios.py                  # hoy 00:00 -> ahora, envia
    resumen_busquedas_precios.py --dry-run        # imprime, no envia
    resumen_busquedas_precios.py --date 2026-11-12 --dry-run
    resumen_busquedas_precios.py --to otro@ejemplo.com --dry-run
"""

from __future__ import annotations

import argparse
import os
import re
import smtplib
import sys
import time
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
UTC = timezone.utc

DEFAULT_TO = (
    "oscar@ferreteriaavenida.com.ar",
    "ventas@ferreteriaavenida.com.ar",
)
TOP_LIMIT = 20
TOP_USERS_LIMIT = 10
LEGACY_PATH = "/var/www/html/utiles"

_WS_RE = re.compile(r"\s+")


def normalize_query(query: Any) -> str:
    """Normaliza un texto de busqueda para agrupar (strip + espacios simples)."""
    return _WS_RE.sub(" ", str(query or "").strip())


def parse_date(value: str) -> datetime:
    """Fecha ``YYYY-MM-DD`` como medianoche de Argentina; error si es invalida."""
    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m-%d")
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"fecha invalida (se espera YYYY-MM-DD): {value!r}") from exc
    return parsed.replace(tzinfo=LOCAL_TZ)


def resolve_window(day: datetime, now: datetime | None = None) -> tuple[datetime, datetime]:
    """Ventana [inicio, fin): el dia completo, o hasta ahora si es hoy.

    Devuelve datetimes con tz de Argentina.
    """
    start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start + timedelta(days=1)
    now = now or datetime.now(LOCAL_TZ)
    return start, min(now, end_of_day)


def _load_runtime() -> dict[str, Any]:
    """Conexion a la base ``revendedores`` via el legado (sin creds en el repo)."""
    jobs_path = str(Path(__file__).resolve().parent)
    for path in (LEGACY_PATH, jobs_path):
        if path not in sys.path:
            sys.path.insert(0, path)

    original_argv = sys.argv
    original_cwd = os.getcwd()
    sys.argv = [original_argv[0] if original_argv else "resumen_busquedas_precios.py"]
    try:
        # libs.utiles parsea -i/-a al importar y resuelve fasa.ini
        # relativo al directorio del actualizador.
        os.chdir(LEGACY_PATH)
        from modelos.ModeloBase import db_reventa
    finally:
        sys.argv = original_argv
        os.chdir(original_cwd)

    def query(sql: str, params: tuple[Any, ...]) -> list[tuple[Any, ...]]:
        cursor = db_reventa.execute_sql(sql, params)
        return list(cursor.fetchall())

    def execute_batch(statements: list[tuple[str, tuple[Any, ...]]]) -> None:
        """Ejecuta varias sentencias en una sola transacción (todo o nada)."""
        with db_reventa.atomic():
            for sql, params in statements:
                db_reventa.execute_sql(sql, params)

    return {"query": query, "execute_batch": execute_batch}


def _fmt_dt_nosec(dt: datetime) -> str:
    local = dt.astimezone(LOCAL_TZ) if dt.tzinfo else dt.replace(tzinfo=UTC).astimezone(LOCAL_TZ)
    return local.strftime("%Y-%m-%d %H:%M")


def fetch_report(
    start: datetime,
    end: datetime,
    *,
    runtime: dict[str, Any],
    top_limit: int = TOP_LIMIT,
    top_users_limit: int = TOP_USERS_LIMIT,
) -> dict[str, Any]:
    """Agrega busquedas y consultas de precio en la ventana dada."""
    q = runtime["query"]
    start_s = start.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
    end_s = end.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")

    busq_total, busq_users, busq_terms = q(
        "SELECT COUNT(*), COUNT(DISTINCT user_id), COUNT(DISTINCT TRIM(query)) "
        "FROM api_busqueda WHERE timestamp >= %s AND timestamp < %s",
        (start_s, end_s),
    )[0]
    busq_top_raw = q(
        "SELECT TRIM(query), COUNT(*), COUNT(DISTINCT user_id) "
        "FROM api_busqueda WHERE timestamp >= %s AND timestamp < %s "
        "GROUP BY TRIM(query) ORDER BY COUNT(*) DESC LIMIT %s",
        (start_s, end_s, int(top_limit)),
    )
    busq_users_top = q(
        "SELECT au.username, COALESCE(ac.nombre, ''), COALESCE(ac.numero_cliente, ''), "
        "COUNT(*) FROM api_busqueda b "
        "JOIN auth_user au ON au.id = b.user_id "
        "LEFT JOIN api_cliente ac ON ac.user_id = au.id "
        "WHERE b.timestamp >= %s AND b.timestamp < %s "
        "GROUP BY au.username, ac.nombre, ac.numero_cliente "
        "ORDER BY COUNT(*) DESC LIMIT %s",
        (start_s, end_s, int(top_users_limit)),
    )

    cons_total, cons_arts, cons_users = q(
        "SELECT COUNT(*), COUNT(DISTINCT articulo_id), COUNT(DISTINCT usuario_id) "
        "FROM api_consultaprecio WHERE fecha_hora >= %s AND fecha_hora < %s",
        (start_s, end_s),
    )[0]
    cons_top_raw = q(
        "SELECT cp.articulo_id, COALESCE(ar.nombre, ''), COUNT(*), "
        "COUNT(DISTINCT cp.usuario_id) "
        "FROM api_consultaprecio cp "
        "LEFT JOIN api_articulos ar ON ar.clave = cp.articulo_id "
        "WHERE cp.fecha_hora >= %s AND cp.fecha_hora < %s "
        "GROUP BY cp.articulo_id, ar.nombre ORDER BY COUNT(*) DESC LIMIT %s",
        (start_s, end_s, int(top_limit)),
    )
    cons_users_top = q(
        "SELECT au.username, COALESCE(ac.nombre, ''), COALESCE(ac.numero_cliente, ''), "
        "COUNT(*), COUNT(DISTINCT cp.articulo_id) FROM api_consultaprecio cp "
        "JOIN auth_user au ON au.id = cp.usuario_id "
        "LEFT JOIN api_cliente ac ON ac.user_id = au.id "
        "WHERE cp.fecha_hora >= %s AND cp.fecha_hora < %s "
        "GROUP BY au.username, ac.nombre, ac.numero_cliente "
        "ORDER BY COUNT(*) DESC LIMIT %s",
        (start_s, end_s, int(top_users_limit)),
    )
    sin_cliente = q(
        "SELECT DISTINCT au.username FROM api_consultaprecio cp "
        "JOIN auth_user au ON au.id = cp.usuario_id "
        "LEFT JOIN api_cliente ac ON ac.user_id = au.id "
        "WHERE cp.fecha_hora >= %s AND cp.fecha_hora < %s AND ac.id IS NULL "
        "ORDER BY au.username LIMIT 50",
        (start_s, end_s),
    )

    return {
        "inicio": _fmt_dt_nosec(start),
        "fin": _fmt_dt_nosec(end),
        "busquedas": {
            "total": int(busq_total or 0),
            "usuarios": int(busq_users or 0),
            "terminos": int(busq_terms or 0),
            "top": [
                {"query": normalize_query(row[0]), "consultas": int(row[1]),
                 "usuarios": int(row[2])}
                for row in busq_top_raw
                if normalize_query(row[0])
            ],
            "top_usuarios": [
                {"username": str(row[0]), "cliente": str(row[1] or "").strip(),
                 "numero": str(row[2] or "").strip(), "consultas": int(row[3])}
                for row in busq_users_top
            ],
        },
        "precios": {
            "total": int(cons_total or 0),
            "articulos": int(cons_arts or 0),
            "usuarios": int(cons_users or 0),
            "top": [
                {"clave": str(row[0]).strip(), "nombre": str(row[1] or "").strip(),
                 "consultas": int(row[2]), "usuarios": int(row[3])}
                for row in cons_top_raw
            ],
            "top_usuarios": [
                {"username": str(row[0]), "cliente": str(row[1] or "").strip(),
                 "numero": str(row[2] or "").strip(), "consultas": int(row[3]),
                 "articulos": int(row[4])}
                for row in cons_users_top
            ],
            "sin_cliente": [str(row[0]) for row in sin_cliente],
        },
    }


def _cuantos(n: int, singular: str, plural: str) -> str:
    """Cantidad con sustantivo en singular/plural ("1 usuario", "3 usuarios")."""
    return f"{n} {singular if n == 1 else plural}"


def _user_label(entry: dict[str, Any]) -> str:
    if entry.get("numero") or entry.get("cliente"):
        return f"{entry['username']} ({entry.get('numero', '')} {entry.get('cliente', '')})".strip()
    return f"{entry['username']} (sin ficha de cliente)"


def format_text(report: dict[str, Any]) -> str:
    b, p = report["busquedas"], report["precios"]
    lines = [
        f"Qué buscan y miran los clientes - {report['inicio']} a {report['fin']} (Arg)",
        "=" * 60,
        "",
        f"BÚSQUEDAS: {_cuantos(b['total'], 'búsqueda', 'búsquedas')} "
        f"de {_cuantos(b['usuarios'], 'usuario', 'usuarios')} "
        f"({_cuantos(b['terminos'], 'término distinto', 'términos distintos')})",
    ]
    if b["top"]:
        lines.append("Top búsquedas:")
        for i, item in enumerate(b["top"], 1):
            lines.append(
                f"  {i:2d}. {item['query']} — "
                f"{_cuantos(item['consultas'], 'vez', 'veces')} "
                f"({_cuantos(item['usuarios'], 'usuario', 'usuarios')})"
            )
    else:
        lines.append("Sin búsquedas en el período.")
    if b["top_usuarios"]:
        lines.append("Quienes más buscaron:")
        for entry in b["top_usuarios"]:
            lines.append(
                f"  - {_user_label(entry)}: "
                f"{_cuantos(entry['consultas'], 'búsqueda', 'búsquedas')}"
            )
    lines += [
        "",
        f"VER PRECIO: {_cuantos(p['total'], 'clic', 'clics')} sobre "
        f"{_cuantos(p['articulos'], 'artículo', 'artículos')} "
        f"por {_cuantos(p['usuarios'], 'usuario', 'usuarios')}",
    ]
    if p["top"]:
        lines.append("Artículos más consultados:")
        for i, item in enumerate(p["top"], 1):
            lines.append(
                f"  {i:2d}. {item['clave']} {item['nombre']} — "
                f"{_cuantos(item['consultas'], 'vez', 'veces')} "
                f"({_cuantos(item['usuarios'], 'usuario', 'usuarios')})"
            )
    else:
        lines.append("Sin clics en Ver precio en el período.")
    if p["top_usuarios"]:
        lines.append("Quienes más precios miraron:")
        for entry in p["top_usuarios"]:
            lines.append(
                f"  - {_user_label(entry)}: "
                f"{_cuantos(entry['consultas'], 'clic', 'clics')} "
                f"en {_cuantos(entry['articulos'], 'artículo', 'artículos')}"
            )
    if p["sin_cliente"]:
        lines.append(
            "Usuarios SIN ficha de cliente que miraron precios: "
            + ", ".join(p["sin_cliente"])
        )
    return "\n".join(lines) + "\n"


def format_html(report: dict[str, Any]) -> str:
    b, p = report["busquedas"], report["precios"]

    def esc(value: Any) -> str:
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    busq_rows = "".join(
        f"<tr><td>{i}</td><td>{esc(item['query'])}</td>"
        f"<td>{item['consultas']}</td><td>{item['usuarios']}</td></tr>"
        for i, item in enumerate(b["top"], 1)
    ) or "<tr><td colspan='4'>Sin búsquedas en el período.</td></tr>"
    busq_users = "".join(
        f"<li>{esc(_user_label(e))}: {e['consultas']} búsquedas</li>"
        for e in b["top_usuarios"]
    )
    prec_rows = "".join(
        f"<tr><td>{i}</td><td>{esc(item['clave'])}</td>"
        f"<td>{esc(item['nombre'])}</td>"
        f"<td>{item['consultas']}</td><td>{item['usuarios']}</td></tr>"
        for i, item in enumerate(p["top"], 1)
    ) or "<tr><td colspan='5'>Sin clics en Ver precio en el período.</td></tr>"
    prec_users = "".join(
        f"<li>{esc(_user_label(e))}: {e['consultas']} clics "
        f"en {e['articulos']} artículos</li>"
        for e in p["top_usuarios"]
    )
    sin_cliente = (
        f"<p><strong>Usuarios SIN ficha de cliente que miraron precios:</strong> "
        f"{esc(', '.join(p['sin_cliente']))}</p>"
        if p["sin_cliente"] else ""
    )
    return f"""<html><body style="font-family:Arial,sans-serif;background:#f6f7f9;padding:20px">
<div style="max-width:760px;margin:auto;background:#fff;padding:24px;border-radius:8px">
<h2 style="color:#1565c0;margin-top:0">Qué buscan y miran los clientes</h2>
<p><strong>{esc(report['inicio'])} a {esc(report['fin'])} (Arg)</strong></p>
<h3>🔍 Búsquedas: {b['total']} de {b['usuarios']} usuarios ({b['terminos']} términos)</h3>
<table style="width:100%;border-collapse:collapse">
<tr><th style="text-align:left;background:#1565c0;color:#fff;padding:8px">#</th>
<th style="text-align:left;background:#1565c0;color:#fff;padding:8px">Búsqueda</th>
<th style="text-align:left;background:#1565c0;color:#fff;padding:8px">Veces</th>
<th style="text-align:left;background:#1565c0;color:#fff;padding:8px">Usuarios</th></tr>
{busq_rows}</table>
{f'<h4>Quienes más buscaron</h4><ul>{busq_users}</ul>' if busq_users else ''}
<h3>💲 Ver precio: {p['total']} clics sobre {p['articulos']} artículos ({p['usuarios']} usuarios)</h3>
<table style="width:100%;border-collapse:collapse">
<tr><th style="text-align:left;background:#1565c0;color:#fff;padding:8px">#</th>
<th style="text-align:left;background:#1565c0;color:#fff;padding:8px">Clave</th>
<th style="text-align:left;background:#1565c0;color:#fff;padding:8px">Artículo</th>
<th style="text-align:left;background:#1565c0;color:#fff;padding:8px">Clics</th>
<th style="text-align:left;background:#1565c0;color:#fff;padding:8px">Usuarios</th></tr>
{prec_rows}</table>
{f'<h4>Quienes más precios miraron</h4><ul>{prec_users}</ul>' if prec_users else ''}
{sin_cliente}
<p style="color:#777;font-size:12px;margin-top:24px">Generado automáticamente por automatizaciones 189.</p>
</div></body></html>"""


def send_mail(subject: str, text: str, html: str, to: list[str]) -> None:
    host = os.environ["SMTP_SERVER"]
    port = int(os.environ.get("SMTP_PORT", "465"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    sender = os.environ.get("SMTP_FROM") or os.environ.get("FROM_EMAIL") or user

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(to)
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    last: Exception | None = None
    for attempt in range(1, 4):
        server = None
        try:
            if port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=30)
            else:
                server = smtplib.SMTP(host, port, timeout=30)
                server.ehlo()
                if server.has_extn("starttls"):
                    server.starttls()
            server.login(user, password)
            server.sendmail(sender, to, msg.as_string())
            return
        except Exception as exc:  # noqa: BLE001 - reintento de red
            last = exc
            print(f"[reintento {attempt}/3] envio fallo: {exc}")
            if attempt < 3:
                time.sleep(15)
        finally:
            if server is not None:
                try:
                    server.quit()
                except Exception:  # noqa: BLE001 - cierre best-effort
                    pass
    raise RuntimeError(last)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resumen diario de búsquedas y Ver precio")
    parser.add_argument("--date", default=None,
                        help="día YYYY-MM-DD (default: hoy, Argentina)")
    parser.add_argument("--to", action="append", default=[],
                        help="destinatario extra (repite la opción)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        day = parse_date(args.date) if args.date else datetime.now(LOCAL_TZ)
    except ValueError as exc:
        parser.error(str(exc))
    start, end = resolve_window(day)
    label = start.strftime("%Y-%m-%d")

    to = list(args.to) if args.to else [
        e.strip() for e in os.environ.get("RESUMEN_TO", ",".join(DEFAULT_TO)).split(",")
        if e.strip()
    ]
    if not to:
        print("Sin destinatarios: definir RESUMEN_TO o --to", file=sys.stderr)
        return 2

    runtime = _load_runtime()
    report = fetch_report(start, end, runtime=runtime)
    subject = f"Qué buscan y miran los clientes - {label}"
    text, html = format_text(report), format_html(report)
    if args.dry_run:
        print(f"Para: {', '.join(to)}")
        print(f"Asunto: {subject}")
        print(text)
        return 0
    try:
        send_mail(subject, text, html, to)
    except Exception as exc:  # noqa: BLE001 - queda en el log del job
        print(f"ERROR ENVIANDO RESUMEN: {exc}")
        print(text)
        return 1
    print(f"RESUMEN ENVIADO OK a {', '.join(to)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
