from decimal import Decimal

from api.models import BonificacionCliente, FormaPago


def calcular_precio_articulo(
    *,
    articulo,
    cliente,
    modalidad="retira",
    con_impuestos=True,
    condicion_pago_id=None,
    forma_pago=None,
    bonificaciones_cliente=None,
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

    precio_final = precio_base

    if modalidad == "reparto":
        if articulo.tiporeparto == "T":
            flete = cliente.codigo_localidad.fletetn1 if cliente.lista_precio == "1" else cliente.codigo_localidad.fletetn4
            flete = flete / Decimal("1000") * articulo.peso if flete else Decimal("0")
        elif articulo.tiporeparto == "P":
            flete = cliente.codigo_localidad.fletep1 if cliente.lista_precio == "1" else cliente.codigo_localidad.fletep4
            flete = precio_final * flete / Decimal("100") if flete else Decimal("0")

    # El flete forma parte de la base antes de aplicar bonificaciones y condición de pago.
    precio_final += flete

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

            if forma_pago.descuento > 0:
                precio_final *= (Decimal("1") - forma_pago.descuento / Decimal("100"))
            if forma_pago.punitorio > 0:
                precio_final *= (Decimal("1") + forma_pago.punitorio / Decimal("100"))
        except FormaPago.DoesNotExist:
            pass

    if con_impuestos:
        precio_final *= (Decimal("1") + articulo.iva / Decimal("100"))

    return round(precio_final, 2)
