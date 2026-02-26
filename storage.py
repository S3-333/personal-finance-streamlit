import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator, List, Dict, Any, Optional

DB_PATH = "categories.db"
JSON_PATH = "categories.json"


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """
    Context manager que abre y cierra una conexión a SQLite de forma segura.
    Separa el detalle de conexión del resto del código.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """
    Inicializa la base de datos SQLite si no existe.
    Crea tablas para categorías y keywords con prioridad.
    Si existe un antiguo archivo categories.json, intenta migrarlo.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                priority INTEGER NOT NULL DEFAULT 100
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                pattern TEXT NOT NULL,
                is_regex INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (category_id) REFERENCES categories (id)
                    ON DELETE CASCADE
            )
            """
        )

        # Insertar categoría "Uncategorized" si no existe
        cur.execute(
            """
            INSERT OR IGNORE INTO categories (name, priority)
            VALUES ('Uncategorized', 999)
            """
        )

    # Después de asegurar las tablas, intentamos migrar desde JSON si aplica
    migrate_from_json_if_present()


def migrate_from_json_if_present() -> None:
    """
    Migra datos desde un antiguo archivo categories.json si:
    - El archivo existe
    - No hay categorías de usuario creadas aún (solo 'Uncategorized')
    Esta función es idempotente: si ya migraste o creaste categorías nuevas,
    no volverá a duplicar nada.
    """
    if not os.path.exists(JSON_PATH):
        return

    # Comprobamos si solo existe 'Uncategorized'
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as c FROM categories WHERE name != 'Uncategorized'")
        row = cur.fetchone()
        if row and row["c"] > 0:
            # Ya hay categorías de usuario, no migramos para no pisar.
            return

    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        # Si el JSON está corrupto o no es válido, simplemente no migramos.
        return

    # Estructura esperada del JSON antiguo: { "Categoria": ["KW1", "KW2", ...], ... }
    for name, keywords in data.items():
        cleaned_name = str(name).strip()
        if not cleaned_name or cleaned_name == "Uncategorized":
            continue

        add_category(cleaned_name)
        cat_id = get_category_id_by_name(cleaned_name)
        if cat_id is None:
            continue

        if isinstance(keywords, list):
            for kw in keywords:
                cleaned_kw = str(kw).strip()
                if cleaned_kw:
                    add_keyword(cat_id, cleaned_kw, is_regex=False)


def get_categories_with_keywords() -> List[Dict[str, Any]]:
    """
    Devuelve una lista de categorías con sus keywords asociadas.
    Estructura:
    [
      {
        "id": 1,
        "name": "Supermercado",
        "priority": 10,
        "keywords": [
            {"id": 1, "pattern": "LULU", "is_regex": 0, "enabled": 1},
            ...
        ]
      },
      ...
    ]
    """
    with get_connection() as conn:
        cur = conn.cursor()

        cur.execute(
            "SELECT id, name, priority FROM categories ORDER BY priority ASC, name ASC"
        )
        categories_rows = cur.fetchall()

        cur.execute(
            """
            SELECT id, category_id, pattern, is_regex, enabled
            FROM keywords
            ORDER BY id ASC
            """
        )
        keywords_rows = cur.fetchall()

    categories_dict = {
        row["id"]: {
            "id": row["id"],
            "name": row["name"],
            "priority": row["priority"],
            "keywords": [],
        }
        for row in categories_rows
    }

    for k in keywords_rows:
        cat = categories_dict.get(k["category_id"])
        if cat is not None:
            cat["keywords"].append(
                {
                    "id": k["id"],
                    "pattern": k["pattern"],
                    "is_regex": bool(k["is_regex"]),
                    "enabled": bool(k["enabled"]),
                }
            )

    return list(categories_dict.values())


def add_category(name: str, priority: int = 100) -> None:
    """
    Crea una nueva categoría con una prioridad opcional.
    """
    cleaned = name.strip()
    if not cleaned:
        return
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO categories (name, priority) VALUES (?, ?)",
            (cleaned, priority),
        )


def delete_category(category_id: int) -> None:
    """
    Elimina una categoría y sus keywords asociadas (ON DELETE CASCADE).
    No se recomienda permitir eliminar 'Uncategorized' desde la UI.
    """
    with get_connection() as conn:
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))


def update_category_priority(category_id: int, priority: int) -> None:
    """
    Actualiza la prioridad de una categoría.
    """
    with get_connection() as conn:
        conn.execute(
            "UPDATE categories SET priority = ? WHERE id = ?",
            (priority, category_id),
        )


def add_keyword(category_id: int, pattern: str, is_regex: bool = False) -> None:
    """
    Añade una keyword / patrón a una categoría.
    Evitamos guardar cadenas vacías.
    """
    cleaned = pattern.strip()
    if not cleaned:
        return

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO keywords (category_id, pattern, is_regex, enabled)
            VALUES (?, ?, ?, 1)
            """,
            (category_id, cleaned, int(is_regex)),
        )


def delete_keyword(keyword_id: int) -> None:
    """
    Elimina una keyword por id.
    """
    with get_connection() as conn:
        conn.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))


def toggle_keyword_enabled(keyword_id: int, enabled: bool) -> None:
    """
    Activa o desactiva una keyword.
    """
    with get_connection() as conn:
        conn.execute(
            "UPDATE keywords SET enabled = ? WHERE id = ?",
            (int(enabled), keyword_id),
        )


def get_category_id_by_name(name: str) -> Optional[int]:
    """
    Devuelve el id de categoría dado su nombre, o None si no existe.
    Útil para lógica de negocio que trabaja con nombres.
    """
    cleaned = name.strip()
    if not cleaned:
        return None
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM categories WHERE name = ?",
            (cleaned,),
        )
        row = cur.fetchone()
    return int(row["id"]) if row else None

