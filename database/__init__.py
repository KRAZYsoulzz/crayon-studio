"""CrayonStudio Database Package."""
from .db import (
    init_db,
    create_project,
    get_all_projects,
    get_project_by_id,
    update_project,
    update_project_status,
    delete_project,
    save_trend_insight,
    get_all_trends,
    get_connection,
)

__all__ = [
    "init_db",
    "create_project",
    "get_all_projects",
    "get_project_by_id",
    "update_project",
    "update_project_status",
    "delete_project",
    "save_trend_insight",
    "get_all_trends",
    "get_connection",
]
