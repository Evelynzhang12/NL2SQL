"""Data formatting utilities for financial query results"""
from typing import Any, List, Dict, Tuple


def format_number(value: Any) -> str:
    """
    Format numeric values for display.
    
    Args:
        value: Numeric value to format
        
    Returns:
        Formatted string representation
    """
    if value is None:
        return "N/A"
    
    if not isinstance(value, (int, float)):
        return str(value)
    
    # Handle very large or small numbers with scientific notation
    if abs(value) >= 1e9:
        return f"{value:.2e}".replace("e+0", "e")
    elif 0 < abs(value) < 0.001:
        return f"{value:.6f}"
    elif isinstance(value, float):
        # Round to 2 decimal places for financial data
        return f"{value:.2f}"
    else:
        return str(value)


def format_table(columns: List[str], rows: List[List[Any]]) -> str:
    """
    Format query results as a readable table.
    
    Args:
        columns: Column names
        rows: List of row data
        
    Returns:
        Formatted table string
    """
    if not rows:
        return "No data available"
    
    # Format all values
    formatted_rows = []
    for row in rows:
        formatted_row = [format_number(cell) for cell in row]
        formatted_rows.append(formatted_row)
    
    # Calculate column widths
    col_widths = []
    for i, col in enumerate(columns):
        max_width = max(
            len(col),
            max(len(formatted_rows[j][i]) for j in range(len(formatted_rows)))
        )
        col_widths.append(max_width + 2)
    
    # Build table
    separator = "+" + "+".join("-" * w for w in col_widths) + "+"
    header = "| " + " | ".join(
        col.ljust(col_widths[i] - 2) for i, col in enumerate(columns)
    ) + " |"
    
    rows_str = []
    for row in formatted_rows:
        row_str = "| " + " | ".join(
            str(val).ljust(col_widths[i] - 2) for i, val in enumerate(row)
        ) + " |"
        rows_str.append(row_str)
    
    table = separator + "\n" + header + "\n" + separator
    for row_str in rows_str:
        table += "\n" + row_str
    table += "\n" + separator
    
    return table


def summarize_data(columns: List[str], rows: List[List[Any]]) -> Dict[str, Any]:
    """
    Generate statistical summary of numeric columns.
    
    Args:
        columns: Column names
        rows: List of row data
        
    Returns:
        Dict with summary statistics
    """
    if not rows:
        return {}
    
    summary = {}
    
    for i, col in enumerate(columns):
        values = []
        for row in rows:
            val = row[i]
            if isinstance(val, (int, float)) and val is not None:
                values.append(float(val))
        
        if values:
            summary[col] = {
                "count": len(values),
                "min": format_number(min(values)),
                "max": format_number(max(values)),
                "avg": format_number(sum(values) / len(values)),
            }
    
    return summary


def format_result_context(
    columns: List[str],
    rows: List[List[Any]],
    max_rows: int = 5
) -> Tuple[str, str]:
    """
    Format result data as context for LLM summarization.
    
    Args:
        columns: Column names
        rows: List of row data
        max_rows: Maximum rows to show in table
        
    Returns:
        Tuple of (table_str, summary_str)
    """
    # Show sample table
    sample_rows = rows[:max_rows]
    table_str = format_table(columns, sample_rows)
    
    # Add row count info
    if len(rows) > max_rows:
        table_str += f"\n... and {len(rows) - max_rows} more rows"
    
    # Generate summary
    summary_data = summarize_data(columns, rows)
    summary_lines = []
    for col, stats in summary_data.items():
        if stats.get("count", 0) > 0:
            summary_lines.append(
                f"  {col}: min={stats['min']}, max={stats['max']}, avg={stats['avg']}"
            )
    
    summary_str = "Summary:\n" + "\n".join(summary_lines) if summary_lines else ""
    
    return table_str, summary_str
