#!/bin/sh

export DEEPFACE_HOME="${DEEPFACE_HOME:-/var/run/app/deepface}"
export UWSGI_PROCESSES="${UWSGI_PROCESSES:-"4"}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-"hope_dedup_engine.config.settings"}"
mkdir -p "${MEDIA_ROOT}" "${STATIC_ROOT}" "${DEFAULT_ROOT}" || echo "Cannot create dirs ${MEDIA_ROOT} ${STATIC_ROOT} ${DEFAULT_ROOT}"

if [ -d "${STATIC_ROOT}" ];then
  chown -R hope:unicef ${STATIC_ROOT}
fi

if [ -d "${DEFAULT_ROOT}" ];then
  chown -R hope:unicef ${DEFAULT_ROOT}
fi

if [ -d "${IMAGES_ROOT}" ];then
  chown -R hope:unicef ${IMAGES_ROOT} 2>/dev/null || true
fi

if [ -d "${DEEPFACE_HOME}" ];then
  chown -R hope:unicef ${DEEPFACE_HOME}
fi

echo "MEDIA_ROOT  ${MEDIA_ROOT}"
echo "STATIC_ROOT ${STATIC_ROOT}"
echo "DEFAULT_ROOT ${DEFAULT_ROOT}"
echo "IMAGES_ROOT ${IMAGES_ROOT}"
echo "DEEPFACE_HOME ${DEEPFACE_HOME}"
echo "Docker run command: $1"

case "$1" in
    setup)
      django-admin check --deploy || exit 1
      django-admin upgrade --no-static --no-sync-models || exit 1
      exit 0
      ;;
    worker)
	    set -- tini -- "$@"
      set -- gosu hope:unicef celery -A hope_dedup_engine.config.celery worker -E --loglevel=DEBUG --concurrency=2
      ;;
    beat)
	    set -- tini -- "$@"
      set -- gosu hope:unicef celery -A hope_dedup_engine.config.celery beat --loglevel=DEBUG --scheduler django_celery_beat.schedulers:DatabaseScheduler
      ;;
    syncmodels)
      gosu hope:unicef django-admin syncmodels || exit 1
      exit 0
      ;;
    run)
      gosu hope:unicef django-admin check --deploy || exit 1
	    set -- tini -- "$@"
      set -- gosu hope:unicef uwsgi --ini /conf/uwsgi.ini
	    ;;
esac

exec "$@"
