# Deploy de Prueba - Docker

Entorno aislado de Revendedores en `fasa_189` (`192.168.0.189`). Usa su propio proyecto Docker y volumen de MySQL. El host publica únicamente el frontend en el puerto `15173`; backend y base de datos sólo se comunican en la red privada del stack.

## Conexión SSH

```bash
ssh fasa_189
```

## Servicios

| Servicio | Acceso | Descripción |
|----------|--------|-------------|
| Frontend | http://192.168.0.189:15173 | Vue SPA y proxy para `/api/` y `/admin/` |
| Backend API | http://192.168.0.189:15173/api/ | Django REST, vía Nginx interno |
| Backend Admin | http://192.168.0.189:15173/admin/ | Django Admin, vía Nginx interno |
| MySQL | Sólo red Docker (`mysql:3306`) | Base de pruebas aislada, sin puerto publicado |

## Requisitos

- Docker y Docker Compose instalados en `fasa_189`.
- Archivo `/home/fasa/revendedores-staging/docker/.env.docker` con las variables de staging. No versionar ese archivo ni copiar secretos de producción.
- Los puertos `15173` libres en el host.

## Levantar o actualizar

```bash
cd /home/fasa/revendedores-staging/docker
sudo docker compose -p revendedores-staging -f docker-compose.staging-189.yml up -d --build
sudo docker compose -p revendedores-staging -f docker-compose.staging-189.yml exec -T backend python manage.py migrate --noinput
sudo docker compose -p revendedores-staging -f docker-compose.staging-189.yml ps
```

Abrir **http://192.168.0.189:15173**. El frontend usa el proxy interno para las llamadas al backend; MySQL no queda expuesto al host.

## Logs y parada

```bash
sudo docker compose -p revendedores-staging -f docker-compose.staging-189.yml logs -f
sudo docker compose -p revendedores-staging -f docker-compose.staging-189.yml down
```

`down` preserva el volumen de la base. No usar `down -v` salvo que se quiera borrar la base de pruebas.
