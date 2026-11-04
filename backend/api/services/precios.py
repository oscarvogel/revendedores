import re
from decimal import Decimal, ROUND_HALF_UP

from django.core.cache import cache
from django.db import connections

from api.models import Articulos, BonificacionCliente, FormaPago


_ERP_PRECIOS_ARTICULO_CACHE_KEY = "api:precios:base-articulo:v3"
_FORMULA_PRECIO_RE = re.compile(r"^([*/+-])\s*(\d+(?:\.\d*)?|\.\d+)$")


def _aplicar_formula_precio(precio, formula):
    """Evalúa el sufijo aritmético que usa VFP en stock.FORMU."""
    formula = str(formula or "").strip()
    if not formula:
        return precio

    coincidencia = _FORMULA_PRECIO_RE.fullmatch(formula)
    if not coincidencia:
        return None

    operador, operando = coincidencia.groups()
    operando = Decimal(operando)
    if operador == "/":
        return precio / operando if operando else None
    if operador == "*":
        return precio * operando
    if operador == "+":
        return precio + operando
    return precio - operando


def _bases_erp_desde_fuente(fuente, *, formula=None, formula_activa=False):
    """Reconstruye las bases de ambas listas desde una fila base del ERP."""
    if Decimal(str(fuente.get("precio_prod") or 0)) != 0:
        return {}

    precio_pro = Decimal(str(fuente.get("precio_pro") or 0))
    formula = str(fuente.get("formula", "") if formula is None else formula).strip()
    if formula_activa and formula:
        precio_pro = _aplicar_formula_precio(precio_pro, formula)
        if precio_pro is None:
            return {}

    peso = Decimal(str(fuente.get("peso") or 0))
    precio_stock = Decimal(str(fuente.get("precio_stock") or 0))
    fijo_retira = Decimal(str(fuente.get("fijo_retira_costo") or 0))
    fijo_retira += (
        precio_stock
        * Decimal(str(fuente.get("fijo_retira_porcentaje") or 0))
        / 100
    )
    fijo_reparto = Decimal(str(fuente.get("fijo_reparto_costo") or 0))
    fijo_reparto += (
        precio_stock
        * Decimal(str(fuente.get("fijo_reparto_porcentaje") or 0))
        / 100
    )

    bases = {}
    for lista, incremento in (("1", fuente.get("incre1")), ("4", fuente.get("incre4"))):
        if str(fuente.get("fporcen") or "").strip():
            porcentaje = fuente.get("porcentaje1" if lista == "1" else "porcentaje4")
            flete_interno = precio_pro * Decimal(str(porcentaje or 0)) / 100
        elif str(fuente.get("fsuma") or "").strip():
            flete_interno = Decimal(
                str(fuente.get("fsum1" if lista == "1" else "fsum4") or 0)
            )
        elif str(fuente.get("fmulti") or "").strip():
            precio_flete = fuente.get("fmulti1" if lista == "1" else "fmulti4")
            flete_interno = Decimal(str(precio_flete or 0)) * peso
        elif str(fuente.get("fpbulto") or "").strip():
            flete_interno = Decimal(str(fuente.get("fpbulto_precio") or 0))
        else:
            flete_interno = Decimal("0")

        base_sin_incremento = precio_pro + flete_interno
        incremento = Decimal(str(incremento or 0))
        descdiscont = Decimal(
            str(fuente.get("descdiscont1" if lista == "1" else "descdiscont4") or 0)
        )
        precio_fijo = {
            "retira": fijo_retira,
            "reparto": fijo_reparto,
        }
        bases[lista] = {
            modalidad: base_sin_incremento * (Decimal("1") + incremento / 100) + fijo
            for modalidad, fijo in precio_fijo.items()
        }
        bases[lista].update(
            {
                f"{modalidad}_discontinuado": (
                    base_sin_incremento
                    * (Decimal("1") + (incremento - descdiscont) / 100)
                    + fijo
                )
                for modalidad, fijo in precio_fijo.items()
            }
        )
    return bases


def _precios_base_erp():
    """Carga las bases e impuestos que PrecioBase calcula desde el ERP."""
    if connections["fasa"].vendor == "sqlite":
        return {}

    def cargar():
        raices_variantes = {
            str(clave).strip()[:7]
            for clave in Articulos.objects.values_list("clave", flat=True)
            if len(str(clave).strip()) == 8
        }
        with connections["fasa"].cursor() as cursor:
            cursor.execute(
                """
                SELECT stock.CLAVE,
                       stock.PRECIOPRO,
                       stock.PRECIOPROD,
                       stock.FPORCEN,
                       stock.FSUMA,
                       stock.FMULTI,
                       stock.FPBULTO,
                       stock.FORMU,
                       stock.INCRE1,
                       stock.INCRE4,
                       stock.PESO,
                       stock.TIPOIMP,
                       COALESCE(impuesto.PORCENTAJE, 0),
                       COALESCE(fporcien.PORCENTAJE1, 0),
                       COALESCE(fporcien.PORCENTAJE4, 0),
                       COALESCE(fsum.PRECIO1, 0),
                       COALESCE(fsum.PRECIO4, 0),
                       COALESCE(fmulti.PRECIO1, 0),
                       COALESCE(fmulti.PRECIO4, 0),
                       COALESCE(fpbulto.PRECIO, 0),
                       stock.PRECIO,
                       COALESCE(cfijos.retira_costo, 0),
                       COALESCE(cfijos.retira_porcentaje, 0),
                       COALESCE(cfijos.reparto_costo, 0),
                       COALESCE(cfijos.reparto_porcentaje, 0),
                       COALESCE((SELECT MAX(com.descdiscont)
                                   FROM comisiones AS com
                                  WHERE com.lista = '1'
                                    AND com.margen = stock.INCRE1), 0),
                       COALESCE((SELECT MAX(com.descdiscont)
                                   FROM comisiones AS com
                                  WHERE com.lista = '4'
                                    AND com.margen = stock.INCRE4), 0)
                  FROM stock
             LEFT JOIN impuesto ON impuesto.CODIGO = stock.TIPOIMP
             LEFT JOIN fporcien ON fporcien.CODIGO = stock.FPORCEN
             LEFT JOIN fporkg AS fsum ON fsum.CODIGO = stock.FSUMA
             LEFT JOIN fporkg AS fmulti ON fmulti.CODIGO = stock.FMULTI
             LEFT JOIN fpbulto ON fpbulto.CODIGO = stock.FPBULTO
             LEFT JOIN (
                   SELECT cFijoxProd.idArtXMed,
                          SUM(CASE WHEN cfijo1.retira = 1 THEN cfijo1.costo ELSE 0 END) AS retira_costo,
                          SUM(CASE WHEN cfijo1.retira = 1 THEN cfijo1.porcentaje ELSE 0 END) AS retira_porcentaje,
                          SUM(CASE WHEN cfijo1.reparto = 1 THEN cfijo1.costo ELSE 0 END) AS reparto_costo,
                          SUM(CASE WHEN cfijo1.reparto = 1 THEN cfijo1.porcentaje ELSE 0 END) AS reparto_porcentaje
                     FROM cFijoxProd
                     JOIN cfijo1 ON cfijo1.codigo = cFijoxProd.cfijo
                 GROUP BY cFijoxProd.idArtXMed
             ) AS cfijos ON cfijos.idArtXMed = stock.idArtXMed
                """
            )
            datos = {}
            for row in cursor.fetchall():
                (
                    clave,
                    precio_pro,
                    precio_prod,
                    fporcen,
                    fsuma,
                    fmulti,
                    fpbulto,
                    formula,
                    incre1,
                    incre4,
                    peso,
                    tipoimp,
                    impuesto,
                    porcentaje1,
                    porcentaje4,
                    fsum1,
                    fsum4,
                    fmulti1,
                    fmulti4,
                    fpbulto_precio,
                    precio_stock,
                    fijo_retira_costo,
                    fijo_retira_porcentaje,
                    fijo_reparto_costo,
                    fijo_reparto_porcentaje,
                    descdiscont1,
                    descdiscont4,
                ) = row

                impuesto = Decimal(str(impuesto or 0))
                clave_texto = str(clave).strip()
                fuente = {
                    "precio_pro": precio_pro,
                    "precio_prod": precio_prod,
                    "fporcen": fporcen,
                    "fsuma": fsuma,
                    "fmulti": fmulti,
                    "fpbulto": fpbulto,
                    "formula": formula,
                    "incre1": incre1,
                    "incre4": incre4,
                    "peso": peso,
                    "porcentaje1": porcentaje1,
                    "porcentaje4": porcentaje4,
                    "fsum1": fsum1,
                    "fsum4": fsum4,
                    "fmulti1": fmulti1,
                    "fmulti4": fmulti4,
                    "fpbulto_precio": fpbulto_precio,
                    "precio_stock": precio_stock,
                    "fijo_retira_costo": fijo_retira_costo,
                    "fijo_retira_porcentaje": fijo_retira_porcentaje,
                    "fijo_reparto_costo": fijo_reparto_costo,
                    "fijo_reparto_porcentaje": fijo_reparto_porcentaje,
                    "descdiscont1": descdiscont1,
                    "descdiscont4": descdiscont4,
                }
                formula_activa = len(clave_texto) >= 8 and bool(clave_texto[7])
                precio_base_por_lista = _bases_erp_desde_fuente(
                    fuente,
                    formula_activa=formula_activa,
                )

                datos[str(clave).strip()] = {
                    "bases": precio_base_por_lista,
                    "impuesto": impuesto,
                    "fuente": (
                        {**fuente, "impuesto": impuesto}
                        if clave_texto in raices_variantes
                        else None
                    ),
                }
            return datos

    return cache.get_or_set(_ERP_PRECIOS_ARTICULO_CACHE_KEY, cargar, timeout=300)


def calcular_precio_articulo(
    *,
    articulo,
    cliente,
    modalidad="retira",
    con_impuestos=True,
    condicion_pago_id=None,
    forma_pago=None,
    bonificaciones_cliente=None,
    impuesto_adicional=None,
    erp_precios=None,
):
    """Calcula el precio comercial vigente para un articulo y cliente."""
    flete = Decimal("0")
    lista_precio = cliente.lista_precio

    if lista_precio == "1":
        precio_base = articulo.pblret1 if modalidad == "retira" else articulo.pblrep1
    elif lista_precio == "4":
        precio_base = articulo.pblret4 if modalidad == "retira" else articulo.pblrep4
    else:
        precio_base = articulo.pblret1

    if erp_precios is None:
        erp_precios = _precios_base_erp()
    clave_articulo = str(articulo.clave).strip()
    erp_datos = erp_precios.get(clave_articulo, {})
    if not erp_datos.get("bases") and len(clave_articulo) == 8:
        raiz = erp_precios.get(clave_articulo[:7], {})
        fuente = raiz.get("fuente")
        if fuente:
            bases_variante = _bases_erp_desde_fuente(
                fuente,
                formula=getattr(articulo, "formula", ""),
                formula_activa=bool(clave_articulo[7]),
            )
            if bases_variante:
                erp_datos = {
                    "bases": bases_variante,
                    "impuesto": fuente.get("impuesto", Decimal("0")),
                }
    if impuesto_adicional is None:
        impuesto_adicional = erp_datos.get("impuesto", Decimal("0"))
    else:
        impuesto_adicional = Decimal(str(impuesto_adicional))
    if str(articulo.clave).startswith("F"):
        # VFP usa el precio guardado directamente para esos artículos; ese
        # precio ya incluye el impuesto comercial.
        impuesto_adicional = Decimal("0")

    precio_base_erp = erp_datos.get("bases", {}).get(cliente.lista_precio)
    if isinstance(precio_base_erp, dict):
        es_discontinuado = (
            str(articulo.discontinuado or "").strip().upper() in {"S", "Y", "1", "T"}
        )
        clave_base = f"{modalidad}_discontinuado" if es_discontinuado else modalidad
        precio_base_erp = precio_base_erp.get(clave_base)
    es_precio_especial = str(articulo.clave).startswith("F")
    if precio_base_erp is not None and not es_precio_especial:
        precio_base = precio_base_erp

    # VFP PrecioBase agrega el impuesto comercial (DEV_IMP) al precio del
    # producto antes de aplicar la condición de pago y el IVA general.
    precio_final = (
        precio_base * (Decimal("1") + impuesto_adicional / Decimal("100"))
    ).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

    if modalidad == "reparto":
        if articulo.tiporeparto == "T":
            flete = cliente.codigo_localidad.fletetn1 if cliente.lista_precio == "1" else cliente.codigo_localidad.fletetn4
            flete = flete / Decimal("1000") * articulo.peso if flete else Decimal("0")
        elif articulo.tiporeparto == "P":
            flete = cliente.codigo_localidad.fletep1 if cliente.lista_precio == "1" else cliente.codigo_localidad.fletep4
            flete = precio_final * flete / Decimal("100") if flete else Decimal("0")

    if condicion_pago_id or forma_pago is not None:
        try:
            if forma_pago is None:
                forma_pago = FormaPago.objects.get(id=condicion_pago_id)

            if bonificaciones_cliente is None:
                bonificacion = BonificacionCliente.objects.filter(
                    cliente=cliente,
                    desde_articulo__lte=articulo.clave,
                    hasta_articulo__gte=articulo.clave,
                ).first()
            else:
                bonificacion = next(
                    (
                        item
                        for item in bonificaciones_cliente
                        if item.desde_articulo <= articulo.clave <= item.hasta_articulo
                    ),
                    None,
                )

            if bonificacion:
                precio_final *= (Decimal("1") - bonificacion.bonificacion / Decimal("100"))

            precio_final += precio_final * (
                forma_pago.punitorio - forma_pago.descuento
            ) / Decimal("100")
        except FormaPago.DoesNotExist:
            pass

    # El ERP aplica el descuento/recargo al artículo y suma después el flete
    # de reparto. El flete no recibe la condición de pago del renglón.
    if con_impuestos:
        precio_final *= (Decimal("1") + articulo.iva / Decimal("100"))
        flete *= Decimal("1") + articulo.iva / Decimal("100")

    precio_final += flete

    return precio_final.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
