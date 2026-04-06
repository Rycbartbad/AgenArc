"""
Math utility functions for demo agent.
"""

def calculate(expression: str) -> dict:
    """
    Safely evaluate a mathematical expression.

    Args:
        expression: A simple math expression like "2 + 2" or "10 * 5"

    Returns:
        Dictionary with result or error
    """
    try:
        # Only allow safe characters
        allowed = set("0123456789+-*/.() ")
        if not all(c in allowed for c in expression):
            return {"error": "Invalid characters in expression"}

        # Evaluate safely
        result = eval(expression)
        return {"result": result, "expression": expression}
    except ZeroDivisionError:
        return {"error": "Division by zero"}
    except Exception as e:
        return {"error": str(e)}


def format_number(num: float, precision: int = 2) -> str:
    """Format a number with specified precision."""
    return f"{num:.{precision}f}"
