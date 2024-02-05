#!/bin/bash

set -eou pipefail

production() {
    uwsgi \
        --http :8000 \
        --master \
        --module=src.hope_dedup_engine.config.wsgi \
        --processes=2 \
        --buffer-size=8192
}

if [ $# -eq 0 ]; then
    production
fi

case "$1" in
    dev)
        ./wait-for-it.sh db:5432
        python3 manage.py upgrade
        python3 manage.py runserver 0.0.0.0:8000 
    ;;
    tests)
        ./wait-for-it.sh db:5432
        pytest --create-db
    ;;
    prd)
        production
    ;;
    celery_worker)
        export C_FORCE_ROOT=1
        celery -A src.hope_dedup_engine.celery worker -l info
    ;;
    *)
        exec "$@"
    ;;
esac