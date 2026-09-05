Application Dockerfiles live next to their code:

- `backend/Dockerfile`
- `frontend/Dockerfile`
- `infrastructure/postgres/Dockerfile`

Nginx is configured but not started by default compose (see nginx/nginx.conf).
Add an nginx service later when you stop using Vite's built-in server.
