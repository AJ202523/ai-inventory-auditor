# Sri Aakriti Jewels - AI Operations Console

This project is a multi-agent AI operations console designed to audit inventory, evaluate margin health, and generate brand-aligned product copy for a luxury jewelry catalog. 

## Architecture

The system consists of three main components:
1. **Local MCP Server (`mcp_server.py`)**: A FastAPI backend that exposes various tools (e.g., spot price fetching, margin calculation, SKU validation) for the agents to use.
2. **Multi-Agent Orchestrator (`adk_orchestrator.py`)**: An orchestration pipeline using Google Gemini models that runs three distinct agents:
   - **Agent A (Market Monitor)**: Evaluates the margin health of a given SKU based on current simulated market prices.
   - **Agent B (Catalog Auditor)**: Enforces structural catalog guardrails (e.g., ensuring two-tone items have distinct SKU mappings).
   - **Agent C (Brand Voice Copywriter)**: Generates sophisticated, luxury-aligned product descriptions for validated SKUs.
3. **Operations Console (`dashboard.py`)**: A streamlined Streamlit frontend for interacting with the multi-agent pipeline and visualizing the audit results.

## Prerequisites

- Python 3.9+
- A Google Gemini API Key

## Setup & Installation

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd capstone_project
   ```

2. **Create a virtual environment** (optional but recommended):
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**:
   Create a `.env` file in the root directory and add your Google Gemini API key:
   ```env
   GOOGLE_API_KEY=your_api_key_here
   ```

## Running the Application

1. **Generate Mock Data**:
   First, populate the local mock database and pricing seed:
   ```bash
   python generate_mock_data.py
   ```

2. **Start the MCP Server**:
   In a terminal, start the FastAPI server that provides tools to the agents:
   ```bash
   python mcp_server.py
   ```

3. **Launch the Dashboard**:
   In a separate terminal, start the Streamlit application:
   ```bash
   streamlit run dashboard.py
   ```
   Open `http://localhost:8501` in your browser to interact with the console.
