from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from rest_framework import serializers


CANTIDAD_QUANT = Decimal('0.001')


def validar_cantidad_articulo(articulo, cantidad):
    """Valida y normaliza una cantidad de pedido a 3 decimales.

    Para artículos tipo A con mts2 informado, la cantidad representa m² y debe
    corresponder a cajas completas (múltiplos exactos de mts2).
    """
    try:
        cantidad = Decimal(str(cantidad)).quantize(CANTIDAD_QUANT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise serializers.ValidationError('Cantidad inválida.') from exc

    if cantidad <= 0:
        raise serializers.ValidationError('La cantidad debe ser mayor que cero.')

    campoa1 = (articulo.campoa1 or '').lower()
    mts2 = Decimal(str(articulo.mts2 or 0)).quantize(CANTIDAD_QUANT, rounding=ROUND_HALF_UP)
    if campoa1 == 'a' and mts2 > 0:
        if cantidad < mts2:
            raise serializers.ValidationError(
                f'La cantidad mínima para {articulo.clave} es {mts2} m² (1 caja).'
  )
        cajas = cantidad / mts2
        if cajas != cajas.to_integral_value():
            raise serializers.ValidationError(
                f'La cantidad debe ser múltiplo de {mts2} m² por caja.'
            )

    return cantidad
