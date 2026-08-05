"""Servicio de gestion de investigaciones - CRUD completo."""
from datetime import datetime
from typing import Dict, List, Optional

import asyncpg

from src.config.settings import settings
from src.models.schemas import InvestigationStatus, Priority
from src.utils.logger import get_logger

logger = get_logger("aegis.investigation_service")


class InvestigationService:
    """Servicio de gestion de investigaciones."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def create(
        self,
        case_id: str,
        title: str,
        description: Optional[str],
        priority: Priority,
        assigned_unit: Optional[str],
        lead_officer: Optional[str],
        classification: str,
        tags: List[str],
        created_by: int,
    ) -> Dict:
        """Crea una nueva investigacion."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO investigations
                (case_id, title, description, status, priority, assigned_unit,
                 lead_officer, classification, tags, created_by, created_at)
                VALUES ($1, $2, $3, 'ACTIVE', $4, $5, $6, $7, $8, $9, $10)
                RETURNING id, case_id, title, status, priority, created_at
                """,
                case_id, title, description, priority.value, assigned_unit,
                lead_officer, classification, tags, created_by, datetime.utcnow(),
            )
            logger.info("investigation_created", case_id=case_id, title=title, created_by=created_by)
            return dict(row)

    async def get_by_id(self, investigation_id: int) -> Optional[Dict]:
        """Obtiene investigacion por ID."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT i.*, u.username as creator_username
                FROM investigations i
                LEFT JOIN users u ON i.created_by = u.id
                WHERE i.id = $1
                """,
                investigation_id,
            )
            return dict(row) if row else None

    async def get_by_case_id(self, case_id: str) -> Optional[Dict]:
        """Obtiene investigacion por case_id."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT i.*, u.username as creator_username
                FROM investigations i
                LEFT JOIN users u ON i.created_by = u.id
                WHERE i.case_id = $1
                """,
                case_id,
            )
            return dict(row) if row else None

    async def list_all(
        self,
        page: int = 1,
        page_size: int = 20,
        status: Optional[InvestigationStatus] = None,
        priority: Optional[Priority] = None,
        assigned_unit: Optional[str] = None,
    ) -> Dict:
        """Lista investigaciones paginadas con filtros."""
        offset = (page - 1) * page_size

        conditions = ["1=1"]
        params = []
        param_idx = 1

        if status:
            conditions.append(f"status = ${param_idx}")
            params.append(status.value)
            param_idx += 1
        if priority:
            conditions.append(f"priority = ${param_idx}")
            params.append(priority.value)
            param_idx += 1
        if assigned_unit:
            conditions.append(f"assigned_unit = ${param_idx}")
            params.append(assigned_unit)
            param_idx += 1

        where_clause = " AND ".join(conditions)

        async with self.db_pool.acquire() as conn:
            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM investigations WHERE {where_clause}",
                *params,
            )

            rows = await conn.fetch(
                f"""
                SELECT i.*, u.username as creator_username
                FROM investigations i
                LEFT JOIN users u ON i.created_by = u.id
                WHERE {where_clause}
                ORDER BY i.created_at DESC
                LIMIT ${param_idx} OFFSET ${param_idx + 1}
                """,
                *params, page_size, offset,
            )

            total_pages = (total + page_size - 1) // page_size

            return {
                "data": [dict(r) for r in rows],
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
            }

    async def update(self, investigation_id: int, updates: Dict, updated_by: int) -> Optional[Dict]:
        """Actualiza una investigacion."""
        allowed_fields = {"title", "description", "status", "priority", "assigned_unit", "lead_officer", "classification", "tags"}
        fields = {k: v for k, v in updates.items() if k in allowed_fields}

        if not fields:
            return None

        set_clause = ", ".join(f"{k} = ${i+3}" for i, k in enumerate(fields.keys()))
        values = list(fields.values())

        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                UPDATE investigations
                SET {set_clause}, updated_at = $1, updated_by = $2
                WHERE id = ${len(values) + 3}
                RETURNING id, case_id, title, status, priority, updated_at
                """,
                datetime.utcnow(), updated_by, *values, investigation_id,
            )
            logger.info("investigation_updated", investigation_id=investigation_id, fields=list(fields.keys()), updated_by=updated_by)
            return dict(row) if row else None

    async def delete(self, investigation_id: int, deleted_by: int) -> bool:
        """Elimina una investigacion."""
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM investigations WHERE id = $1",
                investigation_id,
            )
            logger.info("investigation_deleted", investigation_id=investigation_id, deleted_by=deleted_by)
            return "DELETE 1" in result

    async def get_stats(self) -> Dict:
        """Estadisticas de investigaciones."""
        async with self.db_pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM investigations")
            by_status = await conn.fetch(
                "SELECT status, COUNT(*) as count FROM investigations GROUP BY status"
            )
            by_priority = await conn.fetch(
                "SELECT priority, COUNT(*) as count FROM investigations GROUP BY priority"
            )
            recent = await conn.fetchval(
                "SELECT COUNT(*) FROM investigations WHERE created_at > NOW() - INTERVAL '30 days'"
            )
            return {
                "total": total,
                "by_status": {r["status"]: r["count"] for r in by_status},
                "by_priority": {r["priority"]: r["count"] for r in by_priority},
                "last_30_days": recent,
            }
