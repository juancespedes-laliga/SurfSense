"""Mantiene una carpeta (local o compartida en red) sincronizada con SurfSense.

Revisa la carpeta cada pocos segundos comparando solo nombres, fechas y tamanos
de los archivos (es muy liviano). Si nada cambio, no hace nada. Si algo cambio
(archivo nuevo, modificado o borrado), le pide al worker de SurfSense que
sincronice la carpeta: agrega lo nuevo, actualiza lo modificado y elimina lo
que ya no esta. Los archivos que no cambiaron no se vuelven a procesar.

Requisitos: Docker, la API y el worker de SurfSense encendidos (iniciar_surfsense.bat).

Uso (desde la carpeta surfsense_backend):
    uv run python scripts/sincronizar_carpeta.py
    uv run python scripts/sincronizar_carpeta.py --carpeta "\\\\servidor\\ruta" --cada 15
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import asyncpg
from celery import Celery
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

CARPETA_POR_DEFECTO = r"\\160.1.1.230\Sistemas\Juan David\PRUEBAS_DOCUMENTOS_SURFSENSE"
EXTENSIONES_POR_DEFECTO = ".pdf,.docx,.xlsx,.pptx"  # formatos que Docling sabe leer
# Mismos excluidos que usa SurfSense para carpetas locales.
EXCLUIDOS = [".git", "node_modules", "__pycache__", ".DS_Store", ".obsidian", ".trash"]
ESPERA_TRAS_ERROR = 300  # segundos antes de reintentar si la sincronizacion fallo


def log(msg: str) -> None:
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def es_temporal(nombre: str) -> bool:
    # Word/Excel crean "~$archivo.docx" mientras el documento esta abierto.
    return nombre.startswith("~$") or nombre.startswith(".~lock")


def huella(carpeta: str, extensiones: set[str]) -> frozenset:
    """Lista (ruta relativa, fecha, tamano) de cada archivo: si cambia, algo cambio."""
    raiz = Path(carpeta)
    datos = []
    for dirpath, dirnames, filenames in os.walk(raiz):
        dirnames[:] = [d for d in dirnames if d not in EXCLUIDOS]
        rel_dir = Path(dirpath).relative_to(raiz)
        if any(p in EXCLUIDOS for p in rel_dir.parts):
            continue
        # Las carpetas tambien cuentan: SurfSense replica la estructura.
        datos.append(("dir", str(rel_dir)))
        for nombre in filenames:
            if nombre in EXCLUIDOS or es_temporal(nombre):
                continue
            ruta = Path(dirpath) / nombre
            if ruta.suffix.lower() not in extensiones:
                continue
            try:
                st = ruta.stat()
            except OSError:
                continue
            datos.append((str(ruta.relative_to(raiz)), int(st.st_mtime), st.st_size))
    return frozenset(datos)


def contar_archivos(h: frozenset) -> int:
    return sum(1 for d in h if d[0] != "dir")


def db_dsn() -> str:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        sys.exit("No se encontro DATABASE_URL en surfsense_backend/.env")
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def buscar_workspace(nombre: str | None) -> tuple[int, str, str]:
    conn = await asyncpg.connect(db_dsn())
    try:
        filas = await conn.fetch("SELECT id, name, user_id FROM workspaces ORDER BY id")
    finally:
        await conn.close()
    if not filas:
        sys.exit("No hay espacios de trabajo en SurfSense. Entra a la web primero.")
    if nombre:
        filas = [f for f in filas if f["name"].lower() == nombre.lower()]
        if not filas:
            sys.exit(f"No existe el espacio de trabajo '{nombre}'.")
    f = filas[0]
    return f["id"], f["name"], str(f["user_id"])


async def buscar_carpeta_raiz(workspace_id: int, nombre: str) -> int | None:
    """Id de la carpeta de SurfSense que refleja la compartida (si ya existe)."""
    conn = await asyncpg.connect(db_dsn())
    try:
        return await conn.fetchval(
            "SELECT id FROM folders WHERE workspace_id = $1 AND parent_id IS NULL "
            "AND name = $2 ORDER BY id LIMIT 1",
            workspace_id,
            nombre,
        )
    finally:
        await conn.close()


def main() -> None:
    p = argparse.ArgumentParser(description="Sincroniza una carpeta con SurfSense.")
    p.add_argument("--carpeta", default=os.getenv("SYNC_CARPETA", CARPETA_POR_DEFECTO))
    p.add_argument("--workspace", default=os.getenv("SYNC_WORKSPACE"), help="Nombre del espacio de trabajo (por defecto el primero).")
    p.add_argument("--extensiones", default=os.getenv("SYNC_EXTENSIONES", EXTENSIONES_POR_DEFECTO))
    p.add_argument("--cada", type=int, default=int(os.getenv("SYNC_CADA", "15")), help="Segundos entre revisiones.")
    args = p.parse_args()

    carpeta = args.carpeta.rstrip("\\/")
    nombre_carpeta = os.path.basename(carpeta)
    extensiones = {
        e.strip().lower() if e.strip().startswith(".") else "." + e.strip().lower()
        for e in args.extensiones.split(",")
        if e.strip()
    }

    workspace_id, workspace_nombre, user_id = asyncio.run(buscar_workspace(args.workspace))

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery = Celery(
        broker=os.getenv("CELERY_BROKER_URL", redis_url),
        backend=os.getenv("CELERY_RESULT_BACKEND", redis_url),
    )
    cola = os.getenv("CELERY_TASK_DEFAULT_QUEUE", "surfsense")

    log(f"Carpeta:  {carpeta}")
    log(f"Destino:  espacio '{workspace_nombre}' -> carpeta '{nombre_carpeta}'")
    log(f"Archivos: {', '.join(sorted(extensiones))} | revision cada {args.cada} s")
    log("Esperando cambios... (cierra esta ventana para detener)")

    sincronizada = None  # huella de la ultima sincronizacion exitosa
    anterior = None      # huella de la revision anterior (para esperar a que termine de copiarse)
    no_reintentar_hasta = 0.0
    carpeta_caida = False

    while True:
        try:
            if not os.path.isdir(carpeta):
                raise OSError("no se encuentra")
            actual = huella(carpeta, extensiones)
            if carpeta_caida:
                log("La carpeta volvio a estar disponible.")
                carpeta_caida = False
        except OSError as e:
            # Sin acceso a la red: no se toca nada en SurfSense.
            if not carpeta_caida:
                log(f"No se puede leer la carpeta ({e}). Reintentando...")
                carpeta_caida = True
            time.sleep(args.cada)
            continue

        hay_cambios = actual != sincronizada
        estable = actual == anterior  # igual que hace un ciclo: ya termino de copiarse
        anterior = actual

        if hay_cambios and estable and time.time() >= no_reintentar_hasta:
            motivo = "sincronizacion inicial" if sincronizada is None else "se detectaron cambios"
            log(f"{motivo.capitalize()} ({contar_archivos(actual)} archivos). Sincronizando...")
            root_id = asyncio.run(buscar_carpeta_raiz(workspace_id, nombre_carpeta))
            tarea = celery.send_task(
                "index_local_folder",
                kwargs={
                    "workspace_id": workspace_id,
                    "user_id": user_id,
                    "folder_path": carpeta,
                    "folder_name": nombre_carpeta,
                    "exclude_patterns": EXCLUIDOS,
                    "file_extensions": sorted(extensiones),
                    "root_folder_id": root_id,
                },
                queue=cola,
            )
            try:
                tarea.get(propagate=True, disable_sync_subtasks=False)
                sincronizada = actual
                log("Sincronizacion terminada. Esperando cambios...")
            except Exception as e:
                log(f"La sincronizacion fallo: {e}. Se reintentara en {ESPERA_TRAS_ERROR // 60} min.")
                no_reintentar_hasta = time.time() + ESPERA_TRAS_ERROR

        time.sleep(args.cada)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Detenido.")
