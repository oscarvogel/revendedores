# Pedidos del portal — plan de implementación

**Objetivo:** permitir solicitudes revisadas por Ventas y cargadas manualmente en ERP.
**Base:** d9ee2f9, copia aislada; no modificar producción.
**Diseño aprobado:** carrito por usuario; precios validados en servidor según modalidad y condición; solicitud sin pago ni reserva; estados desde pendiente hasta entrega o cancelación; avisos visibles y prueba integral.

- [ ] Validar precios, cantidades, empresa y artículos en checkout; conservar el cálculo comercial compartido y probar alteración de precio y cambios de modalidad.
- [ ] Implementar estados y controles de Ventas y cliente sin cambiar el significado de pedidos históricos.
- [ ] Aislar carrito por identidad y actualizar precios al revisar; evitar duplicación en reintentos.
- [ ] Mostrar datos y resultado de notificaciones; verificar gestión y reenvío.
- [ ] Ejecutar pruebas locales relevantes, build y revisar límites de sincronización y despliegue.
