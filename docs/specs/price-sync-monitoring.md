# Control de sincronización y diferencias de precios

## Objetivo

Mantener la base de Revendedores actualizada con los datos vigentes del ERP y avisar por WhatsApp antes de que una diferencia llegue al cliente. El control cubre cualquier cliente, condición, artículo y modalidad de entrega; no se limita al cliente 00591 ni al cemento.

## Situación observada

- En `fasa_189`, el cron activo del scheduler configura `actualiza_lista_reventa.189.sh` cada hora, al minuto 00. El log de la corrida 19:00 UTC terminó a las 19:06:26 UTC.
- Ese proceso contiene operaciones de escritura/actualización para artículos, bonificaciones, clientes, pesos, formas de pago y localidades.
- El log de las 19:00 contiene el `OperationalError: Connection already opened` esperado al intentar abrir una conexión Peewee que ya está activa durante bonificaciones. El bloque captura ese caso; el job sigue, registra `Actualización de bonificaciones completada`, informa 10.369 actualizados, 0 creados, 0 errores y termina con `exit_code=0`. El monitor acepta solo este patrón acotado cuando todos esos marcadores aparecen.
- El actualizador sí guarda los cuatro campos calculados `pblret1`, `pblrep1`, `pblret4` y `pblrep4` en `api_articulos` de Revendedores. El monitor los vuelve a leer después de liberar el lock y compara lo persistido contra VFP.
- Un cron de actualización frecuente anterior se retiró por saturación del host; el diseño conserva el actualizador horario existente y evita lanzar un segundo barrido pesado frecuente.
- El dry-run completo del 2026-11-02 leyó de vuelta los cuatro campos base para 11.804 artículos (47.216 campos) y comparó 704.960 precios finales en aproximadamente 3 minutos. Identificó 789 artículos de Revendedores sin fila correspondiente en `Stock`; los registra como condición incompleta y alerta agregada, no como precio correcto.
- La referencia ERP hacía búsquedas ORM repetidas de forma de pago, localidad, Stock e IVA por caso. El monitor ahora cachea las lecturas por ID durante cada proceso. También normaliza a `Decimal` el flete `0.00` que `Reparto` devuelve como `float` cuando un artículo no tiene tipo de reparto; esto evita el `TypeError` antes de aplicar IVA.
- Los mensajes se agrupan para WhatsApp, pero el estado deduplica por caso estable (artículo/campo o cliente/artículo/modalidad). Los canarios rotativos conservan casos no incluidos en esa tanda; el barrido completo es el que puede confirmar que un caso desapareció.

## Flujo propuesto

1. El actualizador vigente sigue sincronizando los datos del ERP hacia Revendedores con la frecuencia configurada actualmente; no se agrega otro escritor masivo.
2. Una vez finalizada la ejecución y liberado el lock, un control lee de nuevo los datos persistidos en Revendedores y compara el precio web para retiro y reparto contra una referencia calculada desde los datos fuente del ERP. La referencia reproduce la rutina local: el `PrecioBase` trae fletes y costos fijos del artículo; `PrecioPublico` calcula el flete de reparto, aplica recargo/descuento al artículo y suma luego el flete con IVA.
3. Cada 2 horas se comprueba un conjunto canario representativo, incluyendo entrega/retiro y condiciones distintas. El canario solo informa “correcto” después de confirmar que la sincronización escribió en la base y que la lectura devuelve los valores esperados.
4. Durante la ventana nocturna se recorre el universo completo en lotes acotados, con límites de carga y tiempo, registro de progreso y bloqueo para impedir solapamientos.
5. Se envía WhatsApp ante fallo de actualización, fallo al leer la base, precio persistido distinto de la referencia o barrido incompleto. Los avisos se deduplican por clave del caso y se repiten solo si cambia el estado o persiste más allá del umbral configurado.

## Reglas de seguridad operativa

- No declarar sincronización exitosa por el código de salida solamente: validar que no haya errores en el log y leer de vuelta valores persistidos. Si hay un error pero la base aún se puede consultar, el monitor igual compara los datos persistidos y avisa ambos hallazgos; el resultado permanece no saludable.
- Si la fuente ERP falla, detener esa tanda sin sobrescribir precios con cero o valores parciales.
- Usar lotes y transacciones acotadas; guardar checkpoint para reanudar el barrido nocturno.
- Ejecutar el barrido nocturno con baja prioridad y detenerlo ante carga elevada o demora fuera de límite.
- Reusar el mecanismo de WhatsApp ya instalado en las automatizaciones; no guardar credenciales en el repositorio ni en el documento.
- No duplicar el actualizador horario hasta determinar si el trabajo existente cubre los precios calculados para retiro y reparto.

## Verificación de aceptación

1. Un caso de prueba de cliente/condición/artículo con flete verifica el orden de cálculo local y web para retiro y reparto.
2. Tras la sincronización, una lectura directa de la base Revendedores confirma los valores calculados persistidos.
3. Un fallo de escritura o una discrepancia produce un único aviso WhatsApp con cliente, condición, artículo, modalidad, valor de referencia y valor persistido; evitar datos personales innecesarios.
4. Una segunda ejecución sin cambios no duplica avisos.
5. El barrido completo informa cantidades verificadas, diferencias, errores y estado de finalización, y puede reanudarse sin duplicar trabajo.
6. La prueba en producción se habilita gradualmente después de una ejecución en modo observación y de verificar el consumo de recursos.

## Estado de activación

La implementación y las pruebas locales están hechas. El canario y el barrido completo en producción se ejecutaron en `dry-run`; no se enviaron WhatsApp reales. El canario verificó 44 campos y 30 casos y encontró 8 artículos sin Stock en su selección. El barrido completo verificó 47.216 campos y 704.960 casos, encontró 789 artículos sin Stock y finalizó en aproximadamente 3 minutos. No detectó otras diferencias de precio. Las tareas programadas se habilitaron únicamente en `automatizaciones-scheduler`; el control permanecerá incompleto y avisará los artículos que falten hasta reconciliarlos.

## Detalles confirmados durante el relevamiento

- El cron productivo inspeccionado ejecuta `actualiza_lista_reventa.189.sh` cada hora (`0 * * * *`). El proceso llama `ActualizaListaReventa.py` y guarda en `ArticulosReventa` los valores `pblret1`, `pblrep1`, `pblret4` y `pblrep4`, además de los datos de artículos. El nuevo chequeo debe leer esos cuatro valores después del job.
- El comparador heredado `comparar_precios_reventa.py` solo contrasta `precio1`/`precio4` entre `stock` y `api_articulos`; no compara retiro/reparto calculados, no envía WhatsApp y no está programado en el cron actual.
- La referencia local disponible es `libs.Facturacion.Calculaprecio`, con `PrecioBase` y `PrecioPublico`. El emisor que usa la automatización de informes ya expone `destinatarios(env)` y `enviar(texto, telefono, env, dry_run)`.
- El monitor se ejecutará en el contenedor scheduler, después del job vigente y con su lock como barrera. Así consulta los valores ya persistidos en Revendedores y no agrega un segundo proceso de actualización masiva.
- En la imagen productiva, el sender está en el volumen persistente `/data/jobs/resumen_dashboard_whatsapp.py`; el archivo de configuración está en `/data/env/alertas-whatsapp.env`. El módulo no forma parte del contexto de build, por eso el monitor añade `/data/jobs` a `sys.path` y usa esa ruta predeterminada sin copiar el secreto.
- Los logs recientes tienen excepciones de base de datos en la etapa de bonificaciones; el monitor debe tratar una ejecución incompleta como estado de error, aunque haya escrito artículos, y no anunciar verde.
