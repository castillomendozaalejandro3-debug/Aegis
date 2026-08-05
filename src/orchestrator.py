"""Orquestador LangGraph - Pipeline de analisis OSINT con checkpoints."""
import time
from typing import Any, Dict, Optional

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from src.config.settings import settings
from src.nodes.collect_data import collect_data_node
from src.nodes.analyze_extract import analyze_extract_node
from src.nodes.persist_graph import persist_graph_node
from src.utils.logger import get_logger, set_request_id

logger = get_logger("aegis.orchestrator")


def should_retry(state: Dict[str, Any]) -> str:
    """Decide si reintentar o continuar."""
    if state.get("error"):
        retry_count = state.get("retry_count", 0)
        if retry_count < 3:
            state["retry_count"] = retry_count + 1
            logger.warning("retrying_stage", stage=state.get("stage"), attempt=retry_count + 1)
            return state.get("stage", "collect_data")
        else:
            logger.error("max_retries_exceeded", stage=state.get("stage"))
            return END
    return "analyze_extract"


def error_handler(state: Dict[str, Any]) -> Dict[str, Any]:
    """Maneja errores del pipeline."""
    error = state.get("error", "Unknown error")
    stage = state.get("stage", "unknown")
    logger.error("pipeline_error", stage=stage, error=error)
    state["pipeline_status"] = "FAILED"
    state["pipeline_error"] = error
    return state


def build_pipeline() -> StateGraph:
    """Construye el grafo de estado del pipeline."""
    workflow = StateGraph(Dict[str, Any])

    # Nodos
    workflow.add_node("collect_data", collect_data_node)
    workflow.add_node("analyze_extract", analyze_extract_node)
    workflow.add_node("persist_graph", persist_graph_node)
    workflow.add_node("error_handler", error_handler)

    # Edges
    workflow.set_entry_point("collect_data")
    workflow.add_conditional_edges(
        "collect_data",
        should_retry,
        {
            "collect_data": "collect_data",
            "analyze_extract": "analyze_extract",
            END: "error_handler",
        },
    )
    workflow.add_conditional_edges(
        "analyze_extract",
        should_retry,
        {
            "analyze_extract": "analyze_extract",
            "persist_graph": "persist_graph",
            END: "error_handler",
        },
    )
    workflow.add_conditional_edges(
        "persist_graph",
        should_retry,
        {
            "persist_graph": "persist_graph",
            END: "error_handler",
        },
    )
    workflow.add_edge("error_handler", END)

    return workflow.compile(checkpointer=MemorySaver())


_pipeline = None


def get_pipeline():
    """Singleton del pipeline."""
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
    return _pipeline


def run_pipeline(payload, investigation_id: str) -> Dict[str, Any]:
    """Ejecuta el pipeline completo de analisis OSINT.

    Args:
        payload: Payload de ingesta
        investigation_id: ID de investigacion

    Returns:
        Estado final del pipeline
    """
    request_id = set_request_id()
    start_time = time.time()

    initial_state = {
        "payload": payload,
        "investigation_id": investigation_id,
        "stage": "collect_data",
        "retry_count": 0,
        "error": None,
        "pipeline_status": "RUNNING",
        "request_id": request_id,
        "start_time": start_time,
    }

    pipeline = get_pipeline()

    try:
        final_state = pipeline.invoke(
            initial_state,
            config={"configurable": {"thread_id": investigation_id}},
        )

        elapsed = time.time() - start_time
        final_state["processing_time_seconds"] = round(elapsed, 2)

        if final_state.get("error"):
            final_state["pipeline_status"] = "FAILED"
            logger.error("pipeline_failed", investigation_id=investigation_id, error=final_state["error"], elapsed=elapsed)
        else:
            final_state["pipeline_status"] = "COMPLETED"
            logger.info("pipeline_completed", investigation_id=investigation_id, elapsed=elapsed)

        return final_state

    except Exception as e:
        elapsed = time.time() - start_time
        logger.critical("pipeline_exception", investigation_id=investigation_id, error=str(e), elapsed=elapsed)
        return {
            "investigation_id": investigation_id,
            "pipeline_status": "CRITICAL_FAILURE",
            "error": str(e),
            "processing_time_seconds": round(elapsed, 2),
            "request_id": request_id,
        }
