"""Servicio de gestion de usuarios - CRUD, MFA, bloqueo."""
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import asyncpg
from passlib.context import CryptContext

from src.config.settings import settings
from src.models.schemas import Role
from src.utils.logger import get_logger
from src.utils.security import hash_password, verify_password

logger = get_logger("aegis.user_service")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService:
    """Servicio de gestion de usuarios con seguridad reforzada."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def authenticate(self, username: str, password: str, ip_address: Optional[str] = None) -> Optional[Dict]:
        """Autentica usuario con proteccion contra fuerza bruta.

        Args:
            username: Nombre de usuario
            password: Contrasena en texto plano
            ip_address: IP del cliente para logging

        Returns:
            Dict con datos del usuario si autentica, None si falla
        """
        async with self.db_pool.acquire() as conn:
            # Verificar si el usuario esta bloqueado
            row = await conn.fetchrow(
                """
                SELECT id, username, password_hash, role, is_active,
                       failed_login_attempts, locked_until, mfa_enabled
                FROM users WHERE username = $1
                """,
                username,
            )

            if not row:
                logger.warning("auth_user_not_found", username=username, ip=ip_address)
                return None

            # Verificar bloqueo temporal
            if row["locked_until"] and row["locked_until"] > datetime.utcnow():
                logger.warning("auth_user_locked", username=username, locked_until=row["locked_until"], ip=ip_address)
                return None

            if not row["is_active"]:
                logger.warning("auth_user_inactive", username=username, ip=ip_address)
                return None

            # Verificar password
            if not verify_password(password, row["password_hash"]):
                # Incrementar contador de fallos
                await conn.execute(
                    """
                    UPDATE users
                    SET failed_login_attempts = failed_login_attempts + 1,
                        locked_until = CASE WHEN failed_login_attempts >= 4
                            THEN $1 ELSE locked_until END
                    WHERE id = $2
                    """,
                    datetime.utcnow() + timedelta(minutes=30),
                    row["id"],
                )
                logger.warning("auth_password_failed", username=username, attempts=row["failed_login_attempts"] + 1, ip=ip_address)
                return None

            # Resetear contador de fallos y actualizar last_login
            await conn.execute(
                """
                UPDATE users
                SET failed_login_attempts = 0,
                    locked_until = NULL,
                    last_login = $1
                WHERE id = $2
                """,
                datetime.utcnow(),
                row["id"],
            )

            logger.info("auth_success", username=username, role=row["role"], ip=ip_address)
            return {
                "id": row["id"],
                "username": row["username"],
                "role": row["role"],
                "mfa_enabled": row["mfa_enabled"],
            }

    async def create_user(
        self,
        username: str,
        password: str,
        full_name: str,
        email: str,
        role: Role,
        created_by: int,
    ) -> Dict:
        """Crea un nuevo usuario.

        Args:
            username: Nombre de usuario unico
            password: Contrasena en texto plano (se hashea)
            full_name: Nombre completo
            email: Correo electronico
            role: Rol del usuario
            created_by: ID del usuario que crea

        Returns:
            Dict con datos del usuario creado
        """
        password_hash = hash_password(password)

        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO users (username, password_hash, full_name, email, role, is_active, created_at)
                VALUES ($1, $2, $3, $4, $5, true, $6)
                RETURNING id, username, full_name, email, role, is_active, created_at
                """,
                username, password_hash, full_name, email, role.value, datetime.utcnow(),
            )

            logger.info("user_created", username=username, role=role.value, created_by=created_by)
            return dict(row)

    async def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Obtiene usuario por ID."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, username, full_name, email, role, is_active,
                       mfa_enabled, last_login, created_at
                FROM users WHERE id = $1
                """,
                user_id,
            )
            return dict(row) if row else None

    async def list_users(self, page: int = 1, page_size: int = 20) -> List[Dict]:
        """Lista usuarios paginados."""
        offset = (page - 1) * page_size
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, username, full_name, email, role, is_active,
                       mfa_enabled, last_login, created_at
                FROM users
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                page_size, offset,
            )
            return [dict(r) for r in rows]

    async def update_user(self, user_id: int, updates: Dict) -> Optional[Dict]:
        """Actualiza datos de usuario."""
        allowed_fields = {"full_name", "email", "role", "is_active", "mfa_enabled"}
        fields = {k: v for k, v in updates.items() if k in allowed_fields}

        if not fields:
            return None

        set_clause = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(fields.keys()))
        values = list(fields.values()) + [user_id]

        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                UPDATE users
                SET {set_clause}, updated_at = $1
                WHERE id = ${len(values) + 1}
                RETURNING id, username, full_name, email, role, is_active, updated_at
                """,
                datetime.utcnow(), *values, user_id,
            )
            logger.info("user_updated", user_id=user_id, fields=list(fields.keys()))
            return dict(row) if row else None

    async def change_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """Cambia la contrasena de un usuario."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT password_hash FROM users WHERE id = $1", user_id
            )
            if not row or not verify_password(old_password, row["password_hash"]):
                return False

            new_hash = hash_password(new_password)
            await conn.execute(
                "UPDATE users SET password_hash = $1, updated_at = $2 WHERE id = $3",
                new_hash, datetime.utcnow(), user_id,
            )
            logger.info("password_changed", user_id=user_id)
            return True

    async def delete_user(self, user_id: int, deleted_by: int) -> bool:
        """Elimina (desactiva) un usuario."""
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE users SET is_active = false, updated_at = $1 WHERE id = $2",
                datetime.utcnow(), user_id,
            )
            logger.info("user_deactivated", user_id=user_id, deleted_by=deleted_by)
            return "UPDATE 1" in result

    async def get_user_stats(self) -> Dict:
        """Estadisticas de usuarios."""
        async with self.db_pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM users")
            active = await conn.fetchval("SELECT COUNT(*) FROM users WHERE is_active = true")
            by_role = await conn.fetch(
                "SELECT role, COUNT(*) as count FROM users GROUP BY role"
            )
            return {
                "total": total,
                "active": active,
                "inactive": total - active,
                "by_role": {r["role"]: r["count"] for r in by_role},
            }
