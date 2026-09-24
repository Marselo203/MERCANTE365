# Atajos del día a día. Todo pasa por compose, así nunca corres nada
# contra un Python del host que no sea el de la imagen.

.PHONY: up down logs shell psql migrate mm seed test lint reset prod-up prod-logs prod-cert prod-backup

up:            ## Levanta el entorno de desarrollo
	docker compose up --build

down:          ## Baja los contenedores (conserva los datos)
	docker compose down

logs:
	docker compose logs -f web

shell:         ## Shell de Django
	docker compose exec web python manage.py shell

bash:
	docker compose exec web bash

psql:
	docker compose exec db psql -U $${POSTGRES_USER:-b2b} -d $${POSTGRES_DB:-b2b}

mm:            ## makemigrations
	docker compose exec web python manage.py makemigrations catalogo

migrate:
	docker compose exec web python manage.py migrate

seed:          ## Ubicaciones + datos de demostración
	docker compose exec web python manage.py seed_ubicaciones
	docker compose exec web python manage.py seed_demo

admin:         ## Crea el superusuario
	docker compose exec web python manage.py createsuperuser

test:
	docker compose exec web python manage.py test

dump:          ## Respaldo de la base al directorio actual
	docker compose exec -T db pg_dump -U $${POSTGRES_USER:-b2b} $${POSTGRES_DB:-b2b} \
		| gzip > respaldo-$$(date +%Y%m%d-%H%M).sql.gz

reset:         ## BORRA la base y la recrea desde cero con datos demo
	docker compose down -v
	docker compose up -d --build
	sleep 8
	$(MAKE) seed

prod-up:       ## Despliega/actualiza en el servidor
	docker compose -f compose.yaml -f compose.prod.yaml up -d --build

prod-logs:
	docker compose -f compose.yaml -f compose.prod.yaml logs -f

prod-cert:     ## Emite el certificado la PRIMERA vez (nginx todavía no puede arrancar sin él)
	@set -a; . ./.env; set +a; \
	sudo mkdir -p /srv/certbot; \
	docker run --rm -d --name certbot-tmp -p 80:80 -v /srv/certbot:/usr/share/nginx/html:ro nginx:1.27-alpine; \
	sudo certbot certonly --webroot -w /srv/certbot -d $$DOMINIO --agree-tos --no-eff-email -m $${CERT_EMAIL:-admin@$$DOMINIO}; \
	docker stop certbot-tmp
	@echo "Listo. Las renovaciones las hace solo el timer de certbot por webroot."

prod-backup:   ## Respaldo manual (el nocturno lo dispara cron)
	./docker/backup.sh
