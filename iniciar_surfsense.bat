@echo off
REM Inicia SurfSense completo: servicios de Docker + API + worker + beat + web.
REM Cada proceso abre su propia ventana. Para detener uno, cierra su ventana.
REM Usa la carpeta desde donde se ejecuta; si ahi no esta SurfSense, usa la carpeta del script.

set "RAIZ=%CD%"
if not exist "%RAIZ%\surfsense_backend" set "RAIZ=%~dp0"
if "%RAIZ:~-1%"=="\" set "RAIZ=%RAIZ:~0,-1%"

if not exist "%RAIZ%\surfsense_backend" (
    echo No se encontro la carpeta surfsense_backend en "%RAIZ%".
    echo Ejecuta este script desde la carpeta raiz de SurfSense.
    pause
    exit /b 1
)

set "BACKEND=%RAIZ%\surfsense_backend"
set "WEB=%RAIZ%\surfsense_web"

echo Usando SurfSense en: %RAIZ%

echo [1/6] Levantando servicios de Docker (base de datos, redis, etc.)...
docker compose -f "%RAIZ%\docker\docker-compose.deps-only.yml" up -d
if errorlevel 1 (
    echo.
    echo No se pudo levantar Docker. Abre Docker Desktop y vuelve a intentarlo.
    pause
    exit /b 1
)

echo [2/6] Iniciando API...
start "SurfSense - API" /D "%BACKEND%" cmd /k uv run main.py --reload

echo [3/6] Iniciando worker...
start "SurfSense - Worker" /D "%BACKEND%" cmd /k uv run celery -A celery_worker.celery_app worker --loglevel=info --concurrency=1 --pool=solo --queues=surfsense,surfsense.connectors

echo [4/6] Iniciando beat...
start "SurfSense - Beat" /D "%BACKEND%" cmd /k uv run celery -A celery_worker.celery_app beat --loglevel=info

echo [5/6] Iniciando web...
REM Se usa Webpack en vez de Turbopack: Turbopack falla al cargar la fuente Roboto de Google en esta red.
start "SurfSense - Web" /D "%WEB%" cmd /k pnpm exec next dev --webpack

echo [6/6] Iniciando sincronizador de la carpeta compartida...
start "SurfSense - Sincronizador" /D "%BACKEND%" cmd /k uv run python scripts/sincronizar_carpeta.py

echo.
echo Listo. En unos segundos abre http://localhost:3000/login
timeout /t 5 >nul
