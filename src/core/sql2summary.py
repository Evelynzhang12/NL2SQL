"""Answer summarization using LLM"""
from typing import Any, Dict

from src.config import settings
from src.constants import ANSWER_SUMMARY_PROMPT_TEMPLATE
from src.utils.llm import complete
from src.utils.logger import get_logger
from src.utils.data_formatter import format_result_context

logger = get_logger(__name__)


def summarize_answer(
    question: str, result: Dict[str, Any], provider: str | None = None, model: str | None = None
) -> Dict[str, Any]:
    """
    Generate a concise summary answer based on SQL query results.

    Args:
        question: Original natural language question
        result: Result dict from nl2sql.eval_one()
        provider: LLM provider override for the eval harness ("openai" |
            "anthropic" | "gemini"). Production callers never pass this.
        model: Specific model override within the resolved provider. Eval
            harness only.

    Returns:
        Updated result dict with 'final_answer' field added
    """
    status = result.get("status")
    logger.debug(f"Summarizing answer for status: {status}")
    
    # Clarify case - needs user to provide more information
    if status == "clarify":
        missing_info = result.get("missing_slots", {})
        messages = [f"- {key}: {value}" for key, value in missing_info.items()]
        clarify_msg = "Please provide more information:\n" + "\n".join(messages)
        result["final_answer"] = clarify_msg
        logger.info("Clarification answer generated")
        return result
    
    # Error case
    if status == "error":
        result["final_answer"] = f"Error: {result.get('message', 'Unknown error')}"
        logger.info("Error answer generated")
        return result
    
    # No data case
    if status == "no_data":
        result["final_answer"] = result.get(
            "message",
            "No data was found for this query.",
        )
        logger.info("No data answer generated")
        return result
    
    # Success case - use LLM to summarize
    try:
        columns = result["data"]["columns"]
        rows = result["data"]["rows"]
        
        # Format data for better LLM context
        table_context, summary_context = format_result_context(columns, rows, max_rows=5)
        
        # 1.3 Optimization: Extract insights from data
        extractor = InsightsExtractor()
        insights = extractor.extract_insights(columns, rows)
        insights_text = extractor.format_insights_text(insights)
        
        # Combine formatted data with insights
        formatted_rows = f"{table_context}\n\n{summary_context}" if summary_context else table_context
        if insights_text:
            formatted_rows = f"{formatted_rows}\n\nKEY INSIGHTS:\n{insights_text}"
        
        prompt = ANSWER_SUMMARY_PROMPT_TEMPLATE.format(
            question=question,
            sql=result.get("sql", ""),
            columns=", ".join(columns),
            rows=formatted_rows,
        )
        
        logger.debug("Calling LLM to summarize answer (with formatted context)...")

        answer = complete(
            prompt,
            temperature=settings.LLM_TEMPERATURE,
            provider=provider,
            model=model,
        )
        result["final_answer"] = answer
        logger.info("Answer summarization successful")
        
    except Exception as e:
        logger.error(f"Failed to summarize answer: {e}")
        result["final_answer"] = f"Error generating summary: {str(e)}"
    
    return result


class InsightsExtractor:
    """Extracts key insights from query results"""
    
    def extract_insights(self, columns: list, rows: list) -> Dict[str, Any]:
        """
        Extract key insights from query results.
        
        Returns:
            {
                "max": {"column": str, "value": float},
                "min": {"column": str, "value": float},
                "avg": {"column": str, "value": float},
                "trend": str,  # "increasing" | "decreasing" | "stable"
                "volatility": str,  # "high" | "medium" | "low"
                "anomalies": list,
            }
        """
        insights = {
            "max": None,
            "min": None, 
            "avg": None,
            "trend": "stable",
            "volatility": "medium",
            "anomalies": []
        }
        
        if not rows or len(rows) == 0:
            return insights
        
        # Find numeric columns
        numeric_cols = []
        for i, col in enumerate(columns):
            if col.lower() in ["close", "volume", "high", "low", "open", "price", "return"]:
                numeric_cols.append((i, col))
        
        if not numeric_cols:
            return insights
        
        # Extract max/min/avg for first numeric column
        col_idx, col_name = numeric_cols[0]
        values = []
        
        for row in rows:
            try:
                val = float(row[col_idx]) if row[col_idx] is not None else None
                if val is not None:
                    values.append(val)
            except (ValueError, TypeError):
                pass
        
        if values:
            insights["max"] = {"column": col_name, "value": max(values)}
            insights["min"] = {"column": col_name, "value": min(values)}
            insights["avg"] = {"column": col_name, "value": sum(values) / len(values)}
            
            # Simple trend detection
            if len(values) > 1:
                if values[-1] > values[0]:
                    insights["trend"] = "increasing"
                elif values[-1] < values[0]:
                    insights["trend"] = "decreasing"
            
            # Simple volatility detection
            if len(values) > 1:
                avg = sum(values) / len(values)
                variance = sum((x - avg) ** 2 for x in values) / len(values)
                std_dev = variance ** 0.5
                cv = (std_dev / avg) if avg > 0 else 0
                
                if cv > 0.1:
                    insights["volatility"] = "high"
                elif cv > 0.05:
                    insights["volatility"] = "medium"
                else:
                    insights["volatility"] = "low"
        
        return insights
    
    def format_insights_text(self, insights: Dict[str, Any]) -> str:
        """Format insights into readable text for LLM context"""
        text_parts = []
        
        if insights.get("max"):
            text_parts.append(f"Maximum {insights['max']['column']}: {insights['max']['value']:.2f}")
        
        if insights.get("min"):
            text_parts.append(f"Minimum {insights['min']['column']}: {insights['min']['value']:.2f}")
        
        if insights.get("avg"):
            text_parts.append(f"Average {insights['avg']['column']}: {insights['avg']['value']:.2f}")
        
        if insights.get("trend"):
            text_parts.append(f"Trend: {insights['trend'].capitalize()}")
        
        if insights.get("volatility"):
            text_parts.append(f"Volatility: {insights['volatility'].capitalize()}")
        
        return "\n".join(text_parts) if text_parts else ""
