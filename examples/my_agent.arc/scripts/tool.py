# Tool script - called by Script_Node

def process_result(result):
    """Process LLM result."""
    return result.upper()

def format_response(text):
    """Format response for display."""
    return f"[Agent] {text}"
