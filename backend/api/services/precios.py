from decimal import Decimal, ROUND_HALF_UP

from django.core.cache import cache
from django.db import connections

from api.models import BonificacionCliente, FormaPago


_ERP_PRECIOS_ARTICULO_CACHE_KEY = "api:precios:base-articulo:v1"


def _precios_base_erp():
    """Carga las bases e impuestos que PrecioBase calcula desde el ERP."""
    if connections["fasa"].vendor == "sqlite":
        return {}

    def cargar():
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
                       (SELECT COUNT(*)
                          FROM cFijoxProd
                         WHERE cFijoxProd.idArtXMed = stock.idArtXMed)
                  FROM stock
             LEFT JOIN impuesto ON impuesto.CODIGO = stock.TIPOIMP
             LEFT JOIN fporcien ON fporcien.CODIGO = stock.FPORCEN
             LEFT JOIN fporkg AS fsum ON fsum.CODIGO = stock.FSUMA
             LEFT JOIN fporkg AS fmulti ON fmulti.CODIGO = stock.FMULTI
             LEFT JOIN fpbulto ON fpbulto.CODIGO = stock.FPBULTO
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
                    componentes_fijos,
                ) = row

                precio_pro = Decimal(str(precio_pro or 0))
                peso = Decimal(str(peso or 0))
                impuesto = Decimal(str(impuesto or 0))
                precio_base_por_lista = {}

                # PrecioBase usa estas fuentes de flete en este orden. Los
                # artículos con precio en moneda extranjera, fórmula o costos
                # fijos quedan con el precio publicado, porque requieren reglas
                # adicionales del ERP.
                soportado = not (
                    Decimal(str(precio_prod or 0)) != 0
                    or str(formula or "").strip()
                    or int(componentes_fijos or 0) > 0
                )
                if soportado:
                    for lista, incremento in (("1", incre1), ("4", incre4)):
                        if str(fporcen or "").strip():
                            porcentaje = porcentaje1 if lista == "1" else porcentaje4
                            flete_interno = precio_pro * Decimal(str(porcentaje or 0)) / 100
                        elif str(fsuma or "").strip():
                            flete_interno = Decimal(str(fsum1 if lista == "1" else fsum4))
                        elif str(fmulti or "").strip():
                            precio_flete = fmulti1 if lista == "1" else fmulti4
                            flete_interno = Decimal(str(precio_flete or 0)) * peso
                        elif str(fpbulto or "").strip():
                            flete_interno = Decimal(str(fpbulto_precio or 0))
                        else:
                            flete_interno = Decimal("0")

                        base = precio_pro + flete_interno
                        base += base * Decimal(str(incremento or 0)) / 100
                        precio_base_por_lista[lista] = base

                datos[str(clave).strip()] = {
                    "bases": precio_base_por_lista,
                    "impuesto": impuesto,
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

    erp_datos = _precios_base_erp().get(str(articulo.clave).strip(), {})
    if impuesto_adicional is None:
        impuesto_adicional = erp_datos.get("impuesto", Decimal("0"))
    else:
        impuesto_adicional = Decimal(str(impuesto_adicional))
    if str(articulo.clave).startswith("F"):
        # VFP usa el precio guardado directamente para esos artículos; ese
        # precio ya incluye el impuesto comercial.
        impuesto_adicional = Decimal("0")

    precio_base_erp = erp_datos.get("bases", {}).get(cliente.lista_precio)
    es_precio_especial = (
        str(articulo.clave).startswith("F")
        or str(articulo.discontinuado or "").strip().upper() in {"S", "Y", "1", "T"}
    )
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
