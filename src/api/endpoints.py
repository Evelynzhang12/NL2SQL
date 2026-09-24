"""API route endpoints"""
import asyncio
import json
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from src.core.progress import progress_listener, report_stage

from src.audit.models import AuditLogCreate, AuditStage
from src.audit.repository import insert_audit_log
from src.auth.dependencies import get_current_user
from src.auth.models import CurrentUser
from src.core.nl2sql import eval_one
from src.core.sql2summary import summarize_answer
from src.core.answer_grounding import validate_answer_grounding
from src.core.safety_checks import build_safety_checks
from src.models import QueryRequest, QueryResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["query"])


@router.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    logger.info("Health check requested")
    return {"status": "healthy", "service": "NL2SQL Backend"}


@router.post("/query", response_model=QueryResponse, status_code=200)
async def query(
    req: QueryRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> QueryResponse:
    return await asyncio.to_thread(process_query, req, current_user)


def process_query(req: QueryRequest, current_user: CurrentUser) -> QueryResponse:
    """
    Process a natural language question through the NL2SQL pipeline.

    Every request writes one row to audit_logs, whether it succeeds,
    fails a known business rule (error/blocked/clarify/no_data), or hits
    an unexpected exception. Audit write failures are fail-open — see
    insert_audit_log().

    `failed_stage` here tracks which post-pipeline step was executing if an
    *unexpected* exception occurs (a bug, not a normal business outcome —
    normal business failures are already returned by eval_one() as
    status="error"/"blocked" with their own failed_stage, with a 200
    response). This is only for the "something we didn't anticipate broke"
    case, so the log line and audit record tell us exactly where instead
    of a bare 500.
    """
    product_type = req.product_type.value
    logger.info(f"Processing query ({product_type}): {req.question}")

    request_id = uuid4()
    start_time = time.perf_counter()
    failed_stage = "sql_pipeline"

    try:
        # Stage: sql_generation / safety_validation / sql_execution
        # (already handled inside eval_one; this only catches an
        # unanticipated exception type slipping through it)
        result = eval_one(req.question, product_type=product_type)

        if result.get("status") == "ok":
            report_stage("answer_generation")
        failed_stage = "answer_generation"
        result = summarize_answer(req.question, result)

        failed_stage = "safety_checks_build"
        result["safety_checks"] = build_safety_checks(
            question=req.question,
            sql=result.get("sql"),
            status=result.get("status"),
            message=result.get("message", ""),
        )

        if result.get("status") == "ok":
            failed_stage = "answer_grounding"
            answer_validation = validate_answer_grounding(
                sql=result.get("sql", ""),
                data=result.get("data", {}),
                final_answer=result.get("final_answer", ""),
            )
            result["safety_checks"]["answer_grounding"] = answer_validation

        logger.info(f"Query processed successfully. Status: {result['status']}")

        failed_stage = "response_generation"
        response = QueryResponse(
            status=result["status"],
            message=result.get("message", ""),
            final_answer=result.get("final_answer"),
            sql=result.get("sql"),
            data=result.get("data"),
            missing_slots=result.get("missing_slots"),
            safety_checks=result.get("safety_checks"),
            meta={
                **(result.get("meta") or {}),
                "request_id": str(request_id),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "product_type": product_type,
                "failed_stage": result.get("failed_stage"),
                "processing_time_ms": int((time.perf_counter() - start_time) * 1000),
            },
        )

        execution_time_ms = int((time.perf_counter() - start_time) * 1000)
        execution_checks = (result.get("safety_checks") or {}).get("execution", {})

        insert_audit_log(AuditLogCreate(
            request_id=request_id,
            user_id=current_user.user_id,
            user_name=current_user.user_name,
            user_role=current_user.role.value,
            question=req.question,
            product_type=product_type,
            generated_sql=result.get("sql"),
            status=result["status"],
            failed_stage=result.get("failed_stage"),
            error_type=result.get("error_type"),
            error_message=result.get("message") if result["status"] in ("error", "blocked") else None,
            result_row_count=len(result["data"]["rows"]) if result.get("data") else None,
            execution_time_ms=execution_time_ms,
            safety_passed=execution_checks.get("connection_stable"),
            permission_granted=execution_checks.get("permission_granted", True),
        ))

        return response

    except Exception as e:
        execution_time_ms = int((time.perf_counter() - start_time) * 1000)
        logger.error(
            f"Query processing failed unexpectedly at stage '{failed_stage}': {e}",
            exc_info=True,
        )

        insert_audit_log(AuditLogCreate(
            request_id=request_id,
            user_id=current_user.user_id,
            user_name=current_user.user_name,
            user_role=current_user.role.value,
            question=req.question,
            product_type=product_type,
            status="error",
            failed_stage=AuditStage(failed_stage),
            error_type=type(e).__name__,
            error_message=str(e),
            execution_time_ms=execution_time_ms,
            permission_granted=True,
        ))

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/query/stream")
async def query_stream(req: QueryRequest, current_user: CurrentUser = Depends(get_current_user)):
    """Stream real stage boundaries followed by the same audited query response.

    The blocking SQL/LLM pipeline runs in a worker thread. Each connection owns
    its queue and ContextVar listener, so concurrent requests cannot mix stages.
    Once started, a disconnected request may finish in the worker (and audit),
    but its events are discarded. A transport error never retries the query.
    """
    async def events():
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()
        connected = True

        def publish(event):
            if connected:
                loop.call_soon_threadsafe(queue.put_nowait, event)

        def work():
            token = progress_listener.set(lambda stage: publish({"type": "stage", "stage": stage}))
            try:
                response = process_query(req, current_user)
                publish({"type": "result", "payload": response.model_dump(mode="json")})
            except Exception:
                publish({"type": "error", "message": "Internal server error"})
            finally:
                progress_listener.reset(token)

        task = asyncio.create_task(asyncio.to_thread(work))
        # Keep the worker alive to finish auditing even if the client disconnects.
        task.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)
        try:
            while True:
                event = await queue.get()
                yield json.dumps(event) + "\n"
                if event["type"] in {"result", "error"}:
                    break
        finally:
            connected = False

    return StreamingResponse(events(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
