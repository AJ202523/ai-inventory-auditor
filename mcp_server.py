import json
import sqlite3
import random
import os
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Local MCP Server - Sri Aakriti Jewels")

# --- Agent A Models ---
class SpotPriceRequest(BaseModel):
    metal_string: str

class MarginRequest(BaseModel):
    cost_price: float
    retail_price: float

class ThresholdRequest(BaseModel):
    current_margin: float
    required_margin: float

# --- Agent B Models ---
class InventoryQueryRequest(BaseModel):
    query_type: str
    parameters: Dict[str, Any]

class ValidationRequest(BaseModel):
    sku_string: str
    material_list: List[str]

class FlagRequest(BaseModel):
    sku_id: str
    reason_code: str


# --- Agent A Endpoints ---

@app.post("/fetch_simulated_spot_price")
def fetch_simulated_spot_price(req: SpotPriceRequest):
    try:
        with open("mock_pricing_seed.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Data Source Unreachable")
    
    if req.metal_string.lower() != data["metal"].lower():
        raise HTTPException(status_code=404, detail=f"Metal {req.metal_string} not found in mock data.")
    
    # Apply +/- 5% volatility
    base_price = data["price"]
    volatility = random.uniform(-0.05, 0.05)
    simulated_price = base_price * (1 + volatility)
    
    return {
        "metal": req.metal_string,
        "price": round(simulated_price, 2),
        "unit": data["unit"],
        "is_mock": True,
        "simulated_volatility_applied": True
    }

@app.post("/calculate_gross_margin")
def calculate_gross_margin(req: MarginRequest):
    if req.retail_price <= 0:
        raise HTTPException(status_code=400, detail="Retail price must be > 0")
    
    margin = ((req.retail_price - req.cost_price) / req.retail_price) * 100
    return {"gross_margin_percentage": round(margin, 2)}

@app.post("/evaluate_margin_threshold")
def evaluate_margin_threshold(req: ThresholdRequest):
    # Enforce a minimum 40% threshold logic as mentioned in PRD
    # The requirement asks if current_margin >= required_margin
    is_healthy = req.current_margin >= req.required_margin
    # We also strictly check against the 40% baseline
    meets_baseline = req.current_margin >= 40.0
    
    return {
        "is_healthy": is_healthy and meets_baseline,
        "threshold_checked": req.required_margin,
        "baseline_checked": 40.0
    }

# --- Agent B Endpoints ---

@app.post("/query_local_inventory")
def query_local_inventory(req: InventoryQueryRequest):
    db_path = "mock_inventory.sqlite"
    if not os.path.exists(db_path):
        raise HTTPException(status_code=500, detail="Database not found")
        
    try:
        # Open in read-only mode using uri
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if req.query_type == "get_sku":
            sku_id = req.parameters.get("sku_id")
            cursor.execute("SELECT * FROM inventory WHERE sku_id = ?", (sku_id,))
            row = cursor.fetchone()
            if row:
                return {"data": dict(row)}
            else:
                return {"data": None}
                
        elif req.query_type == "get_all":
            cursor.execute("SELECT * FROM inventory")
            rows = cursor.fetchall()
            return {"data": [dict(r) for r in rows]}
            
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported query_type: {req.query_type}")
            
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'conn' in locals():
            conn.close()

@app.post("/validate_two_tone_isolation")
def validate_two_tone_isolation(req: ValidationRequest):
    """
    Enforces that two-tone items are distinct SKUs, not grouped under pure platinum.
    """
    # Simple heuristic: if the material list indicates multiple metals (e.g. Gold and Platinum)
    # or the text directly implies two-tone, the SKU should have a specific distinct marker (like 'TT')
    # or should not be grouped under a 'PT' only prefix without two-tone indication.
    
    materials_lower = [m.lower() for m in req.material_list]
    has_platinum = any("platinum" in m for m in materials_lower)
    has_other_metal = any(metal in m for m in materials_lower for metal in ["gold", "rose", "yellow", "silver", "two-tone"])
    
    is_two_tone = has_platinum and has_other_metal
    
    # Check if SKU clearly delineates it as two-tone (e.g. contains 'TT' or 'TWO-TONE')
    sku_upper = req.sku_string.upper()
    has_distinct_sku_mapping = "TT" in sku_upper or "TWOTONE" in sku_upper
    
    if is_two_tone and not has_distinct_sku_mapping:
        return {
            "valid": False, 
            "isolation_required": True, 
            "reason": "Two-tone construction requires distinct SKU mapping from pure platinum items."
        }
        
    return {
        "valid": True,
        "isolation_required": False,
        "reason": "SKU structure is compliant."
    }

@app.post("/flag_for_human_review")
def flag_for_human_review(req: FlagRequest):
    # Simulates halting the pipeline and logging the error
    return {
        "status": "HALTED",
        "flagged_sku": req.sku_id,
        "reason": req.reason_code,
        "message": f"Item {req.sku_id} flagged for human review: {req.reason_code}"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
