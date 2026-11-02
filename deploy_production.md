# Deploy de Producción — `ventas.ferreteriaavenida.com.ar`

> **Stack actual: Coolify sobre `fasa_189` (192.168.0.189).**
> Ver la sección **[0. Setup actual y procedimiento de deploy](#0-setup-actual-y-procedimiento-de-deploy-coolify--fasa_189)**.
>
> La sección 1 documenta el setup **anterior** (`fasa_195` + nginx/systemd), que
> **ya no está en uso**: las imágenes hoy se construyen en el server y se
> despliegan vía la API de Coolify.

>
> **Dominio:** `https://ventas.ferreteriaavenida.com.ar`
> **Rama canónica:** `main`
> **Servidor:** `fasa_189` (192.168.0.189) — usuario `fasa`, key `~/.ssh/id_ed25519`
> **Panel Coolify:** `https://coolify.vogelconsultoria.com.ar`

---

## 0. Setup actual y procedimiento de deploy (Coolify / fasa_189)

### 0.1 Topología

```
Internet
  └── coolify-proxy (Traefik v3.6)
        └── frontend-1ezipmojg…   (nginx:alpine, imagen fasa-revendedores-frontend:staging)
              ├── /            → /usr/share/nginx/html  (SPA Vue compilada)
              └── /api/, /media/, /static/, /admin/, /t/  → http://backend:8000
                    └── backend-1ezipmojg…  (gunicorn, imagen fasa-revendedores-backend:staging-env2)
                          └── MySQL externo  192.168.0.150:3306   (DB `revendedores` + `fasa`)
```

> El contenedor `mysql` del compose **no** es el que usa la app: el backend
> conecta al MySQL **externo** `192.168.0.150:3306` (definido en
> `/srv/fasa-data/data/revendedores/.env.docker`).

### 0.2 Componentes y paths en el server

| Qué | Dónde |
|---|---|
| Source del proyecto | `/srv/fasa-data/compose/revendedores-src/` (**no es un repo git**) |
| Compose de Coolify | `/srv/fasa-data/compose/revendedores-coolify.compose.yml` |
| Secrets / env del backend | `/srv/fasa-data/data/revendedores/.env.docker` → montado como `/run/secrets/revendedores.env` |
| Media y logs (volumes) | `/srv/fasa-data/data/revendedores/{media,logs}` |
| Registry local de imágenes | `127.0.0.1:5000` (`registry:2` en el host) |
| Imagen backend | `127.0.0.1:5000/fasa-revendedores-backend:staging-env2` |
| Imagen frontend | `127.0.0.1:5000/fasa-revendedores-frontend:staging` |
| Dockerfile backend | `revendedores-src/staging/Dockerfile.revendedores.backend` |
| Dockerfile frontend | `revendedores-src/docker/Dockerfile.frontend` |

**IDs de Coolify** (para la API):

| Recurso | UUID |
|---|---|
| Proyecto | `l0h5euhntsennj8llc1t1f99` |
| Entorno `production` | `fiztusoqxra9y9toj29ibt9y` |
| Servicio (compose) | `1ezipmojg3zemckxlug8ndjv` |
| Sub-aplicación backend | `suoalpnbt3xhmsppgrwzzdea` |
| Sub-aplicación frontend | `qeqfukgjmxwecbvdagxffqnm` |

> El servicio se llama `revendedores-staging` **pero sirve el dominio de
> producción** y vive en el entorno `production`. El nombre es engañoso.

### 0.3 Procedimiento de deploy

Las imágenes **no** se construyen en Coolify: se construyen en el server y se
pushean al registry local. La secuencia completa es:

**1. Mergear a `main`** (los deploys salen de `main`).

**2. Sincronizar el source en el server** (el source no es un repo git):

```bash
ssh fasa_189
BUILD=/tmp/revend-build
git clone --depth 1 --branch main https://github.com/sistemas-fasa/revendedores.git $BUILD
# …o actualizar un clone existente:
git -C $BUILD fetch --depth 1 origin main && git -C $BUILD checkout -q FETCH_HEAD

SRC=/srv/fasa-data/compose/revendedores-src
# backup antes de tocar nada
tar czf /tmp/revendedores-src-backup-$(date +%Y%m%d-%H%M%S).tar.gz \
  -C /srv/fasa-data/compose revendedores-src/backend revendedores-src/frontend/src

chmod -R u+w $SRC/backend $SRC/frontend/src $SRC/docker $SRC/staging $SRC/scripts
rsync -a --exclude '__pycache__' --exclude '*.pyc' --exclude '.pytest_cache' \
  $BUILD/backend/ $SRC/backend/
rsync -a --exclude '__pycache__' $BUILD/frontend/src/ $SRC/frontend/src/
rsync -a $BUILD/docker/nginx/ $SRC/docker/nginx/
rsync -a $BUILD/staging/ $SRC/staging/
rsync -a $BUILD/scripts/ $SRC/scripts/
chmod +x $SRC/scripts/*.sh
cp -f $BUILD/frontend/{package.json,package-lock.json,vite.config.ts,index.html} $SRC/frontend/
```

> ⚠️ El `rsync` de `docker/nginx/` **es obligatorio**: `docker/Dockerfile.frontend`
> hace `COPY docker/nginx/default.conf /etc/nginx/conf.d/default.conf`, así que
> la config de nginx queda horneada en la imagen. Sin este sync, los cambios en
> `docker/nginx/default.conf` **nunca llegan a producción** (y el build usa
> silenciosamente la conf vieja que quedó en el server).
>
> El `rsync` de `staging/` también es obligatorio: el build del backend usa
> `staging/Dockerfile.revendedores.backend`, que copia
> `staging/revendedores-entrypoint.sh` (el que carga el env del secret y corre
> `collectstatic`). Si no se sincroniza, el build usa el entrypoint viejo que
> quedó en el server.
>
> El `rsync` de `scripts/` es lo que deja el script de cron en el path que
> usa el crontab (ver 0.11). El `chmod +x` es necesario porque el checkout en
> Windows no preserva el bit de ejecución: en git los dos `.sh` están
> marcados como `100755`, pero el `rsync` desde el clone de Linux ya llega con
> el permiso, y el `chmod` queda como red de seguridad.
>
> `chmod -R u+w` incluye `$SRC/docker` porque en el server ese árbol es
> read-only (`dr-xr-sr-x`) y `rsync` necesita permiso de escritura en el
> directorio para reemplazar el archivo.


**3. Construir y pushear las imágenes:**

```bash
cd $SRC
docker build -f staging/Dockerfile.revendedores.backend \
  -t 127.0.0.1:5000/fasa-revendedores-backend:staging-env2 .
docker build -f docker/Dockerfile.frontend \
  -t 127.0.0.1:5000/fasa-revendedores-frontend:staging .
docker push 127.0.0.1:5000/fasa-revendedores-backend:staging-env2
docker push 127.0.0.1:5000/fasa-revendedores-frontend:staging
```

**4. Redeploy vía la API de Coolify** (solo las apps que cambiaron; MySQL no se toca):

```bash
TOKEN='<token de la API de Coolify>'
BASE=https://coolify.vogelconsultoria.com.ar/api/v1
SVC=1ezipmojg3zemckxlug8ndjv

curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "$BASE/services/$SVC/applications/suoalpnbt3xhmsppgrwzzdea/start?latest=true&force=true"
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "$BASE/services/$SVC/applications/qeqfukgjmxwecbvdagxffqnm/start?latest=true&force=true"
```

### 0.4 Verificación post-deploy

```bash
# 1. Las imágenes nuevas están corriendo
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}' | grep 1ezipmojg
docker inspect -f '{{.Image}}' backend-1ezipmojg3zemckxlug8ndjv

# 2. El fix está dentro del contenedor
docker exec backend-1ezipmojg3zemckxlug8ndjv grep -c FechaContableField /app/api/models.py

# 3. La API responde (usar el Host real: si no, 400 por ALLOWED_HOSTS)
curl -s -H "Host: ventas.ferreteriaavenida.com.ar" \
  "http://<ip-backend>:8000/api/comprobantes/" -H "Authorization: Bearer <jwt>"

# 4. Sin errores nuevos en el log
docker logs --since 10m backend-1ezipmojg3zemckxlug8ndjv | grep -iE "Traceback|Error"
```

Para los comandos que corren Django dentro del contenedor hay que usar el
entrypoint, porque es el que carga `/run/secrets/revendedores.env`:

```bash
docker exec backend-1ezipmojg… revendedores-entrypoint python manage.py shell -c "…"
```

### 0.5 Rollback

El digest anterior queda registrado en el registry. Para volver atrás:

1. `docker pull 127.0.0.1:5000/fasa-revendedores-backend@sha256:<digest-anterior>`
2. Reetiquetar el tag al digest viejo:
   `docker tag 127.0.0.1:5000/fasa-revendedores-backend@sha256:<anterior> 127.0.0.1:5000/fasa-revendedores-backend:staging-env2`
3. `docker push` del tag y redeploy con `?latest=true`.

También hay backups del source en `/tmp/revendedores-src-backup-*.tar.gz`.

### 0.6 Gotchas

- **`restart` NO hace pull.** `POST …/applications/{uuid}/restart` reinicia el
  contenedor con la imagen **local vieja**. Para tomar la imagen nueva del
  registry hay que usar `POST …/applications/{uuid}/start?latest=true&force=true`.
- **El source del server tiene código que NO está en git.** El feature bot
  (`api/services/bot_*.py`, `api/bot_views.py`, migraciones 0027/0028/0031)
  vive **solo en el server**. Por eso el `rsync` **no debe usar `--delete`**:
  se perdería ese código. Verificá que sigue presente después del sync.
- **El source no es un repo git**: los cambios se sincronizan con `rsync`
  desde un clone de `main`, no con `git pull`.
- **`docker exec` no carga el env**: sin el entrypoint, Django falla con
  `SECRET_KEY not found`.
- **`ALLOWED_HOSTS`**: al curls directo contra el contenedor hay que mandar
  `-H "Host: ventas.ferreteriaavenida.com.ar"`, si no responde 400.
- **El service deploy completo** (`POST /services/{uuid}/start`) devuelve 400
  si el servicio ya está `running`. Para redeployar se va por aplicación.
- **La API de Coolify 4.4.6 está rota para TODOS los tokens** (verificado
  2026-10-20): `app/Models/PersonalAccessToken.php` define `casts()` como
  **método**, y eso pisa la propiedad `$casts` de Sanctum
  (`'abilities' => 'json'`). Entonces `abilities` queda como **string** y
  `tokenCan()` revienta con
  `in_array(): Argument #2 ($haystack) must be of type array, string given`
  → la API responde **500** (no 401), así que el token parece válido pero no
  funciona. No hay token en el panel que sirva: en `personal_access_tokens` el
  campo `token` es un **hash sha256**, no el texto plano.
  **Workaround sin API:** recrear el contenedor con el compose efectivo que
  Coolify ya genera (tiene las labels de traefik adentro), ver 0.7.

### 0.7 Redeploy sin la API de Coolify (compose efectivo)

Coolify genera un compose final **con las labels de traefik ya inyectadas**.
Ese archivo es el que hay que usar para recrear un contenedor a mano:

```bash
# 1. Copiar el compose efectivo + su .env a un directorio accesible
docker exec coolify cat /var/www/html/storage/app/services/1ezipmojg3zemckxlug8ndjv/docker-compose.yml > /tmp/rev/docker-compose.yml
docker exec coolify cat /var/www/html/storage/app/services/1ezipmojg3zemckxlug8ndjv/.env > /tmp/rev/.env

# 2. Recrear SOLO el frontend con la imagen nueva del registry
cd /tmp/rev && docker compose up -d --no-deps --force-recreate frontend
```

> **No usar** `docker compose` con `/srv/fasa-data/compose/revendedores-coolify.compose.yml`
> (el que está en el repo): ese no tiene las labels de traefik, y recrear el
> contenedor con él **deja el sitio sin ruta y sin HTTPS**.
>
> `docker compose up` recrea el contenedor con el **mismo nombre**
> (`frontend-1ezipmojg3zemckxlug8ndjv`), así que Coolify sigue viéndolo
> running y no se rompe el estado.
>
> Alternativa sin recrear nada, para cambios **solo de nginx**: copiar la conf
> al contenedor y recargar, sin downtime ni recrear:
>
> ```bash
> docker cp /tmp/rev/default.conf frontend-1ezipmojg3zemckxlug8ndjv:/etc/nginx/conf.d/default.conf
> docker exec frontend-1ezipmojg3zemckxlug8ndjv nginx -s reload
> ```
>
> Esto **no** es permanente: la próxima vez que se recree el contenedor vuelve
> la conf vieja. Por eso hay que pushear la imagen igual.


### 0.8 Imágenes de productos: case del filesystem y archivos faltantes

Las imágenes de productos se sirven desde `/media/` → backend → Django
(`Articulos.imagen`). Hay **dos problemas distintos** que se ven igual en el
navegador (el texto alternativo en vez de la foto):

**1. Case de la extensión (arreglado).** La importación del ERP dejó
referencias con la extensión en mayúscula (`002.534.PNG`, `COR.000.jpg`)
mientras que el archivo en disco está en minúscula (`002.534.png`,
`cor.000.jpg`). En Linux el filesystem es case-sensitive, así que esas URLs
daban 404.

Se corrige con un comando, **no con una migración**: el grafo de migraciones
del server tiene hojas que solo existen en producción (`0028_rename_botconversation_indexes`,
`0031_merge_20260821_1033`), así que agregar una migración nueva en el repo
genera un segundo nodo hoja y `manage.py migrate` falla con *"Conflicting
migrations detected"*.

```bash
# Ver qué haría, sin tocar nada
docker exec backend-1ezipmojg… revendedores-entrypoint \
  python manage.py normalizar_imagenes --dry-run

# Aplicar
docker exec backend-1ezipmojg… revendedores-entrypoint \
  python manage.py normalizar_imagenes
```

> **Correrlo después de cada importación del ERP**, que es lo que introduce
> el case incorrecto. El comando es idempotente.
>
> El comando compara contra el listado exacto del directorio (`os.listdir`), no
> contra `os.path.exists`, porque en Windows `exists()` es case-insensitive y
> el resultado sería distinto según el sistema.

**2. Archivos que directamente no existen (sin resolver).** Hay referencias en
la DB a imágenes que no están en `MEDIA_ROOT` ni en mayúscula ni en minúscula.
Aproximadamente **570 referencias (~570 artículos)** al momento de esta
documentación. Estas **no** se pueden arreglar desde la app: hay que copiar
el archivo al `media/` del server o corregir el dato en el ERP.

```bash
# Listar las que faltan (el comando las reporta al final)
docker exec backend-1ezipmojg… revendedores-entrypoint \
  python manage.py normalizar_imagenes --dry-run
```


### 0.9 `/static/`: el CSS del admin de Django

El admin de Django (`/admin/`) llegaba **sin CSS**: sin estilos, todo en HTML
crudo. El backend corre bajo gunicorn, y **gunicorn no sirve archivos
estáticos** (el server de estáticos de Django es solo para desarrollo).

Había dos problemas encadenados:

1. `STATIC_URL = 'static/'` (sin barra inicial) → Django generaba URLs
   **relativas** (`static/admin/css/base.css`), que desde `/admin/` resuelven a
   `/admin/static/...` → 404.
2. No había nadie que sirviera `/static/`: el nginx del frontend lo manda al
   backend, y el backend no lo servía.

La solución es **WhiteNoise** (middleware que sirve los estáticos desde el
propio proceso, con gzip/brotli y cache headers):

- `backend/requirements.txt`: `whitenoise==6.12.0`
- `backend/backend/settings.py`: `STATIC_URL = '/static/'` (con barra) y el
  bloque `STORAGES` con `whitenoise.storage.CompressedStaticFilesStorage`
- `backend/backend/settings.py`: `'whitenoise.middleware.WhiteNoiseMiddleware'`
  en `MIDDLEWARE`, después de `SecurityMiddleware`
- `staging/revendedores-entrypoint.sh`: corre `manage.py collectstatic
  --noinput` **antes** de levantar gunicorn, para poblar `/app/staticfiles`

> Se usa la variante **sin manifest** a propósito: `ManifestStaticFilesStorage`
> hace fallar el `collectstatic` si algún template referencia un archivo que no
> existe, y eso abortaría el arranque del container.
>
> Si el `collectstatic` falla, el entrypoint **no aborta**: loguea el error y
> sigue levantando gunicorn. Es preferible un backend sin CSS que un backend
> caído.

Verificar:

```bash
# El CSS del admin tiene que dar 200 y content-type de CSS
curl -sI https://ventas.ferreteriaavenida.com.ar/static/admin/css/base.css | head -5
# El HTML del admin tiene que apuntar a /static/ (no a una ruta relativa)
curl -s https://ventas.ferreteriaavenida.com.ar/admin/login/ | grep -o 'href="[^"]*base\.css[^"]*"'
```

> **Gotcha:** `backend/static/` existe en el server (163 archivos: el CSS/JS del
> admin y el de DRF) pero **no está versionado en git**. Por eso
> `STATICFILES_DIRS` apunta a un directorio inexistente cuando se construye la
> imagen desde git puro: Django loguea el warning `W004` y sigue. No es
> bloqueante, pero es la razón de que el admin se vea distinto si se compara
> con el server. Si alguna vez se versiona, ese warning desaparece.

> **Gotcha (service worker):** la PWA de revendedores tiene un service worker
> que sirve el `index.html` de la SPA en **toda navegación**
> (`NavigationRoute` con `createHandlerBoundToURL("index.html")`). Con eso,
> abrir `/admin/` en el navegador devolvía la SPA en vez del admin de Django,
> aunque el CSS ya sirviera. Por eso `frontend/vite.config.ts` tiene:
>
> - `navigateFallbackDenylist: [/^\/admin\//, /^\/health\//]` → esas rutas no
>   usan el fallback y van a la red
> - una regla `NetworkOnly` (`no-cache-backend`) para `/admin/` y `/health/`,
>   **antes** de la regla same-origin `NetworkFirst` (en Workbox gana la
>   primera que matchea, y la same-origin matchea todo)
>
> Con eso el admin abre con estilos y el health check nunca se sirve de un
> caché viejo. Si se cambia la config del PWA, hay que **rebuildear y
> redeployar el frontend**: el service worker se regenera en el build.


### 0.10 `/health/`: el health check público

Había dos confusiones:

- `/health/` **no** estaba expuesto en el dominio público: caía en el
  `location /` del nginx del frontend y devolvía el `index.html` de la SPA con
  **HTTP 200**. Un monitor que chequea solo el status code daba **falso
  positivo**: el backend podía estar caído y el chequeo pasaba igual.
- `/api/health/` devolvía **404** de Django, porque la ruta real es `/health/`
  (ver `backend/backend/urls.py`).

Ahora el nginx del frontend tiene un match exacto:

```nginx
location = /health/ {
    proxy_pass http://backend:8000/health/;
    proxy_set_header Host $host;
    access_log off;
}
```

El `=` (match exacto) gana sobre cualquier otra location, así que esta
request nunca cae en la SPA. Y el backend devuelve JSON:

```json
{"status": "ok", "service": "ventas-ferreteria", "database": "ok", "version": "…", "time": "…"}
```

El chequeo incluye un `SELECT 1` contra la base, así que un 200 con
`"status": "ok"` significa que **el backend y la base** están respondiendo.
Un 500 con `"database": "error"` significa que el backend está vivo pero la
base no.

```bash
curl -s https://ventas.ferreteriaavenida.com.ar/health/
```


### 0.11 Automatizar la normalización de imágenes (cron)

La importación del ERP corre en otro host (`192.168.0.150`, `debian-fasa`) y
**no hay acceso SSH** a esa máquina, así que no se puede enganchar un hook al
importador. La automatización se hace con un **cron en el server de la app**:
el comando es idempotente y tarda ~4 segundos, así que correrlo cada 30
minutos es barato y cubre cualquier importación.

El script está versionado en `scripts/normalizar-imagenes-cron.sh` (se
sincroniza al server con el `rsync` del paso 2 de 0.3). Instalar en el host
`fasa_189`, usuario `fasa`:

```bash
SRC=/srv/fasa-data/compose/revendedores-src

crontab -l 2>/dev/null | grep -v 'normalizar-imagenes-cron.sh' > /tmp/cron.txt || true
echo "*/30 * * * * sh $SRC/scripts/normalizar-imagenes-cron.sh" >> /tmp/cron.txt
crontab /tmp/cron.txt

# Verificar
crontab -l
```

> El crontab invoca el script con `sh` explícito: así no depende del bit de
> ejecución del archivo en el disco.

Log: `/srv/fasa-data/data/revendedores/logs/normalizar-imagenes.log`.

El script resuelve el nombre del contenedor **en cada corrida** (el sufijo lo
genera Coolify), y si el backend no está corriendo lo saltea sin error.


### 0.12 Monitor de precios Revendedores (solo `automatizaciones-scheduler`)

El contenedor del scheduler se construye desde dos ubicaciones distintas:

- Compose y Dockerfile: `/srv/fasa-data/compose/automations/automatizaciones/`.
- Contexto real del build: `/srv/fasa-data/automation-src/automatizaciones/`.
- Estado persistente y scripts de WhatsApp: `/srv/fasa-data/data/automatizaciones/`, montado como `/data`.

El checkout de automatizaciones del server tiene cambios locales ajenos al
monitor. Para este deploy no sincronizar el repositorio completo, no hacer
`git reset` y no usar `rsync --delete`: copiar únicamente el nuevo script y
añadir sus líneas al `cron.disabled` del contexto de build. El sender existente
está en `/data/jobs/resumen_dashboard_whatsapp.py`; su configuración permanece
en `/data/env/alertas-whatsapp.env` y no se copia ni imprime.

El actualizador de Revendedores ya escribe los cuatro campos `pblret1`,
`pblrep1`, `pblret4` y `pblrep4`. En el cron productivo inspeccionado está
programado cada hora al minuto 00 y usa `/data/locks/actualiza_lista_reventa_cron.lock`.
El monitor solo lee esos valores después de la actualización. Sus canarios
corren cada dos horas al minuto 15; el barrido completo está previsto a las
03:10. Ambos usan un único lock y los logs quedan bajo
`/data/logs/linux/price_sync_monitor/`.

#### Deploy por etapas

Mantener una sesión SSH abierta en `fasa_189` durante los pasos del host; así
se conserva `STAMP` para ambas imágenes. Ejecutar los comandos marcados
**PowerShell local** desde el worktree del monitor.

1. Guardar la imagen actualmente ejecutada como rollback y respaldar los dos
   archivos que se tocarán en el source persistente:

```bash
CTX=/srv/fasa-data/automation-src/automatizaciones
COMPOSE=/srv/fasa-data/compose/automations/automatizaciones
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP=/srv/fasa-data/backups/automatizaciones/price-sync-monitor-$STAMP
mkdir -p "$BACKUP"
CURRENT_IMAGE=$(docker inspect --format '{{.Image}}' automatizaciones-scheduler-cw05ffwv7jkgaaazm9qq9xp2)
docker image tag "$CURRENT_IMAGE" local/automatizaciones:rollback-price-monitor-$STAMP
cp -a "$CTX/cron.disabled" "$BACKUP/cron.disabled"
if [ -e "$CTX/jobs/price_sync_monitor.py" ]; then
  cp -a "$CTX/jobs/price_sync_monitor.py" "$BACKUP/price_sync_monitor.py"
fi
```

2. Copiar solo `price_sync_monitor.py` a `$CTX/jobs/` y agregar las dos
   entradas de `ops/automatizaciones/price_sync_monitor.cron` al final de
   `$CTX/cron.disabled`, sin reemplazar su contenido. El checkout de origen
   tiene cambios locales; conservarlos.

   Para evitar hornear esos otros cambios en producción, construir un overlay
   del contenedor actual. Copiar el cron activo desde la imagen actual; primero
   se prueba el script sin las nuevas entradas:

```powershell
scp ops/automatizaciones/price_sync_monitor.py fasa_189:/tmp/price_sync_monitor.py
scp ops/automatizaciones/Dockerfile.price-monitor fasa_189:/tmp/price-monitor-Dockerfile
```

Dentro de la sesión SSH abierta en el servidor:

```bash
install -m 0644 /tmp/price_sync_monitor.py "$CTX/jobs/price_sync_monitor.py"
docker cp automatizaciones-scheduler-cw05ffwv7jkgaaazm9qq9xp2:/etc/cron.d/automatizaciones /tmp/price-sync-cron.base
mkdir -p /tmp/price-monitor-overlay
cp /tmp/price-sync-cron.base /tmp/price-monitor-overlay/cron.disabled
cp "$CTX/jobs/price_sync_monitor.py" /tmp/price-monitor-overlay/price_sync_monitor.py
cp /tmp/price-monitor-Dockerfile /tmp/price-monitor-overlay/Dockerfile
cd "$COMPOSE"
docker build -f /tmp/price-monitor-overlay/Dockerfile \
  --build-arg BASE_IMAGE=local/automatizaciones:rollback-price-monitor-$STAMP \
  -t local/automatizaciones:price-monitor-dryrun-$STAMP /tmp/price-monitor-overlay
AUTOMATIZACIONES_IMAGE_TAG=price-monitor-dryrun-$STAMP \
  docker compose --profile scheduler up -d --no-deps --force-recreate automatizaciones-scheduler
```

3. Correr manualmente el canario de observación; no envía WhatsApp:

```bash
docker exec automatizaciones-scheduler-cw05ffwv7jkgaaazm9qq9xp2 \
  python3 /opt/automatizaciones/jobs/price_sync_monitor.py --mode canary --dry-run
```

Revisar el JSON (`complete`, cantidades comprobadas, estado de sincronización,
alertas pendientes y fallos de notificación). El monitor acepta el `OperationalError:
Connection already opened` de bonificaciones solo cuando también constan la etapa
completada, 10.369 filas actualizadas, cero errores y `exit_code=0`. El canario
puede seguir como `incomplete` cuando encuentra artículos de Revendedores sin
registro en Stock ERP; debe preparar la alerta y no marcar el control como verde.

El dry-run completo del 2026-11-02 verificó 47.216 campos base y 704.960 casos
de precio en aproximadamente 3 minutos. Encontró 789 artículos de Revendedores
sin fila correspondiente en `Stock`; esta condición queda informada y mantiene
el resultado incompleto hasta que se reconcilien esos artículos. No detectó
diferencias adicionales de precio ni envió WhatsApp real. El límite interno de
45 minutos y la ventana hasta la siguiente actualización horaria siguen vigentes.

4. Solo tras revisar el canario, preparar el cron overlay con las líneas nuevas
   y recrear únicamente el scheduler:

```powershell
scp ops/automatizaciones/price_sync_monitor.cron fasa_189:/tmp/price_sync_monitor.cron
```

Dentro de la misma sesión SSH abierta en el servidor:

```bash
sed -i 's/\r$//' /tmp/price_sync_monitor.cron
if ! grep -q 'JOB_NAME=price_sync_monitor_canary' "$CTX/cron.disabled"; then
  cat /tmp/price_sync_monitor.cron >> "$CTX/cron.disabled"
fi
if ! grep -q 'JOB_NAME=price_sync_monitor_canary' /tmp/price-monitor-overlay/cron.disabled; then
  cat /tmp/price_sync_monitor.cron >> /tmp/price-monitor-overlay/cron.disabled
fi
docker build -f /tmp/price-monitor-overlay/Dockerfile \
  --build-arg BASE_IMAGE=local/automatizaciones:rollback-price-monitor-$STAMP \
  -t local/automatizaciones:price-monitor-live-$STAMP /tmp/price-monitor-overlay
AUTOMATIZACIONES_IMAGE_TAG=price-monitor-live-$STAMP \
  docker compose --profile scheduler up -d --no-deps --force-recreate automatizaciones-scheduler
```

5. Verificar la salud, la imagen nueva, el cron cargado en
   `/etc/cron.d/automatizaciones`, y los logs canary/full. Para rollback,
   ejecutar `docker compose --profile scheduler up -d --no-deps
   --force-recreate automatizaciones-scheduler` con
   `AUTOMATIZACIONES_IMAGE_TAG=rollback-price-monitor-$STAMP`.

**Despliegue ejecutado el 2026-11-02:** `local/automatizaciones:price-monitor-live-20261102-183904` quedó `running/healthy`; se confirmaron ambos cron y los directorios persistentes de logs/lock. El canario posterior verificó 44 campos y 30 casos en `dry-run`, con 8 artículos sin fila en Stock; no envió mensajes reales. El barrido completo de observación verificó 47.216 campos y 704.960 precios válidos, encontró 789 artículos sin fila en Stock y tardó cerca de 3 minutos. El backup de source/cron está en `/srv/fasa-data/backups/automatizaciones/price-sync-monitor-20261102-183904`; la imagen anterior quedó etiquetada `local/automatizaciones:rollback-price-monitor-20261102-183904`. Solo se recreó `automatizaciones-scheduler`. La primera entrega real de WhatsApp depende de la próxima ejecución cron.


---

## 1. Setup anterior (fasa_195 + nginx/systemd) — histórico, ya no vigente

> ⚠️ **Este setup ya no está en uso.** La producción migró a Coolify sobre
> `fasa_189` (ver sección 0). Se conserva como referencia histórica.

### 1.0 Topología de producción

### 1.1 Servicios activos

| Servicio | Mecanismo | Puerto | Origen / config |
|---|---|---|---|
| **Frontend** (Vue estático) | nginx (host) sirve archivos | `443` (`80` redirige a `443`) | `/var/www/html/reventa/frontend/` (build output) — config en `/etc/nginx/sites-enabled/ventas` |
| **Backend** (Django + gunicorn) | systemd (`reventa.service`) | `127.0.0.1:8088` | `/var/www/html/reventa/backend/` con `backend.backend.wsgi`; venv `/var/www/html/reventa/venv` |
| **MySQL** | servidor externo | `192.168.0.150:3306` | DB `revendedores` + `fasa` (legado ERP) |

nginx hace de reverse proxy: `https://ventas.ferreteriaavenida.com.ar/api/* → http://127.0.0.1:8088`.

### 1.2 Stack Docker de pruebas (NO TOCAR en deploy de producción)

| Servicio | Contenedor | Puerto |
|---|---|---|
| MySQL | `revendedores-mysql` | `3307` |
| Backend | `revendedores-backend` | `18089` |
| Frontend | `revendedores-frontend` | `15173` |

> Este stack se usa para validar cambios antes de pasarlos a producción. **No
> comparte datos** con producción (DB local en `docker_mysql_data`, config en
> `docker/.env.docker`). El deploy de producción **no toca** este stack.

### 1.3 Volúmenes / paths protegidos (no se sobrescriben en deploy de prod)

| Path | Contenido | Notas |
|---|---|---|
| `/var/www/html/reventa/backend/.env` | Config Django prod (DB, email, OpenRouter) | **NO TOCAR** salvo cambio explícito aprobado |
| `/var/www/html/reventa/venv/` | Python venv (lo usa `reventa.service`) | Solo actualizar si cambia `requirements.txt` |
| `/var/www/html/reventa/logs/gunicorn.log` | Log del backend prod | Rotación a definir |
| `/var/www/html/reventa/sockets/` | (vacío) | — |
| `/var/www/html/reventa/_backup_codex/` | Backups antiguos | — |
| `/var/www/html/reventa/docker/` | Config del stack Docker de pruebas | Solo se toca en deploys de **pruebas** |
| `/var/www/html/reventa/frontend/dist/` | Salida del último `npm run build` | Se usa como fuente para copiar al root nginx |
| `192.168.0.150:3306` | MySQL externo | **NO TOCAR** estructura, sí se pueden correr migrations |

### 1.4 Permisos clave

```
/var/www/html/reventa                  root:www-data       777
/var/www/html/reventa/frontend         administracion:...  777
/var/www/html/reventa/frontend/src     ferreteria:...      555  ← sin write
/var/www/html/reventa/backend          root:www-data       777
/var/www/html/reventa/backend/api      root:www-data       777
/var/www/html/reventa/venv             root:www-data       777
```

> **Permisos reales (verificado 2026-08-21):** aunque `backend/` es `777`,
> los subdirectorios (`api/`, `api/migrations/`, `api/services/`, etc.) están
>owned por `root:www-data` y `ferreteria` **NO puede hacer `chmod`** en ellos.
> Los .py files dentro sí son owned por `ferreteria` y se pueden sobrescribir.
> Los directorios nuevos (ej: `api/tests/`) en `555` impiden crear archivos.

---

## 2. Cómo hacer deploy (paso a paso real)

> Este es el procedimiento **real tal como se ejecutó** el 2026-08-21.
> Incluye los workarounds que funcionaron.

### 2.1 Pre-flight local

```bash
# Rama correcta
git branch --show-current   # debe decir: ui-venta-rapida

# Actualizar
git fetch origin
git pull --ff-only origin ui-venta-rapida

# Verificar qué cambió
git log --oneline --since="<fecha_ultimo_deploy>" ui-venta-rapida
git diff <commit_anterior>..HEAD --name-only
```

### 2.2 Backup en el server (siempre antes de tocar algo)

```bash
ssh fasa_195 'cd /var/www/html/reventa && \
  tar czf /tmp/backend_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
    backend/api backend/backend backend/graficos backend/manage.py backend/requirements.txt && \
  tar czf /tmp/frontend_src_backup_$(date +%Y%m%d_%H%M%S).tar.gz \
    frontend/src frontend/index.html frontend/package.json frontend/package-lock.json \
    frontend/vite.config.ts frontend/tailwind.config.js frontend/tsconfig.json frontend/.eslintrc.cjs'
```

### 2.3 Sync BACKEND (método que funciona)

**NO usar rsync desde Windows** (no funciona bien con UNC paths). Usar **tar local + scp + extract**:

```powershell
# 1. Crear carpeta temporal
$tmpDir = "C:\Users\Ventas\AppData\Local\Temp\opencode\reventa_deploy\backend"
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null

# 2. Copiar archivos (robocopy excluyendo migraciones, venv, __pycache__)
robocopy "\\pc-oscar\programacion\web\revendedores\backend\api" "$tmpDir\api" /E /XD migrations __pycache__ | Out-Null
robocopy "\\pc-oscar\programacion\web\revendedores\backend\backend" "$tmpDir\backend" /E /XD __pycache__ | Out-Null
robocopy "\\pc-oscar\programacion\web\revendedores\backend\graficos" "$tmpDir\graficos" /E /XD __pycache__ | Out-Null
Copy-Item "\\pc-oscar\programacion\web\revendedores\backend\manage.py" "$tmpDir\manage.py" -Force
Copy-Item "\\pc-oscar\programacion\web\revendedores\backend\requirements.txt" "$tmpDir\requirements.txt" -Force

# 3. Tar y subir
tar -czf "$tmpDir\..\backend_code.tar.gz" -C "$tmpDir\.." backend
scp "$tmpDir\..\backend_code.tar.gz" "ferreteria@fasa_195:/tmp/backend_code.tar.gz"
```

En el server:

```bash
# 4. Extraer (ignorar errores de permisos en directorios — los .py SÍ se copian)
ssh fasa_195 'cd /var/www/html/reventa && \
  tar xzf /tmp/backend_code.tar.gz --strip-components=1 -C backend/ \
    backend/api backend/backend backend/graficos backend/manage.py backend/requirements.txt'
```

> **Nota:** el `tar` muestra errores como "No se puede efectuar utime" y
> "No se puede cambiar el modo" — son por permisos de directorios. Los
> archivos .py SÍ se extraen correctamente. Verificar después con `head`
> en los archivos clave.

### 2.4 Sync MIGRACIONES

Las migraciones se sync por separado porque se excluyen del tar principal:

```powershell
# Local: copiar migraciones nuevas a carpeta temporal
$migDir = "C:\Users\Ventas\AppData\Local\Temp\opencode\reventa_deploy\migrations"
Copy-Item "\\pc-oscar\programacion\web\revendedores\backend\api\migrations\0027_pedido_*.py" "$migDir\" -Force
Copy-Item "\\pc-oscar\programacion\web\revendedores\backend\api\migrations\0028_alter_*.py" "$migDir\" -Force
Copy-Item "\\pc-oscar\programacion\web\revendedores\backend\api\migrations\0029_*.py" "$migDir\" -Force
Copy-Item "\\pc-oscar\programacion\web\revendedores\backend\api\migrations\0030_*.py" "$migDir\" -Force

# Tar y subir
tar -czf "$migDir\..\migrations.tar.gz" -C $migDir .
scp "$migDir\..\migrations.tar.gz" "ferreteria@fasa_195:/tmp/migrations.tar.gz"
```

En el server:

```bash
# Extraer a carpeta temporal y copiar (por permisos del directorio migrations)
ssh fasa_195 'mkdir -p /tmp/mig_extract && cd /tmp/mig_extract && \
  tar xzf /tmp/migrations.tar.gz && \
  cp *.py /var/www/html/reventa/backend/api/migrations/'
```

### 2.5 Aplicar migraciones

```bash
ssh fasa_195 'cd /var/www/html/reventa/backend && \
  ../venv/bin/python manage.py migrate --noinput 2>&1'
```

> Si hay ramas de migración sin merge (error "multiple leaf nodes"), crear
> migración merge primero:
> ```bash
> ssh fasa_195 'cd /var/www/html/reventa/backend && \
>   ../venv/bin/python manage.py makemigrations --merge --noinput'
> ```

### 2.6 Sync FRONTEND fuente + build

```powershell
# 1. Copiar source files
$tmpDir = "C:\Users\Ventas\AppData\Local\Temp\opencode\reventa_deploy\frontend"
$src = "\\pc-oscar\programacion\web\revendedores\frontend"
robocopy "$src\src" "$tmpDir\src" /E | Out-Null
Copy-Item "$src\package.json" "$tmpDir\" -Force
Copy-Item "$src\package-lock.json" "$tmpDir\" -Force
Copy-Item "$src\vite.config.ts" "$tmpDir\" -Force
Copy-Item "$src\tailwind.config.js" "$tmpDir\" -Force
Copy-Item "$src\tsconfig.json" "$tmpDir\" -Force
Copy-Item "$src\.eslintrc.cjs" "$tmpDir\" -Force
Copy-Item "$src\index.html" "$tmpDir\" -Force

# 2. Tar y subir
tar -czf "$tmpDir\..\frontend_source.tar.gz" -C "$tmpDir\.." frontend
scp "$tmpDir\..\frontend_source.tar.gz" "ferreteria@fasa_195:/tmp/frontend_source.tar.gz"
```

En el server:

```bash
# 3. Extraer
ssh fasa_195 'cd /var/www/html/reventa && \
  tar xzf /tmp/frontend_source.tar.gz --strip-components=1 -C frontend/ \
    frontend/src frontend/index.html frontend/package.json frontend/package-lock.json \
    frontend/vite.config.ts frontend/tailwind.config.js frontend/tsconfig.json frontend/.eslintrc.cjs'

# 4. Build
ssh fasa_195 'cd /var/www/html/reventa/frontend && \
  npm install --legacy-peer-deps && npm run build'

# 5. Publicar (copiar dist/* al root de nginx)
ssh fasa_195 'cd /var/www/html/reventa/frontend && cp -r dist/* .'
```

### 2.7 Reiniciar gunicorn

**Opción A — systemctl (requiere sudo):**

```bash
ssh fasa_195 'sudo systemctl restart reventa'
# Te va a pedir la contraseña de ferreteria
```

**Opción B — HUP signal (sin sudo, si ya tenés la sesión SSH):**

```bash
ssh fasa_195 'kill -HUP $(pgrep -f "gunicorn.*reventa" | head -1)'
```

> `kill -HUP` hace graceful restart: mata workers viejos y crea nuevos
> cargando el código actualizado. Funciona sin sudo porque `ferreteria`
> es owner del proceso gunicorn.

### 2.8 Verificar

```bash
# Estado del servicio
ssh fasa_195 'systemctl status reventa --no-pager | head -10'

# Backend responde
ssh fasa_195 'curl -sk https://127.0.0.1/api/token/ -H "Host: ventas.ferreteriaavenida.com.ar" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"test\",\"password\":\"test\"}" 2>&1'

# Frontend sirve bundle nuevo
ssh fasa_195 'curl -sk https://127.0.0.1/ -H "Host: ventas.ferreteriaavenida.com.ar" 2>&1 | \
  grep -oE "assets/index-[^\"]+\.(css|js)"'

# Django check
ssh fasa_195 'cd /var/www/html/reventa/backend && ../venv/bin/python manage.py check --no-color 2>&1'
```

> **El usuario `oscar` tiene password diferente en producción** (DB externa
> `192.168.0.150`) que en el stack Docker de pruebas. No confundir.

---

## 3. Troubleshooting

### 3.1 `sudo: se requiere una contraseña`

`ferreteria` tiene sudo pero **necesita ingresar la contraseña**. No hay
workaround sin contraseña. Alternativa: usar `kill -HUP` (ver 2.7 opción B).

### 3.2 tar errores "No se puede efectuar utime" / "Permiso denegado"

Es normal. Los directorios `api/`, `api/migrations/`, `api/services/` están
owned por `root:www-data` y `ferreteria` no puede cambiar timestamps/perms.
**Los archivos .py SÍ se extraen.** Verificar con `head` después.

### 3.3 `Conflicting migrations detected; multiple leaf nodes`

Django detecta ramas de migración sin merge (ej: bot y pedido). Solución:

```bash
ssh fasa_195 'cd /var/www/html/reventa/backend && \
  ../venv/bin/python manage.py makemigrations --merge --noinput && \
  ../venv/bin/python manage.py migrate --noinput'
```

### 3.4 Después del deploy el sitio muestra el bundle viejo

- `Ctrl+Shift+R` en el navegador
- Verificar hash: `curl -sk https://127.0.0.1/ -H "Host: ventas.ferreteriaavenida.com.ar" | grep -oE "assets/index-[^\"]+\.js"`
- Confirmar que `cp -r dist/* .` se ejecutó en `frontend/`

### 3.5 Backend devuelve 500

```bash
ssh fasa_195 'tail -100 /var/www/html/reventa/logs/gunicorn.log'
```

### 3.6 Verificar qué migraciones faltan en prod

```bash
ssh fasa_195 'cd /var/www/html/reventa/backend && \
  ../venv/bin/python manage.py showmigrations api 2>&1 | grep "\[ \]"'
```

### 3.7 Verificar estado de la DB (columnas de pedido)

```bash
ssh fasa_195 'cd /var/www/html/reventa/backend && \
  ../venv/bin/python manage.py shell -c "
from django.db import connection
c = connection.cursor()
c.execute(\"DESCRIBE api_pedido\")
for r in c.fetchall():
    print(r[0], r[1])
"'
```

---

## 4. Rollback

### 4.1 Frontend

```bash
# Restaurar desde backup
ssh fasa_195 'ls /tmp/frontend_src_backup_*.tar.gz'  # identificar backup
ssh fasa_195 'cd /var/www/html/reventa && tar xzf /tmp/frontend_src_backup_<fecha>.tar.gz'
ssh fasa_195 'cd /var/www/html/reventa/frontend && npm run build && cp -r dist/* .'
```

### 4.2 Backend

```bash
# Restaurar desde backup
ssh fasa_195 'ls /tmp/backend_backup_*.tar.gz'
ssh fasa_195 'cd /var/www/html/reventa && tar xzf /tmp/backend_backup_<fecha>.tar.gz'

# Rollback de migración
ssh fasa_195 'cd /var/www/html/reventa/backend && \
  ../venv/bin/python manage.py migrate api <migration_anterior>'

# Reiniciar
ssh fasa_195 'kill -HUP $(pgrep -f "gunicorn.*reventa" | head -1)'
```

---

## 5. Cache de navegador

nginx define `Cache-Control: public, max-age=3600` para `/`. Después de cada
deploy el usuario debe hacer **`Ctrl+Shift+R`** (o ventana incógnito).

---

## 6. Cheat sheet

```bash
# === BACKEND ===
# Backup
ssh fasa_195 'cd /var/www/html/reventa && tar czf /tmp/backend_backup_$(date +%Y%m%d_%H%M%S).tar.gz backend/api backend/backend backend/graficos backend/manage.py backend/requirements.txt'

# Sync (desde Windows, crear tar local primero, luego:)
ssh fasa_195 'cd /var/www/html/reventa && tar xzf /tmp/backend_code.tar.gz --strip-components=1 -C backend/ backend/api backend/backend backend/graficos backend/manage.py backend/requirements.txt'

# Migrations
ssh fasa_195 'cd /var/www/html/reventa/backend && ../venv/bin/python manage.py migrate --noinput'

# === FRONTEND ===
# Build
ssh fasa_195 'cd /var/www/html/reventa/frontend && npm install --legacy-peer-deps && npm run build'
ssh fasa_195 'cd /var/www/html/reventa/frontend && cp -r dist/* .'

# === REINICIAR ===
ssh fasa_195 'kill -HUP $(pgrep -f "gunicorn.*reventa" | head -1)'  # sin sudo
# o
ssh fasa_195 'sudo systemctl restart reventa'  # pide contraseña

# === VALIDAR ===
ssh fasa_195 'curl -sk https://127.0.0.1/ -H "Host: ventas.ferreteriaavenida.com.ar" | grep -oE "assets/index-[^\"]+\.js"'
ssh fasa_195 'systemctl status reventa --no-pager | head -5'
```

---

## 7. Diferencias con el stack de pruebas (Docker)

| Aspecto | Producción | Pruebas (Docker) |
|---|---|---|
| HTTPS | ✅ Let's Encrypt | ❌ HTTP plano |
| Dominio | `ventas.ferreteriaavenida.com.ar` | `192.168.0.195:15173` |
| Frontend servido por | nginx (host) | nginx dentro de contenedor |
| Backend corre como | systemd (`reventa.service`) | contenedor `revendedores-backend` |
| gunicorn puerto | `127.0.0.1:8088` | `0.0.0.0:8000` (mapeado a `18089`) |
| MySQL | `192.168.0.150:3306` (externo) | contenedor `revendedores-mysql` (volumen local) |
| Email backend | SMTP real (`dtc035.ferozo.com:465`) | `console.EmailBackend` (logs) |
| Logs | `/var/www/html/reventa/logs/gunicorn.log` | `docker logs revendedores-backend` |
| Cabeceras seguridad | HSTS, CSP, X-Frame-Options, etc. | Ninguna (solo nginx default) |
| Build frontend | `npm run build` + `cp dist/* .` | docker compose build (Vite + nginx alpine) |

> **Regla de oro:** todo cambio se prueba primero en el stack Docker (puerto
> 15173), y solo cuando está validado se promote a producción.
