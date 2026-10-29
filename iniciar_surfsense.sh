#!/usr/bin/env bash
# Inicia SurfSense completo: servicios de Docker + API + worker + beat + web.
# Todos los procesos corren en segundo plano; sus registros quedan en la carpeta "logs".
# Para detener todo, presiona Ctrl+C en esta terminal.
# Usa la carpeta desde donde se ejecuta; si ahi no esta SurfSense, usa la carpeta del script.

RAIZ="$(pwd)"
if [ ! -d "$RAIZ/surfsense_backend" ]; then
    # readlink -f sigue los enlaces, asi funciona tambien desde un acceso directo en el escritorio.
    RAIZ="$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"
fi

if [ ! -d "$RAIZ/surfsense_backend" ]; then
    echo "No se encontro la carpeta surfsense_backend en \"$RAIZ\"."
    echo "Ejecuta este script desde la carpeta raiz de SurfSense."
    exit 1
fi

BACKEND="$RAIZ/surfsense_backend"
WEB="$RAIZ/surfsense_web"
LOGS="$RAIZ/logs"
mkdir -p "$LOGS"

echo "Usando SurfSense en: $RAIZ"

echo "[1/5] Levantando servicios de Docker (base de datos, redis, etc.)..."
if ! docker compose -f "$RAIZ/docker/docker-compose.deps-only.yml" up -d; then
    echo
    echo "No se pudo levantar Docker. Revisa que Docker este corriendo y vuelve a intentarlo."
    exit 1
fi

PIDS=()
detener() {
    echo
    echo "Deteniendo SurfSense..."
    for pid in "${PIDS[@]}"; do
        kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null
    done
    wait 2>/dev/null
    echo "Listo, todo detenido."
    exit 0
}
trap detener INT TERM

# Lanza un proceso en su propio grupo para poder detenerlo junto con sus hijos.
iniciar() {
    local nombre="$1" carpeta="$2"
    shift 2
    (cd "$carpeta" && exec setsid "$@") >"$LOGS/$nombre.log" 2>&1 &
    PIDS+=($!)
}

echo "[2/5] Iniciando API...      (logs/api.log)"
iniciar api "$BACKEND" uv run main.py --reload

echo "[3/5] Iniciando worker...   (logs/worker.log)"
iniciar worker "$BACKEND" uv run celery -A celery_worker.celery_app worker --loglevel=info --concurrency=1 --pool=solo --queues=surfsense,surfsense.connectors

echo "[4/5] Iniciando beat...     (logs/beat.log)"
iniciar beat "$BACKEND" uv run celery -A celery_worker.celery_app beat --loglevel=info

echo "[5/5] Iniciando web...      (logs/web.log)"
iniciar web "$WEB" pnpm dev

echo
echo "Listo. En unos segundos abre http://localhost:3000/login"
echo "Para ver un registro en vivo:  tail -f logs/api.log"
echo "Presiona Ctrl+C para detener todo."
wait
