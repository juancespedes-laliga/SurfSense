"""Cambia la contrasena de un usuario de SurfSense directamente en la base de datos.

Uso (desde la carpeta surfsense_backend, con Docker encendido):
    uv run python scripts/resetear_contrasena.py            -> lista los usuarios
    uv run python scripts/resetear_contrasena.py tu@correo  -> pide la nueva contrasena
"""

import asyncio
import getpass
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv
from fastapi_users.password import PasswordHelper

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def dsn() -> str:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        sys.exit("No se encontro DATABASE_URL en surfsense_backend/.env")
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def main() -> None:
    conn = await asyncpg.connect(dsn())
    try:
        if len(sys.argv) < 2:
            rows = await conn.fetch('SELECT email, is_active FROM "user" ORDER BY email')
            print("Usuarios registrados:")
            for r in rows:
                print(f"  - {r['email']}{'' if r['is_active'] else '  (inactivo)'}")
            print("\nPara cambiar una contrasena:")
            print("  uv run python scripts/resetear_contrasena.py <correo>")
            return

        email = sys.argv[1].strip()
        user = await conn.fetchrow(
            'SELECT id FROM "user" WHERE lower(email) = lower($1)', email
        )
        if not user:
            sys.exit(f"No existe ningun usuario con el correo {email}")

        nueva = getpass.getpass("Nueva contrasena: ")
        if len(nueva) < 8:
            sys.exit("La contrasena debe tener al menos 8 caracteres.")
        if nueva != getpass.getpass("Repite la contrasena: "):
            sys.exit("Las contrasenas no coinciden.")

        hashed = PasswordHelper().hash(nueva)
        await conn.execute(
            'UPDATE "user" SET hashed_password = $1, is_active = true WHERE id = $2',
            hashed,
            user["id"],
        )
        print(f"Listo. Contrasena actualizada para {email}.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
