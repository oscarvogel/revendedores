# Descarga de comprobantes generados por FASA ERP

El backend del portal llama a `POST /api/v1/documents/invoices/by-reference` en FASA ERP. El navegador sólo descarga la respuesta del backend del portal; el token multisistema y el payload fiscal no se exponen al cliente.

## Variables nuevas del backend Revendedores

- `ERP_DOCUMENT_RENDER_URL`: URL completa de la ruta de integración en ERP.
- `ERP_DOCUMENT_API_TOKEN`: token bearer de un cliente API ERP autorizado con `documents:render`.
- `ERP_DOCUMENT_TIMEOUT`: timeout HTTP en segundos (opcional; default `15`, rango `1` a `60`).

Configurar estos valores en el entorno del proceso Django/Gunicorn, nunca en Vite, archivos públicos, logs, URL de parámetros ni respuestas al navegador. No se agrega ni se versiona un `.env` con credenciales.

El portal ya usa `EMPRESA_ID`; ese valor identifica la empresa para la consulta de cuenta corriente y para la referencia enviada al ERP.

## Configuración requerida en FASA ERP

Agregar al secreto `DOCUMENT_API_CLIENTS_JSON` un cliente habilitado para Revendedores con:

- `client_id`: identificador `revendedores`.
- `token`: el mismo valor configurado como `ERP_DOCUMENT_API_TOKEN` en el backend del portal.
- `allowed_company_ids`: sólo las empresas que el portal puede consultar.
- `scopes`: incluir `documents:render`.

La ruta acepta `company_id`, `customer_code`, `document_type` e `invoice_number`. Resuelve el movimiento desde las tablas canónicas del ERP; no acepta ni usa un `idmovi` enviado por el portal.

Se exponen tipos `F`, `C` y `D` porque el servicio existente del ERP ya contempla factura, nota de crédito y nota de débito. El portal verifica pertenencia contra la cuenta corriente del cliente autenticado antes de invocar el ERP, que vuelve a validar empresa, cliente y referencia.

## Comportamiento de errores

- Comprobante inexistente, ambiguo o ajeno al cliente: `404` con mensaje genérico.
- Rechazo fiscal del ERP: `422` con una explicación segura.
- Credenciales/allowlist inválidas, timeout, respuesta no PDF o ERP no disponible: `503` genérico.
- PDF: `application/pdf`, descarga adjunta y `Cache-Control: private, no-store`.

## Validación antes de habilitar

Configurar los secretos primero en ambos backends de prueba. Validar una factura, una nota de crédito y una nota de débito autorizadas; una referencia inexistente; dos clientes distintos; dos empresas, incluida una fuera de allowlist; y un comprobante sin autorización fiscal. El navegador debe recibir sólo el PDF o un mensaje seguro, nunca el token.

