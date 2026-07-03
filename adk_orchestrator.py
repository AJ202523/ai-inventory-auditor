import json
import os
import random
import uuid
import datetime
import time
import requests
from typing import Dict, Any, List
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv(override=True)

# ==========================================
# State Management
# ==========================================
class SystemState(BaseModel):
    session_id: str
    timestamp: str
    sku_to_audit: str
    market_data: Dict[str, Any] = {}
    audit_payload: Dict[str, Any] = {}
    content_generation: Dict[str, Any] = {}

# ==========================================
# Tool Functions (Connecting to FastAPI MCP Server)
# ==========================================
BASE_URL = "http://127.0.0.1:8000"
REQUEST_TIMEOUT_SECONDS = 10  # Prevent indefinite hangs if server is slow

def _safe_post(endpoint: str, payload: dict) -> dict:
    """Shared helper – POST to the MCP server with timeout and error handling."""
    try:
        response = requests.post(
            f"{BASE_URL}/{endpoint}",
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        if response.status_code == 200:
            return response.json()
        return {"error": f"Server returned {response.status_code}: {response.text}"}
    except requests.exceptions.ConnectionError:
        return {"error": f"Connection refused – is the MCP server running at {BASE_URL}?"}
    except requests.exceptions.Timeout:
        return {"error": f"Request to {endpoint} timed out after {REQUEST_TIMEOUT_SECONDS}s."}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}

def fetch_simulated_spot_price(metal_string: str) -> dict:
    """Fetches the current spot price for a given metal from the simulated market."""
    return _safe_post("fetch_simulated_spot_price", {"metal_string": metal_string})

def calculate_gross_margin(cost_price: float, retail_price: float) -> dict:
    """Calculates the gross margin percentage given cost and retail prices."""
    return _safe_post("calculate_gross_margin", {"cost_price": cost_price, "retail_price": retail_price})

def evaluate_margin_threshold(current_margin: float, required_margin: float) -> dict:
    """Evaluates if the current margin meets the required threshold (and 40% baseline)."""
    return _safe_post("evaluate_margin_threshold", {"current_margin": current_margin, "required_margin": required_margin})

def query_local_inventory(query_type: str, parameters: dict) -> dict:
    """Queries the local inventory database. Use query_type='get_sku' with parameters={'sku_id': '...'} or 'get_all'."""
    return _safe_post("query_local_inventory", {"query_type": query_type, "parameters": parameters})

def validate_two_tone_isolation(sku_string: str, material_list: List[str]) -> dict:
    """Validates if a two-tone item has a distinct SKU mapping."""
    return _safe_post("validate_two_tone_isolation", {"sku_string": sku_string, "material_list": material_list})

def flag_for_human_review(sku_id: str, reason_code: str) -> dict:
    """Flags a specific SKU for human review and halts its processing."""
    return _safe_post("flag_for_human_review", {"sku_id": sku_id, "reason_code": reason_code})

# Map for dynamic tool execution
TOOL_MAP = {
    "fetch_simulated_spot_price": fetch_simulated_spot_price,
    "calculate_gross_margin": calculate_gross_margin,
    "evaluate_margin_threshold": evaluate_margin_threshold,
    "query_local_inventory": query_local_inventory,
    "validate_two_tone_isolation": validate_two_tone_isolation,
    "flag_for_human_review": flag_for_human_review,
}

# ==========================================
# Agent Execution Loop Helper
# ==========================================

# Mandatory pause between consecutive API calls to naturally throttle request rate.
API_CALL_THROTTLE_SECONDS = 1.0

def generate_content_with_retry(client, model, contents, config, max_retries=5, initial_delay=2.0):
    """Wraps the generate_content call with exponential backoff + jitter for 429 / rate-limit errors.

    - Adds a short mandatory delay before every call to stay under quota.
    - On a 429 (Resource Exhausted) or transient 5xx, waits with exponential
      backoff plus random jitter and retries up to `max_retries` times.
    - All other exceptions are raised immediately.
    """
    # Throttle: always pause briefly before firing the request.
    time.sleep(API_CALL_THROTTLE_SECONDS)

    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
        except Exception as e:
            error_str = str(e).lower()
            is_retryable = (
                "429" in error_str
                or "resource exhausted" in error_str
                or "resourceexhausted" in error_str
                or "503" in error_str
                or "service unavailable" in error_str
            )

            if not is_retryable or attempt == max_retries - 1:
                raise e

            # Exponential backoff with random jitter (±25 %)
            jitter = delay * random.uniform(-0.25, 0.25)
            wait_time = delay + jitter
            print(f"  [Rate Limit] Attempt {attempt + 1}/{max_retries} — "
                  f"{str(e)}. Retrying in {wait_time:.1f}s...")
            time.sleep(wait_time)
            delay *= 2  # double for next potential retry

def run_agent_loop(client: genai.Client, model: str, instruction: str, initial_prompt: str, tools: list) -> str:
    """Manually handles the tool-calling loop using generate_content."""
    config = types.GenerateContentConfig(
        system_instruction=instruction,
        tools=tools,
        temperature=0.2
    )
    
    contents = [
        types.Content(role="user", parts=[types.Part.from_text(text=initial_prompt)])
    ]
    
    while True:
        response = generate_content_with_retry(
            client=client,
            model=model,
            contents=contents,
            config=config
        )
        
        if response.function_calls:
            # Add the model's response (with function calls) to the conversation history
            contents.append(response.candidates[0].content)
            
            tool_responses = []
            for function_call in response.function_calls:
                func_name = function_call.name
                
                # In google.genai, args is a dictionary mapping argument names to values
                kwargs = function_call.args if function_call.args else {}
                
                print(f"  [Tool Execution] {func_name}({kwargs})")
                if func_name in TOOL_MAP:
                    try:
                        res = TOOL_MAP[func_name](**kwargs)
                    except Exception as e:
                        res = {"error": str(e)}
                else:
                    res = {"error": f"Unknown function: {func_name}"}
                    
                tool_responses.append(types.Part.from_function_response(
                    name=func_name,
                    response={"result": res}
                ))
            
            # Add the tool responses back to the model as user role
            contents.append(types.Content(role="user", parts=tool_responses))
        else:
            # No more function calls, return final text
            return response.text

# ==========================================
# Agents
# ==========================================
def run_agent_a(state: SystemState, client: genai.Client):
    print(f"\\n[Agent A: Market Monitor] Running for SKU: {state.sku_to_audit}...")
    instruction = """
    You are Agent A (The Market Monitor). 
    Your goal is to evaluate the margin health of a specific SKU given to you.
    1. Fetch the mock spot price for 'platinum' using the fetch_simulated_spot_price tool.
    2. Query the local inventory for the provided SKU using query_local_inventory (query_type='get_sku', parameters={'sku_id': '<sku>'}).
    3. Calculate the gross margin using calculate_gross_margin (pass cost_price and retail_price from inventory).
    4. Evaluate if it meets a 40.0% threshold using evaluate_margin_threshold (pass current_margin as the gross_margin_percentage you just calculated, and required_margin as 40.0).

    CRITICAL OUTPUT FORMAT:
    - If evaluate_margin_threshold returns is_healthy=True, your summary MUST start with the exact tag: [MARGIN_HEALTHY]
    - If evaluate_margin_threshold returns is_healthy=False, your summary MUST start with the exact tag: [MARGIN_VIOLATION]

    After the tag, provide a concise summary of the market data and the audit results.
    Do NOT use the words 'violation' or 'flagged' anywhere in your output when the margin is healthy.
    """
    
    tools = [fetch_simulated_spot_price, calculate_gross_margin, evaluate_margin_threshold, query_local_inventory]
    
    result = run_agent_loop(
        client=client, 
        model="gemini-3.5-flash", 
        instruction=instruction, 
        initial_prompt=f"Please process SKU: {state.sku_to_audit}",
        tools=tools
    )
    
    print(f"[Agent A Output]\\n{result}")
    state.market_data["summary"] = result

def run_agent_b(state: SystemState, client: genai.Client):
    print(f"\\n[Agent B: Catalog Auditor] Running for SKU: {state.sku_to_audit}...")
    instruction = """
    You are Agent B (The Catalog Auditor).
    Your goal is to enforce structural guardrails on the SKU provided to you.
    1. Query the local inventory for the SKU using query_local_inventory (query_type='get_sku', parameters={'sku_id': '<sku>'}) if you need details.
    2. Read the description and declared_material of the SKU.
    3. Determine the list of materials (e.g. ['Platinum', 'Gold'] if it's two-tone based on description/material).
    4. Use the validate_two_tone_isolation tool to check if the SKU structure is valid.
    5. If validate_two_tone_isolation returns valid=False, use the flag_for_human_review tool and explicitly state "Upload Blocked: Two-tone item identified. Must be generated as a distinct SKU." in your final response.
    
    Output a clear audit status ('APPROVED' or 'BLOCKED') and the associated error message if any.
    """
    
    tools = [query_local_inventory, validate_two_tone_isolation, flag_for_human_review]
    
    result = run_agent_loop(
        client=client, 
        model="gemini-3.1-flash-lite", 
        instruction=instruction, 
        initial_prompt=f"Please audit SKU: {state.sku_to_audit}. Market summary: {state.market_data.get('summary')}",
        tools=tools
    )
    
    print(f"[Agent B Output]\\n{result}")
    state.audit_payload["summary"] = result

def run_agent_c(state: SystemState, client: genai.Client):
    print(f"\\n[Agent C: Brand Voice Copywriter] Running for SKU: {state.sku_to_audit}...")
    instruction = """
    You are Agent C (The Brand Voice Copywriter).
    Your input is the validated SKU details and audit status.
    If the audit status is 'BLOCKED' or the SKU is flagged, DO NOT generate copy. Simply output that copywriting was bypassed due to validation failure.
    If 'APPROVED', generate front-end product descriptions and metadata strings for this SKU based on the provided details.
    
    CRITICAL INSTRUCTION: Adhere to a strict stylistic boundary. Focus entirely on simplicity and sophistication to align with a luxury brand identity. Use ZERO aggressive promotional language or buzzwords.
    
    Format your output cleanly.
    """
    
    # Agent C just generates text, no tools needed
    config = types.GenerateContentConfig(
        system_instruction=instruction,
        temperature=0.4
    )
    
    prompt = f"Please write copy for SKU: {state.sku_to_audit}. Audit Results: {state.audit_payload.get('summary')}"
    response = generate_content_with_retry(
        client=client,
        model="gemini-3.5-flash",
        contents=prompt,
        config=config
    )
    
    result = response.text
    print(f"[Agent C Output]\\n{result}")
    state.content_generation["summary"] = result

# ==========================================
# Orchestration Execution
# ==========================================
async def run_pipeline(target_sku: str) -> dict:
    """Main pipeline execution replacing ADK orchestrator. Kept async to maintain compatibility with dashboard.py"""
    print(f"\\n--- Initiating Vanilla Python Pipeline for SKU: {target_sku} ---")

    # ── Fix 1: Force-reload .env so a rotated API key is picked up immediately
    # without restarting the process. override=True overwrites any previously
    # cached value in os.environ.
    load_dotenv(override=True)

    # Initialize genai client with the *current* key (never stale).
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No API key found. Set GOOGLE_API_KEY or GEMINI_API_KEY in your .env file."
        )
    client = genai.Client(api_key=api_key)

    # Initialize Pydantic State
    state = SystemState(
        session_id=str(uuid.uuid4()),
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        sku_to_audit=target_sku
    )

    for pipeline_attempt in range(2):
        try:
            run_agent_a(state, client)
            # Per-call throttle inside generate_content_with_retry handles
            # rate-limiting; a short courtesy pause between agents is enough.
            time.sleep(2)
            run_agent_b(state, client)
            time.sleep(2)
            run_agent_c(state, client)
            break  # Success
        except Exception as e:
            if pipeline_attempt == 0:
                print(f"Pipeline error ({str(e)}). Waiting 45 seconds for demand spike to resolve before retrying...")
                time.sleep(45)
            else:
                print(f"Pipeline failed after final retry: {str(e)}")
                state.audit_payload["summary"] = f"Pipeline execution error: {str(e)}"
    
    final_state_dict = state.model_dump()
    print("\\n=== FINAL SYSTEM STATE ===")
    print(json.dumps(final_state_dict, indent=2))
    print("--------------------------------------------------\\n")
    
    return final_state_dict

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_pipeline("PT-RING-001"))
    asyncio.run(run_pipeline("PT-RING-007"))
