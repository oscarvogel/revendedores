# Revendedores - Ferreteria Avenida SA

Portal web para la gestion de revendedores de Ferreteria Avenida SA. Permite buscar productos, gestionar carritos de compra, realizar pedidos y dar seguimiento a comercializaciones.

## Stack Tecnologico

| Capa | Tecnologia |
|------|------------|
| Frontend | Vue 3, Vite, Pinia, Tailwind CSS, Vue Router |
| Backend | Django 5.2, Django REST Framework, SimpleJWT |
| Base de datos | MySQL 8 |
| Auth | JWT (access + refresh tokens) |
| AI Bot | OpenRouter API |
| Infra (produccion) | gunicorn, nginx, systemd |
| Infra (prueba) | Docker Compose |

## Estructura del Proyecto

```
revendedores/
  backend/
    backend/          # Configuracion Django (settings, urls, wsgi)
    api/              # App principal: auth, pedidos, articulos, staff, bot
    graficos/         # Dashboard de graficos y facturacion
    media/            # Archivos subidos (productos, etc.)
  frontend/
    src/
      views/          # Paginas de la aplicacion
      components/     # Componentes reutilizables
      stores/         # Stores Pinia (auth, carrito)
      services/       # Cliente API (axios), carrito, utilidades
      router/         # Rutas con guards de autenticacion
      styles/         # Estilos globales
  docker/             # Entorno Docker de prueba
  docs/               # Documentacion y planes
```

## Funcionalidades

- **Busqueda de productos** con filtros por condicion comercial (ofertas, descuentos)
- **Carrito de compras** con persistencia en localStorage y sincronizacion al servidor
- **Pedidos** con confirmacion y notificacion por email
- **Dashboard de revendedor** con KPIs y graficos
- **Panel staff** para gestion de usuarios, pedidos, tracking y reportes
- **Bot IA** (OpenRouter) para asistencia a vendedores
- **PWA** con soporte offline y servicio worker

## Desarrollo Local

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
cp .env.example .env      # Configurar variables de entorno
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

El frontend en desarrollo apunta a `http://192.168.0.200:8000/` por defecto. Para cambiar, editar `frontend/src/services/api.js`.

### Comandos utiles

```bash
cd frontend
npm run lint          # Linting con ESLint
npm run format        # Formateo con Prettier
npm run build         # Build de produccion
```

## Deploy de Prueba (Docker)

Ver [deploy_prueba.md](deploy_prueba.md) para instrucciones completas.

Resumen rápido:

```bash
cd /home/fasa/revendedores-staging/docker
sudo docker compose -p revendedores-staging -f docker-compose.staging-189.yml up -d --build
sudo docker compose -p revendedores-staging -f docker-compose.staging-189.yml exec -T backend python manage.py migrate --noinput
```

Acceso: http://192.168.0.189:15173

| Servicio | Acceso |
|----------|--------|
| Frontend y proxy API | 15173 |
| Backend y MySQL | Sólo red privada de Docker |
## Deploy en Producción

**Servidor:** `fasa_189` (`192.168.0.189`)
**Dominio:** https://ventas.ferreteriaavenida.com.ar

- Aplicación administrada con Coolify.
- Seguir el procedimiento vigente en [deploy_production.md](deploy_production.md).
- Los pasos manuales del servidor anterior no aplican.
## Arquitectura de Auth

1. Login: POST `/api/token/` con usuario + password
2. Respuesta: access token, refresh token, datos del usuario, session_id
3. Tokens almacenados en localStorage
4. Requests autenticados via header `Authorization: Bearer <token>`
5. Auto-refresh del access token al recibir 401
6. Keep-alive cada 10 minutos

## Variables de Entorno

Ver `backend/.env` para la referencia completa. Variables principales:

| Variable | Descripcion |
|----------|-------------|
| `DB_ENGINE`, `DB_NAME`, `DB_HOST` | Conexion a MySQL |
| `FASA_DB_*` | Segunda conexion (base FASA) |
| `CORS_ALLOWED_ORIGINS` | Origenes permitidos |
| `OPENROUTER_API_KEY` | API key para el bot IA |
| `EMAIL_*` | Configuracion SMTP |

## Licencia

Uso interno - Ferreteria Avenida SA

