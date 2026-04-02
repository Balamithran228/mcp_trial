# IICS MCP Tool

An automated AI-driven tool for fetching, parsing, and converting Informatica Intelligent Cloud Services (IICS) mappings into comprehensive AI prompts. This project allows AI coding assistants (like Antigravity, Cursor, Copilot) to automatically understand IICS data integration logic and assist with translating it into modern data stacks (like dbt + Snowflake).

## 🚀 Features
- **Automated Login & Session Handling**: Securely manages IICS authentication.
- **Dynamic Mapping Search**: Finds IICS mappings dynamically by name.
- **Export & Extraction**: Triggers IICS export jobs and extracts the binary ZIP packages.
- **Mapping Preprocessor**: Parses raw binary IICS mapping definitions (`@3.bin`) into clean, structured JSON format.
- **AI Prompt Generation**: Compiles the mapped data flows, sources, and targets into a formatted prompt template for AI consumption.
- **MCP Server Ready**: Built-in support to run as an MCP (Model Context Protocol) server for deep Cursor/AI integration.

---

## 🛠️ Implementation Guide (Setup)

### 1. Prerequisites
- Python 3.9+ installed and added to PATH.
- Git installed.
- Valid IICS Credentials.

### 2. Installation
Clone the repository:
```bash
git clone https://github.com/Balamithran228/mcp_trial.git
cd mcp_trial
```

Create and activate a virtual environment:
- **Windows**: `python -m venv .venv` then `.venv\Scripts\activate`
- **Mac/Linux**: `python3 -m venv .venv` then `source .venv/bin/activate`

Install dependencies:
```bash
pip install -r requirements.txt
```
*(Note for Mac/Linux users: Skip `pywin32` if it causes installation errors, it is only required on Windows).*

### 3. Configuration
Create a `.env` file in the root of the project with your IICS credentials:
```env
IICS_USERNAME=your_email@domain.com
IICS_PASSWORD=your_secure_password
```
*(Do NOT share or commit this file!)*

### 4. Running the Tool
Run the main script and pass the name of the IICS mapping you want to analyze:
```bash
python test_iics_fetch_3.py "Mapping1_snow_to_snow_SCD_type2"
```

The script will:
1. Log into IICS.
2. Search and export the mapping.
3. Parse the data flow.
4. Output a detailed AI Prompt text document to the `debug_output/` folder.

---

## 📖 Explanation Guide (How It Works)

### Core Files
- `test_iics_fetch_3.py`: The **main entry point**. It handles IICS REST API calls (Login, Search, Export, Download), unzips the payload, passes the binary files to the preprocessor, and merges the result into the prompt template.
- `preprocessor.py`: The **core parsing engine**. It takes the raw, complicated IICS mapping files (`@3.bin` / JSON structures) and distills them into a clean `data_flow` model, tracking sources, transformations (Expressions, Lookups, Joiners, Routers), and targets.
- `prompt_template.txt`: The template used to format the final output. It instructs the AI on how to interpret the JSON logic, ensuring context constraints (like Markdown logging) are enforced.
- `mcp_server.py`: An optional wrapper. Allows AI IDEs like Cursor to call this project's functions directly using the Model Context Protocol.
- `AI_SETUP.md`: An autonomous setup instructional file specifically designed for AI agents so they can set up the environment without human intervention.

### The Pipeline Flow
1. **Auth (`POST /ma/api/v2/user/login`)** 
   - Retrieves `icSessionId` and `serverUrl`. Caches them in `session.json`.
2. **Search (`GET /public/core/v3/objects`)** 
   - Finds the object ID for the requested mapping.
3. **Export & Download (`POST /public/core/v3/export`)** 
   - Exports the `DTEMPLATE` object including its dependencies and downloads the `.zip` archive.
4. **Parse** 
   - `preprocessor.py` analyzes the components, extracting `field_mappings`, `lookups`, `filters`, and SCD logic (Slowly Changing Dimensions).
5. **Prompt Assembly** 
   - Populates `{CONNECTION_JSON}` and `{LOGIC_JSON}` in `prompt_template.txt` and writes `ai_prompt_<timestamp>.txt`.

---

## 📝 License
This project is for internal IICS integration trial purposes. Do not push proprietary data or credentials.
