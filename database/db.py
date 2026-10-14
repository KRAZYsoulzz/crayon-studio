"""Database access layer for CrayonStudio.

Handles SQLite connection, schema initialization, and CRUD operations for
projects and research trends.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict, List, Optional

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(CURRENT_DIR, "crayon_studio.db")
SCHEMA_PATH = os.path.join(CURRENT_DIR, "schema.sql")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Return a configured SQLite database connection."""
    target_path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize database tables from schema.sql and run migrations."""
    target_path = db_path or DEFAULT_DB_PATH
    with get_connection(target_path) as conn:
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)

        # Migration 1: Ensure visual_engine column exists
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(projects)")
        columns = [row["name"] for row in cursor.fetchall()]
        if "visual_engine" not in columns:
            cursor.execute("ALTER TABLE projects ADD COLUMN visual_engine TEXT DEFAULT '2D_Crayon'")

        # Migration 1B: Ensure complaints and praises columns exist in research_trends
        cursor.execute("PRAGMA table_info(research_trends)")
        rt_cols = [row["name"] for row in cursor.fetchall()]
        if "complaints" not in rt_cols:
            cursor.execute("ALTER TABLE research_trends ADD COLUMN complaints TEXT DEFAULT ''")
        if "praises" not in rt_cols:
            cursor.execute("ALTER TABLE research_trends ADD COLUMN praises TEXT DEFAULT ''")

        # Migration 2: Verify category constraint allows 'Engineering' and 'How It''s Made'
        try:
            conn.execute("SAVEPOINT check_cat_migration")
            conn.execute(
                "INSERT INTO projects (project_slug, title, category) VALUES ('__test_cat_migration__', 'Test', 'Engineering')"
            )
            conn.execute("ROLLBACK TO check_cat_migration")
            conn.execute("RELEASE check_cat_migration")
        except sqlite3.IntegrityError:
            conn.execute("ROLLBACK TO check_cat_migration")
            conn.execute("RELEASE check_cat_migration")
            # Table has legacy CHECK constraint, migrate to expanded schema
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("ALTER TABLE projects RENAME TO _projects_old")
            conn.executescript(schema_sql)
            cursor.execute("PRAGMA table_info(_projects_old)")
            old_cols = [r["name"] for r in cursor.fetchall()]
            valid_cols = [
                c for c in old_cols
                if c in [
                    "id", "project_slug", "title", "hook", "category",
                    "visual_engine", "script_text", "duration_target",
                    "tiktok_product", "status", "scheduled_time", "created_at"
                ]
            ]
            cols_str = ", ".join(valid_cols)
            conn.execute(f"INSERT INTO projects ({cols_str}) SELECT {cols_str} FROM _projects_old")
            conn.execute("DROP TABLE _projects_old")
            conn.execute("PRAGMA foreign_keys = ON")

        conn.commit()


def create_project(
    project_slug: str,
    title: str,
    hook: str = "",
    category: str = "STEM",
    visual_engine: str = "2D_Crayon",
    script_text: str = "",
    duration_target: int = 65,
    tiktok_product: str = "",
    status: str = "Draft",
    scheduled_time: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """Insert a new project record and return its row ID."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO projects (
                project_slug, title, hook, category, visual_engine, script_text,
                duration_target, tiktok_product, status, scheduled_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_slug,
                title,
                hook,
                category,
                visual_engine,
                script_text,
                duration_target,
                tiktok_product,
                status,
                scheduled_time,
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0


def get_all_projects(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all projects ordered by creation date descending."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_project_by_id(project_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a single project by its primary key ID."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_project_by_slug(project_slug: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieve a single project by its unique slug."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE project_slug = ?", (project_slug,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_project_status(
    project_id: int,
    status: str,
    scheduled_time: Optional[str] = None,
    db_path: Optional[str] = None,
) -> bool:
    """Update status and optional scheduled_time of a project."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if scheduled_time is not None:
            cursor.execute(
                "UPDATE projects SET status = ?, scheduled_time = ? WHERE id = ?",
                (status, scheduled_time, project_id),
            )
        else:
            cursor.execute(
                "UPDATE projects SET status = ? WHERE id = ?",
                (status, project_id),
            )
        conn.commit()
        return cursor.rowcount > 0


def update_project(
    project_id: int,
    title: Optional[str] = None,
    hook: Optional[str] = None,
    category: Optional[str] = None,
    visual_engine: Optional[str] = None,
    script_text: Optional[str] = None,
    duration_target: Optional[int] = None,
    tiktok_product: Optional[str] = None,
    status: Optional[str] = None,
    scheduled_time: Optional[str] = None,
    db_path: Optional[str] = None,
) -> bool:
    """Update general fields of an existing project."""
    updates = []
    params = []
    field_map = {
        "title": title,
        "hook": hook,
        "category": category,
        "visual_engine": visual_engine,
        "script_text": script_text,
        "duration_target": duration_target,
        "tiktok_product": tiktok_product,
        "status": status,
        "scheduled_time": scheduled_time,
    }
    for field, val in field_map.items():
        if val is not None:
            updates.append(f"{field} = ?")
            params.append(val)

    if not updates:
        return False

    params.append(project_id)
    sql = f"UPDATE projects SET {', '.join(updates)} WHERE id = ?"
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params))
        conn.commit()
        return cursor.rowcount > 0


def delete_project(project_id: int, db_path: Optional[str] = None) -> bool:
    """Delete a project from the database."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
        return cursor.rowcount > 0


def save_trend_insight(
    topic: str,
    source_url: str,
    views: int,
    content_gaps: str,
    confusion_points: str,
    complaints: str = "",
    praises: str = "",
    db_path: Optional[str] = None,
) -> int:
    """Insert a scraped trend and audience insight record."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO research_trends (
                topic, source_url, views, content_gaps, confusion_points, complaints, praises
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (topic, source_url, views, content_gaps, confusion_points, complaints, praises),
        )
        conn.commit()
        return cursor.lastrowid or 0


def get_all_trends(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve all trend insights ordered by date descending."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM research_trends ORDER BY date_scraped DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
