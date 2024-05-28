#!/bin/sh -e

alias env='env|sort'

export MEDIA_ROOT="${MEDIA_ROOT:-/var/media}"
export STATIC_ROOT="${STATIC_ROOT:-/var/static}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-"hope_dedup_engine.config.settings"}"


mkdir -p /var/run "${MEDIA_ROOT}" "${STATIC_ROOT}" || echo "Cannot create dir"

echo "Executing '$1'..."
echo "INIT_RUN_UPGRADE         '$INIT_RUN_UPGRADE'"
echo "  INIT_RUN_CHECK         '$INIT_RUN_CHECK'"
echo "  INIT_RUN_COLLECTSTATIC '$INIT_RUN_COLLECTSTATIC'"
echo "  INIT_RUN_MIGRATATIONS  '$INIT_RUN_MIGRATATIONS'"

case "$1" in
    run)
      if [ "$INIT_RUN_CHECK" = "1" ];then
        echo "Running Django checks..."
        django-admin check --deploy
      fi
      OPTS="--no-check -v 1"
      if [ "$INIT_RUN_UPGRADE" = "1" ];then
        if [ "$INIT_RUN_COLLECTSTATIC" != "1" ];then
          OPTS="$OPTS --no-static"
        fi
        if [ "$INIT_RUN_MIGRATATIONS" != "1" ];then
          OPTS="$OPTS --no-migrate"
        fi
        echo "Running 'upgrade $OPTS'"
        django-admin upgrade $OPTS
      fi
      set -- tini -- "$@"
      echo "Starting uwsgi..."
      exec uwsgi --ini /conf/uwsgi.ini
      ;;
    worker)
      export C_FORCE_ROOT=1
      exec celery -A hope_dedup_engine.config.celery worker -E --loglevel=ERROR --concurrency=4
      ;;
    beat)
      exec celery -A hope_dedup_engine.config.celery beat --loglevel=ERROR --scheduler django_celery_beat.schedulers:DatabaseScheduler
      ;;
    dev)
      until pg_isready -h db -p 5432;
        do echo "waiting for database"; sleep 2; done;
      django-admin collectstatic --no-input
      django-admin migrate
      django-admin runserver 0.0.0.0:8000
      ;;
    *)
      exec "$@"
      ;;
esac
