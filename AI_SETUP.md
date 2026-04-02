# AI_SETUP.md — Machine-Readable Project Setup Instructions
# This file is written for an AI assistant (e.g., Antigravity, Cursor, Copilot) to
# fully understand and set up this project on any system (Mac or Linux).

## PROJECT OVERVIEW
- **Name**: IICS MCP Tool
- **Purpose**: Fetch a named mapping from Informatica Intelligent Cloud Services (IICS),
  export it, process the binary mapping definition, and generate a structured AI prompt
  saved to `debug_output/`.
- **Language**: Python 3.9+
- **Platform**: Cross-platform (Windows/Mac/Linux)

---

## FILE STRUCTURE

```
mcp_trial/
├── test_iics_fetch_3.py     # MAIN SCRIPT — entry point, run this
├── preprocessor.py          # Parses raw .bin mapping XML into clean JSON
├── mcp_server.py            # MCP server wrapper (optional, for Cursor integration)
├── prompt_template.txt      # Template for the final AI prompt output
├── requirements.txt         # Python dependencies
├── .env                     # Secrets: IICS_USERNAME, IICS_PASSWORD (CREATE THIS)
├── session.json             # Auto-generated: stores IICS session token (auto-created)
└── debug_output/            # Auto-generated: output AI prompt files saved here
```

---

## REQUIRED ENVIRONMENT VARIABLES (.env file)

Create a `.env` file in the project root with:
```
IICS_USERNAME=<iics_login_email>
IICS_PASSWORD=<iics_login_password>
```

The script uses `python-dotenv` to load these automatically.

---

## SETUP COMMANDS (Mac / Linux)

```bash
# 1. Navigate to project folder
cd ~/projects/mcp_trial

# 2. Create virtual environment
python3 -m venv .venv

# 3. Activate virtual environment
source .venv/bin/activate

# 4. Install dependencies (skip pywin32 on Mac/Linux)
pip install requests python-dotenv mcp pydantic pydantic-settings uvicorn httpx pydantic-settings

# 5. Create .env file with credentials
echo "IICS_USERNAME=your_email@example.com" > .env
echo "IICS_PASSWORD=your_password" >> .env
```

---

## HOW TO RUN

```bash
# Activate venv first
source .venv/bin/activate   # Mac/Linux
# OR
.venv\Scripts\activate      # Windows

# Run the script with a mapping name
python3 test_iics_fetch_3.py "Mapping1_snow_to_snow_SCD_type2"
# OR for a different mapping:
python3 test_iics_fetch_3.py "Mapping1_snow_to_snow_SCD_type2_NEW"
```

---

## WHAT THE SCRIPT DOES (step-by-step)

1. **Login**: POST to `https://dm-ap.informaticacloud.com/ma/api/v2/user/login` → gets `serverUrl` + `icSessionId`
2. **Session Cache**: Saves/loads session from `session.json` to avoid re-login
3. **Search**: GET `{serverUrl}/public/core/v3/objects` → finds object with matching name + type `DTEMPLATE`
4. **Export**: POST to `{serverUrl}/public/core/v3/export` → polls until `SUCCESSFUL`
5. **Download**: GET export package ZIP bytes
6. **Parse**: Extracts `@3.bin` (mapping logic) and `connection*.json` files from ZIP
7. **Process**: Calls `preprocessor.process_mapping_text()` → returns structured dict
8. **Template**: Fills `prompt_template.txt` with `{CONNECTION_JSON}` and `{LOGIC_JSON}`
9. **Save**: Writes final prompt to `debug_output/ai_prompt_<timestamp>.txt`
10. **Print**: Prints final prompt to stdout

---

## OUTPUT

- **File**: `debug_output/ai_prompt_YYYYMMDD_HHMMSS.txt`
- **Content**: A filled prompt template containing:
  - Connection JSON (Snowflake source/target connection details)
  - Logic JSON (parsed mapping: sources, targets, transformations, field mappings, data flow)

---

## DEPENDENCIES

| Package | Purpose |
|---------|---------|
| `requests` | HTTP calls to IICS REST API |
| `python-dotenv` | Load `.env` credentials |
| `mcp` | MCP server framework (for Cursor integration) |
| `pydantic` | Data validation |
| `uvicorn` | ASGI server for MCP |
| `httpx` | Async HTTP (used by mcp) |

> `pywin32` in `requirements.txt` is Windows-only. Skip on Mac/Linux.

---

## ERROR REFERENCE

| Error Message | Cause | Fix |
|--------------|-------|-----|
| `Error: Mapping 'X' not found.` | Mapping name doesn't match | Check exact name in IICS UI |
| `Error: IICS Export failed.` | IICS-side export error | Retry or check IICS permissions |
| `Error: No mapping logic found in export.` | ZIP didn't contain `@3.bin` | May be wrong object type |
| `401` HTTP error | Session expired / wrong credentials | Check `.env` file |
| `ModuleNotFoundError` | Dependencies not installed | Run `pip install -r requirements.txt` |

---

## AI AGENT INSTRUCTIONS

If you are an AI assistant setting this up for a user:
1. Check Python 3.9+ is installed (`python3 --version`)
2. Create and activate a virtual environment
3. Run `pip install requests python-dotenv mcp pydantic pydantic-settings uvicorn httpx`
4. Ask the user for their IICS username and password, write them to `.env`
5. Run: `python3 test_iics_fetch_3.py "<mapping_name>"` where mapping_name is provided by user
6. Check `debug_output/` for the generated prompt file
7. If error, refer to ERROR REFERENCE table above
