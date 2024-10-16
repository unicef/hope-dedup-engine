#!/bin/sh

export MEDIA_ROOT="${MEDIA_ROOT:-/var/run/app/media}"
export STATIC_ROOT="${STATIC_ROOT:-/var/run/app/static}"
export DEFAULT_ROOT="${DEFAULT_ROOT:-/var/run/app/default}"
export UWSGI_PROCESSES="${UWSGI_PROCESSES:-"4"}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-"hope_dedup_engine.config.settings"}"
mkdir -p "${MEDIA_ROOT}" "${STATIC_ROOT}" "${DEFAULT_ROOT}" || echo "Cannot create dirs ${MEDIA_ROOT} ${STATIC_ROOT} ${DEFAULT_ROOT}"

if [ -d "${STATIC_ROOT}" ];then
  chown -R user:app ${STATIC_ROOT}
fi

if [ -d "${DEFAULT_ROOT}" ];then
  chown -R user:app ${DEFAULT_ROOT}
fi


echo "MEDIA_ROOT  ${MEDIA_ROOT}"
echo "STATIC_ROOT ${STATIC_ROOT}"
echo "DEFAULT_ROOT  ${DEFAULT_ROOT}"
echo "Docker run command: $1"

case "$1" in
    setup)
      django-admin check --deploy || exit 1
      django-admin upgrade --no-static || exit 1
      exit 0
      ;;
    worker)
      gosu user:app django-admin syncdnn || exit 1
	    set -- tini -- "$@"
      set -- gosu user:app celery -A hope_dedup_engine.config.celery worker -E --loglevel=ERROR --concurrency=4
      ;;
    beat)
	    set -- tini -- "$@"
      set -- gosu user:app celery -A hope_dedup_engine.config.celery beat --loglevel=ERROR --scheduler django_celery_beat.schedulers:DatabaseScheduler
      ;;
    run)
      django-admin check --deploy || exit 1
	    set -- tini -- "$@"
  		set -- gosu user:app uwsgi --ini /conf/uwsgi.ini
	    ;;
esac

exec "$@"
