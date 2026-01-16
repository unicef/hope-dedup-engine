# envs to set before use this script
.ONESHELL:
VERSION:=$(shell cd .. && uvx --with hatch-vcs hatchling metadata version)
DOCKER_IMAGE_NAME:=unicef/hope_dedup_engine
BUILD_DATE:="$(shell date +"%Y-%m-%d %H:%M")"
SOURCE_COMMIT=$(shell git rev-parse --short HEAD)
STAGE?=dist
TAG?=${VERSION}

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)


build: ## build docker image
	@cd .. && uv build
	DOCKER_BUILDKIT=1 cd .. && docker build \
			--progress=plain \
			--build-arg VERSION=${VERSION} \
			--build-arg GIT_SHA=${SOURCE_COMMIT} \
			--build-arg BUILD_DATE=${BUILD_DATE} \
			--platform=linux/amd64 \
			--cache-from ${DOCKER_IMAGE_NAME}:local \
			--cache-from ${DOCKER_IMAGE_NAME}:latest \
			-t ${DOCKER_IMAGE_NAME}:local \
			-f docker/Dockerfile .
	docker images | grep "${DOCKER_IMAGE_NAME}" | grep local

.run:
	cd .. && docker run \
	 		--rm \
			-p 8000:8000 \
			-e ADMIN_EMAIL="${ADMIN_EMAIL}" \
			-e ADMIN_PASSWORD="${ADMIN_PASSWORD}" \
			-e ALLOWED_HOSTS="*" \
			-e CACHE_DEFAULT="redis://host.docker.internal:6379/0" \
			-e CELERY_BROKER_URL=redis://host.docker.internal:6379/0 \
			-e CSRF_COOKIE_SECURE=False \
			-e CSRF_TRUSTED_ORIGINS=http://localhost \
			-e DATABASE_URL="postgres://postgres:@host.docker.internal:5432/hope_dedup_engine" \
			-e DEBUG="1" \
			-e DJANGO_ADMIN_URL=admin/ \
			-e DJANGO_SETTINGS_MODULE=hope_dedup_engine.config.settings \
			-e FERNET_KEY=123 \
			-e LOGGING_LEVEL="DEBUG" \
			-e SECRET_KEY="super-secret-key-just-for-testing" \
			-e SENTRY_DSN="${SENTRY_DSN}" \
			-e SOCIAL_AUTH_REDIRECT_IS_HTTPS="False" \
			-e SECURE_HSTS_PRELOAD=1 \
			-e SESSION_COOKIE_DOMAIN= \
			-e SESSION_COOKIE_SECURE=false \
			${RUN_OPTIONS} \
			-t ${DOCKER_IMAGE} \
			${CMD}

run: ## Run docker build
	DOCKER_IMAGE=${DOCKER_IMAGE_NAME}:${VERSION} \
	$(MAKE) .run

check: ## Check docker build
	CMD='sh /usr/local/bin/check.sh' \
	DOCKER_IMAGE=${DOCKER_IMAGE_NAME}:${VERSION} \
	$(MAKE) .run

shell:  ## Run shell into docker
	DOCKER_IMAGE=${DOCKER_IMAGE_NAME}:${VERSION} \
	RUN_OPTIONS="-it" \
 	CMD='/bin/bash' \
	$(MAKE) .run
