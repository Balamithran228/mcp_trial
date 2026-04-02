import requests
import time
import zipfile
import io
import os
import datetime
import json
import preprocessor
import sys
import argparse
from dotenv import load_dotenv

load_dotenv()

# --- Constants ---
USERNAME = os.getenv("IICS_USERNAME")
PASSWORD = os.getenv("IICS_PASSWORD")
LOGIN_URL = "https://dm-ap.informaticacloud.com/ma/api/v2/user/login"

# Use absolute paths so the MCP server works regardless of the current working directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(SCRIPT_DIR, "session.json")
PROMPT_TEMPLATE_FILE = os.path.join(SCRIPT_DIR, "prompt_template.txt")
DEBUG_DIR = os.path.join(SCRIPT_DIR, "debug_output")

# --- Fallback Template (Embedded so the tool NEVER fails even if files are missing) ---
DEFAULT_PROMPT_TEMPLATE = """
Setup logging:
 
1) Create or update ".cursor/rules/logging.mdc" (do not create duplicates).
 
2) Add:
 
After every response:
- Save to logs/prompt_log_<timestamp>.md
- Use markdown only (.md), no JSON
- Include:
 
# Prompt
<Original Prompt>
 
# Explanation / Answer
<Generated Response>
 
(VERBATIM: exact copy, no summarization)
 
# Generated Code / SQL / Files
- Include FULL code/files
- No truncation, no "..."
 
# Notes
<Optional>
 
- Always create new file
- Never overwrite logs
 
3) Ensure "logs" folder exists.
4) Confirm setup.
below is the source configuration file contents load it :
CONNECTION JSON:
{CONNECTION_JSON}
---
LOGIC JSON:
{LOGIC_JSON}
"""

def debug_log(msg):
    """Prints to stderr so it doesn't interfere with the tool output (stdout)."""
    print(f"[DEBUG] {msg}", file=sys.stderr)

debug_log(f"Script initialized at: {SCRIPT_DIR}")
debug_log(f"Expected template path: {PROMPT_TEMPLATE_FILE}")

def load_session():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r") as f:
                data = json.load(f)
                return data.get("serverUrl"), data.get("icSessionId")
        except:
            pass
    return None, None

def save_session(server_url, session_id):
    with open(SESSION_FILE, "w") as f:
        json.dump({"serverUrl": server_url, "icSessionId": session_id}, f)

def perform_login():
    debug_log("Logging in to IICS...")
    login_payload = {"@type": "login", "username": USERNAME, "password": PASSWORD}
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    resp = requests.post(LOGIN_URL, json=login_payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    save_session(data["serverUrl"], data["icSessionId"])
    return data["serverUrl"], data["icSessionId"]

def find_mapping_and_connections(zip_bytes):
    mapping_bins = []
    connection_jsons = []
    def search_zip(zf, prefix=""):
        for name in zf.namelist():
            full_path = prefix + name
            if name.endswith("@3.bin"):
                mapping_bins.append(zf.read(name))
            elif name.lower().endswith(".json") and "connection" in name.lower():
                try:
                    content = zf.read(name).decode("utf-8", errors="ignore")
                    connection_jsons.append(content)
                except:
                    pass
            elif name.lower().endswith(".zip"):
                try:
                    search_zip(zipfile.ZipFile(io.BytesIO(zf.read(name))), full_path + "/")
                except:
                    pass
    search_zip(zipfile.ZipFile(io.BytesIO(zip_bytes)))
    return mapping_bins, connection_jsons

def get_iics_mapping_prompt(mapping_name):
    """
    Main entry point for AI tools. Performs the end-to-end fetch and transformation flow.
    
    Args:
        mapping_name (str): The exact name or suffix of the IICS mapping.
        
    Returns:
        str: A massive, self-contained prompt string that instructs an AI on how to 
             convert the fetched JSON data into a Snowflake dbt project.
    """
    try:
        # 1. Session Handling
        server_url, session_id = load_session()
        if not (server_url and session_id):
            server_url, session_id = perform_login()

        # 2. Search Object
        search_headers = {"INFA-SESSION-ID": session_id, "Accept": "application/json"}
        search_url = f"{server_url}/public/core/v3/objects"
        
        resp = requests.get(search_url, headers=search_headers)
        if resp.status_code == 401:
            debug_log("Session expired. Re-logging...")
            server_url, session_id = perform_login()
            search_headers["INFA-SESSION-ID"] = session_id
            resp = requests.get(search_url, headers=search_headers)
        
        resp.raise_for_status()
        objects = resp.json().get("objects", [])
        
        target_obj = next((o for o in objects if o.get("path", "").endswith(mapping_name) and o.get("type") == "DTEMPLATE"), None)
        if not target_obj:
            return f"Error: Mapping '{mapping_name}' not found."

        object_id = target_obj["id"]

        # 3. Export & Download
        export_url = f"{server_url}/public/core/v3/export"
        export_headers = {"Content-Type": "application/json", "Accept": "application/json", "INFA-SESSION-ID": session_id}
        resp = requests.post(export_url, json={"name": "MCPExport", "objects": [{"id": object_id, "includeDependencies": True}]}, headers=export_headers)
        resp.raise_for_status()
        export_id = resp.json()["id"]

        while True:
            resp = requests.get(f"{server_url}/public/core/v3/export/{export_id}", headers=export_headers)
            state = resp.json()["status"]["state"]
            if state == "SUCCESSFUL": break
            if state == "FAILED": return "Error: IICS Export failed."
            time.sleep(2)

        resp = requests.get(f"{server_url}/public/core/v3/export/{export_id}/package", headers=export_headers)
        resp.raise_for_status()
        
        # 4. Extract & Process
        mapping_bins, connection_jsons = find_mapping_and_connections(resp.content)
        if not mapping_bins: return "Error: No mapping logic found in export."
        
        mapping_text = mapping_bins[0].decode("utf-8", errors="ignore")
        processed_dict = preprocessor.process_mapping_text(mapping_text)
        processed_json_str = json.dumps(processed_dict, indent=2)
        connection_json = connection_jsons[0] if connection_jsons else "{}"

        # 5. Load Template and Return Prompt
        if os.path.exists(PROMPT_TEMPLATE_FILE):
            with open(PROMPT_TEMPLATE_FILE, "r", encoding="utf-8") as f:
                template = f.read()
            debug_log("Loaded template from file.")
        else:
            template = DEFAULT_PROMPT_TEMPLATE
            debug_log("Template file missing. Using embedded fallback template.")
            
        final_prompt = template.replace("{CONNECTION_JSON}", connection_json).replace("{LOGIC_JSON}", processed_json_str)
        
        if not os.path.exists(DEBUG_DIR):
            os.makedirs(DEBUG_DIR, exist_ok=True)
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        prompt_file_path = os.path.join(DEBUG_DIR, f"ai_prompt_{timestamp}.txt")
        with open(prompt_file_path, "w", encoding="utf-8") as f:
            f.write(final_prompt)
            
        return final_prompt

    except Exception as e:
        return f"Error occurred: {str(e)}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch IICS mapping data and generate AI prompt.")
    parser.add_argument("mapping_name", help="The name of the IICS mapping.")
    args = parser.parse_args()

    result = get_iics_mapping_prompt(args.mapping_name)
    print(result) # Stout is used by Cursor AI
