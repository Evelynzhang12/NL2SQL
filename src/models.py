"""Pydantic models for API requests and responses"""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StatusEnum(str, Enum):
    """Query status enumeration"""
    OK = "ok"
    NO_DATA = "no_data"
    ERROR = "error"
    CLARIFY = "clarify"
    BLOCKED = "blocked"


class ProductTypeEnum(str, Enum):
    """Supported product types"""
    EQUITIES = "equities"
    ETFS = "etfs"
    OPTIONS = "options"
    CRYPTO = "crypto"


class QueryRequest(BaseModel):
    """API request model"""
    question: str = Field(..., min_length=1, max_length=500)
    product_type: ProductTypeEnum = Field(default=ProductTypeEnum.EQUITIES)


class SqlGenerationChecks(BaseModel):
    """SQL generation phase checks"""
    select_only: bool
    no_table_modification: bool
    source_correct: bool


class SafetyValidationChecks(BaseModel):
    """Safety and business rule validation"""
    time_window_correct: bool


class ExecutionChecks(BaseModel):
    """Execution phase checks"""
    permission_granted: bool
    connection_stable: bool


class SafetyChecks(BaseModel):
    """Complete safety checks with three stages"""
    sql_generation: SqlGenerationChecks
    safety_validation: SafetyValidationChecks
    execution: ExecutionChecks
    answer_grounding: Optional[Dict[str, Any]] = None


class QueryResponse(BaseModel):
    """Complete API response model"""
    status: StatusEnum
    message: str = ""
    final_answer: Optional[str] = None
    sql: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    missing_slots: Optional[Dict[str, str]] = None
    safety_checks: Optional[SafetyChecks] = None
    meta: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "final_answer": "The average closing price of NVDA is $100.23",
                "sql": "SELECT AVG(close) FROM stock_data WHERE ticker = 'NVDA'",
                "data": {
                    "columns": ["avg"],
                    "rows": [[100.23]],
                },
                "safety_checks": {
                    "sql_generation": {
                        "select_only": True,
                        "no_table_modification": True,
                        "source_correct": True,
                    },
                    "safety_validation": {"time_window_correct": True},
                    "execution": {
                        "permission_granted": True,
                        "connection_stable": True,
                    },
                },
            }
        }
