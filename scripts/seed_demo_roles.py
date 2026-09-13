"""Crea cuentas de prueba para cada uno de los roles del piloto."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from talentia.platform.security.contrasenas import hash_contrasena
from talentia.shared.domain.modelos import nuevo_id

DB_PATH = ROOT_DIR / "talentia_greenfield.db"

PASSWORD_COMUN = "TalentIA-Demo-2026!"

USUARIOS = [
    ("admin@talentia.local", "Administrador TalentIA", "administrador"),
    ("reclutador@talentia.local", "Reclutador TCS", "reclutador"),
    ("gestor@talentia.local", "Gestor de Contratacion TCS", "gestor_contratacion"),
    ("entrevistador@talentia.local", "Entrevistador Tecnico", "entrevistador"),
    ("auditor@talentia.local", "Auditor de Procesos", "auditor"),
    ("importador@talentia.local", "Operador de Lotes y Proveedores", "importador"),
]

def main() -> None:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cliente_res = cur.execute("select id from clients where codigo='TCS'").fetchone()
    if not cliente_res:
        print("Cliente TCS no existe, creandolo...")
        cliente_id = nuevo_id()
        cur.execute(
            "insert into clients (id, codigo, nombre, activo, creado_en, actualizado_en) values (?, 'TCS', 'TCS', 1, datetime('now'), datetime('now'))",
            (cliente_id,),
        )
    else:
        cliente_id = cliente_res[0]

    roles = dict(cur.execute("select codigo, id from roles").fetchall())
    hash_pwd = hash_contrasena(PASSWORD_COMUN)

    for correo, nombre, rol_codigo in USUARIOS:
        existente = cur.execute("select id from users where correo=?", (correo,)).fetchone()
        if existente:
            user_id = existente[0]
            cur.execute(
                "update users set hash_contrasena=?, activo=1, nombre=? where id=?",
                (hash_pwd, nombre, user_id),
            )
        else:
            user_id = nuevo_id()
            cur.execute(
                "insert into users (id, correo, nombre, hash_contrasena, activo, version, creado_en, actualizado_en) values (?, ?, ?, ?, 1, 1, datetime('now'), datetime('now'))",
                (user_id, correo, nombre, hash_pwd),
            )

        rol_id = roles[rol_codigo]
        cur.execute("delete from user_roles where usuario_id=?", (user_id,))
        cur.execute(
            "insert into user_roles (usuario_id, rol_id) values (?, ?)",
            (user_id, rol_id),
        )

        cur.execute("delete from user_client_assignments where usuario_id=?", (user_id,))
        cur.execute(
            "insert into user_client_assignments (usuario_id, cliente_id) values (?, ?)",
            (user_id, cliente_id),
        )

    con.commit()
    print("Usuarios creados exitosamente:")
    for row in cur.execute(
        "select u.correo, u.nombre, r.codigo from users u join user_roles ur on u.id=ur.usuario_id join roles r on ur.rol_id=r.id"
    ).fetchall():
        print(f" - Correo: {row[0]} | Rol: {row[2]} | Nombre: {row[1]}")

if __name__ == "__main__":
    main()
