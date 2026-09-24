"""Audit log persistence — writes to the Neon audit_logs table."""
import json

from sqlalchemy import text

from src.audit.models import AuditLogCreate
from src.utils.db import get_db_engine
from src.utils.logger import get_logger

logger = get_logger(__name__)


INSERT_AUDIT_LOG_SQL = text(
    """
    INSERT INTO audit_logs (
        request_id, user_id, user_name, user_role, session_id,
        question, product_type, generated_sql, status, failed_stage,
        error_type, error_code, error_message, result_row_count,
        execution_time_ms, sql_execution_time_ms, llm_execution_time_ms,
        safety_passed, permission_granted, completed_at, metadata
    )
    VALUES (
        :request_id, :user_id, :user_name, :user_role, :session_id,
        :question, :product_type, :generated_sql, :status, :failed_stage,
        :error_type, :error_code, :error_message, :result_row_count,
        :execution_time_ms, :sql_execution_time_ms, :llm_execution_time_ms,
        :safety_passed, :permission_granted, NOW(), CAST(:metadata AS JSONB)
    )
    """
)


def insert_audit_log(log: AuditLogCreate) -> None:
    """
    Write one audit log row. Never raises — a failure here should not
    break the user-facing query response (fail-open).
    """
    try:
        engine = get_db_engine()

        parameters = {
            "request_id": str(log.request_id),
            "user_id": log.user_id,
            "user_name": log.user_name,
            "user_role": log.user_role,
            "session_id": log.session_id,
            "question": log.question,
            "product_type": log.product_type,
            "generated_sql": log.generated_sql,
            "status": log.status.value,
            "failed_stage": log.failed_stage.value if log.failed_stage else None,
            "error_type": log.error_type,
            "error_code": log.error_code,
            "error_message": log.error_message,
            "result_row_count": log.result_row_count,
            "execution_time_ms": log.execution_time_ms,
            "sql_execution_time_ms": log.sql_execution_time_ms,
            "llm_execution_time_ms": log.llm_execution_time_ms,
            "safety_passed": log.safety_passed,
            "permission_granted": log.permission_granted,
            "metadata": json.dumps(log.metadata),
        }

        with engine.begin() as connection:
            connection.execute(INSERT_AUDIT_LOG_SQL, parameters)

    except Exception as e:
        logger.error(f"Failed to write audit log for request {log.request_id}: {e}", exc_info=True)
