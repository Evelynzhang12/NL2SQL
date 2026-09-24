"""Audit log data models"""
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from src.models import StatusEnum


class AuditStage(str, Enum):
    """Pipeline stage names — must match the strings used in
    nl2sql.py's _failure() calls and endpoints.py's failed_stage variable."""
    INPUT_VALIDATION = "input_validation"
    SQL_GENERATION = "sql_generation"
    SAFETY_VALIDATION = "safety_validation"
    SQL_EXECUTION = "sql_execution"
    ANSWER_GENERATION = "answer_generation"
    SAFETY_CHECKS_BUILD = "safety_checks_build"
    ANSWER_GROUNDING = "answer_grounding"
    RESPONSE_GENERATION = "response_generation"
    SQL_PIPELINE = "sql_pipeline"  # fallback for eval_one() itself


class AuditLogCreate(BaseModel):
    """One row to be inserted into audit_logs."""
    request_id: UUID

    user_id: str
    user_name: Optional[str] = None
    user_role: str

    session_id: Optional[str] = None

    question: str
    product_type: str
    generated_sql: Optional[str] = None

    status: StatusEnum
    failed_stage: Optional[AuditStage] = None

    error_type: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    result_row_count: Optional[int] = None

    execution_time_ms: Optional[int] = None
    sql_execution_time_ms: Optional[int] = None
    llm_execution_time_ms: Optional[int] = None

    safety_passed: Optional[bool] = None
    permission_granted: Optional[bool] = None

    metadata: dict[str, Any] = Field(default_factory=dict)
