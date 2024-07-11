#!/bin/sh


export MEDIA_ROOT="${MEDIA_ROOT:-/var/run/app/media}"
export STATIC_ROOT="${STATIC_ROOT:-/var/run/app/static}"
export UWSGI_PROCESSES="${UWSGI_PROCESSES:-"4"}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-"hope_dedup_engine.config.settings"}"
mkdir -p "${MEDIA_ROOT}" "${STATIC_ROOT}" || echo "Cannot create dirs ${MEDIA_ROOT} ${STATIC_ROOT}"

if [ -d "${STATIC_ROOT}" ];then
  chown -R user:app ${STATIC_ROOT}
fi

echo "MEDIA_ROOT  ${MEDIA_ROOT}"
echo "STATIC_ROOT ${STATIC_ROOT}"

case "$1" in
    setup)
      django-admin check --deploy
      django-admin upgrade
      ;;
    worker)
      exec celery -A hope_dedup_engine.config.celery worker -E --loglevel=ERROR --concurrency=4
      ;;
    beat)
      exec celery -A hope_dedup_engine.config.celery beat -E --loglevel=ERROR ---scheduler django_celery_beat.schedulers:DatabaseScheduler
      ;;
    run)
      django-admin check --deploy
      django-admin upgrade
	    set -- tini -- "$@"
  		set -- gosu user:app uwsgi --ini /conf/uwsgi.ini
	    ;;
	  *)
	    exec "$@"
esac
