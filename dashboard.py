import streamlit as st
import asyncio
import sqlite3
import json
import adk_orchestrator
from dotenv import load_dotenv

load_dotenv(override=True)

# Set page config
st.set_page_config(
    page_title="Operations Console - Sri Aakriti Jewels",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for Warm Minimalism
st.markdown("""
<style>
    /* Hide Streamlit Hamburger Menu and Footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Typography Imports */
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600&family=Inter:wght@400;500;600&display=swap');
    
    /* Base Colors & Background */
    .stApp {
        background-color: #FAFAFA;
        color: #2B2B2B;
        font-family: 'Inter', sans-serif;
    }
    
    /* Headers */
    h1, h2, h3 {
        font-family: 'Playfair Display', serif;
        color: #2B2B2B;
    }
    
    /* Secondary Text */
    .secondary-text {
        color: #7A7A7A;
        font-size: 0.9em;
    }
    
    /* Data Cards */
    div.stCard, .data-card, div.stMetric {
        background-color: #FFFFFF;
        border-radius: 8px;
        padding: 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        border: none;
    }
    
    /* Output Blocks */
    .output-card {
        background-color: #FFFFFF;
        border-radius: 8px;
        padding: 24px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    /* Alerts and Flags */
    .alert-box {
        background-color: #C48787;
        color: white;
        padding: 12px;
        border-radius: 8px;
        margin-top: 10px;
    }
    
    .success-box {
        background-color: #8CA58A;
        color: white;
        padding: 12px;
        border-radius: 8px;
        margin-top: 10px;
    }
    
    /* Primary Accent Buttons */
    div.stButton > button {
        background-color: #B89B72;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 10px 24px;
        font-family: 'Inter', sans-serif;
        font-weight: 500;
        transition: background-color 0.2s ease;
    }
    div.stButton > button:hover {
        background-color: #A38760;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to load SKUs
def get_skus():
    try:
        conn = sqlite3.connect("file:mock_inventory.sqlite?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT sku_id, product_name FROM inventory")
        skus = cursor.fetchall()
        conn.close()
        return [f"{sku[0]} - {sku[1]}" for sku in skus]
    except Exception as e:
        return ["Error loading SKUs"]

# ----------------- UI Layout -----------------

# Global Header
col_header_left, col_header_right = st.columns([3, 1])

with col_header_left:
    st.markdown("<h1>Operations Console</h1>", unsafe_allow_html=True)
    st.markdown("<div class='secondary-text'>Last synced: Just now</div>", unsafe_allow_html=True)

with col_header_right:
    st.write("") # Spacer
    skus_list = get_skus()
    selected_sku_raw = st.selectbox("Select SKU to Audit", skus_list, label_visibility="collapsed")
    initiate_btn = st.button("Initiate Audit Cycle", use_container_width=True)

st.divider()

# Session State to hold results
if "audit_results" not in st.session_state:
    st.session_state.audit_results = None

if initiate_btn:
    if selected_sku_raw and "Error" not in selected_sku_raw:
        target_sku = selected_sku_raw.split(" - ")[0]
        with st.spinner(f"Running Multi-Agent Pipeline for {target_sku}..."):
            try:
                # Run the ADK Orchestrator
                final_state = asyncio.run(adk_orchestrator.run_pipeline(target_sku))
                st.session_state.audit_results = final_state
            except Exception as e:
                st.error(f"Pipeline Execution Failed: {str(e)}")

# Display Results if available
if st.session_state.audit_results:
    results = st.session_state.audit_results
    
    st.markdown("<h3>Section 1: The Market Monitor (Agent A)</h3>", unsafe_allow_html=True)
    
    market_summary = results.get("market_data", {}).get("summary", {})
    if isinstance(market_summary, str):
        # The agent might have outputted a string. 
        # But wait, we specified the output_key. It usually contains the text if not using structured schema.
        agent_a_text = market_summary
    else:
        agent_a_text = str(market_summary)
        
    st.markdown(f"<div class='output-card'>{agent_a_text}</div>", unsafe_allow_html=True)
    
    # Check if Agent A reported a margin violation via the deterministic status tag
    if "[MARGIN_VIOLATION]" in agent_a_text:
        st.markdown("<div class='alert-box'>🚨 Alert: Margin Drop Below Threshold Detected.</div>", unsafe_allow_html=True)
    elif "[MARGIN_HEALTHY]" in agent_a_text:
        st.markdown("<div class='success-box'>✅ Margin Health Check Passed.</div>", unsafe_allow_html=True)
        
    st.divider()
    
    st.markdown("<h3>Section 2: Catalog & SKU Auditor (Agent B)</h3>", unsafe_allow_html=True)
    
    audit_summary = results.get("audit_payload", {}).get("summary", "")
    st.markdown(f"<div class='output-card'>{audit_summary}</div>", unsafe_allow_html=True)
    
    if "BLOCKED" in audit_summary.upper() or "Upload Blocked" in audit_summary:
        st.markdown("<div class='alert-box'>❌ Upload Blocked: Two-tone item identified. Must be generated as a distinct SKU.</div>", unsafe_allow_html=True)
    elif "APPROVED" in audit_summary.upper():
        st.markdown("<div class='success-box'>✅ SKU Validation Passed.</div>", unsafe_allow_html=True)

    st.divider()
    
    st.markdown("<h3>Section 3: Brand Voice Output (Agent C)</h3>", unsafe_allow_html=True)
    
    content_summary = results.get("content_generation", {}).get("summary", "")
    
    if "BLOCKED" in audit_summary.upper() or "Upload Blocked" in audit_summary:
        st.info("Copywriting was bypassed due to validation failure in Agent B.")
    else:
        st.markdown("<div class='secondary-text' style='margin-bottom: 10px;'>Draft Card</div>", unsafe_allow_html=True)
        # Using Streamlit's code block for easy copy-to-clipboard functionality
        st.code(content_summary, language="markdown")
else:
    st.info("Select a SKU and click 'Initiate Audit Cycle' to view the operations dashboard.")
