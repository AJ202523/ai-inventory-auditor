# Sri Aakriti Jewels - AI Operations Console

This project is a multi-agent AI operations console designed to audit inventory, evaluate margin health, and generate brand-aligned product copy for a luxury jewelry catalog. 

## System Architecture

The system consists of three main components:
1. **Local MCP Server (`mcp_server.py`)**: A FastAPI backend that exposes various tools (e.g., spot price fetching, margin calculation, SKU validation) for the agents to use.
2. **Multi-Agent Orchestrator (`adk_orchestrator.py`)**: An orchestration pipeline using Google Gemini models that runs three distinct agents:
   - **Agent A (Market Monitor)**: Evaluates the margin health of a given SKU based on current simulated market prices.
   - **Agent B (Catalog Auditor)**: Enforces structural catalog guardrails and performs **Visual Image Validation** (e.g., ensuring two-tone items have distinct SKU mappings and checking uploaded images for material discrepancies).
   - **Agent C (Brand Voice Copywriter)**: Generates sophisticated, luxury-aligned product descriptions for validated SKUs. Includes a **Human-in-the-Loop (HITL)** refinement loop to adjust copy dynamically.
   - **Executive Impact Calculator**: A post-pipeline module that scans for intercepted errors and calculates the simulated revenue protected.
3. **Operations Console (`dashboard.py`)**: A streamlined Streamlit frontend for interacting with the multi-agent pipeline, uploading SKU images, and visualizing the audit results including Executive Impact.

## Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone https://github.com/AJ202523/ai-inventory-auditor.git
   cd capstone_project
   ```

2. **Environment Setup**:
   Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   
   pip install -r requirements.txt
   ```

3. **Configure API Key**:
   Create a `.env` file in the root directory and add your Google Gemini API key:
   ```env
   GOOGLE_API_KEY=your_api_key_here
   ```

## Running the Application

1. **Generate Mock Data**:
   Populate the local mock database and pricing seed by running:
   ```bash
   python generate_mock_data.py
   ```

2. **Start the Backend Server**:
   Start the FastAPI server that provides tools to the agents:
   ```bash
   python mcp_server.py
   ```

3. **Launch the User Interface**:
   In a separate terminal window, start the Streamlit dashboard:
   ```bash
   streamlit run dashboard.py
   ```
   Navigate to `http://localhost:8501` in your web browser to interact with the console. You can now upload product images and interact with the human-in-the-loop copy refinement tools.
