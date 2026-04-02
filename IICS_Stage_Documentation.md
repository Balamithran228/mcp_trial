# IICS Migration Accelerator: Stage 1 & 2 Technical Documentation

## 2.2 Stage 1 — IICS Mapping Extraction

### 1. Description
This stage enables Cursor AI to securely retrieve live mapping definitions directly from the Informatica Intelligent Cloud Services (IICS) environment using the Model Context Protocol (MCP). It abstracts the complexity of IICS API authentication and export workflows into a single conversational command.

### 2. What is Hardcoded
*   **Object Type Filter**: The system specifically filters for `DTEMPLATE` (Informatica Mapping) objects.
*   **Authentication Flow**: The login URL (`/ma/api/v2/user/login`) and the use of `INFA-SESSION-ID` for subsequent V3 API calls are fixed.
*   **Polling Logic**: A hardcoded 2-second sleep interval is used to poll the IICS export status until it reaches `SUCCESSFUL`.
*   **Dependency Inclusion**: The export request is hardcoded to `includeDependencies: True`, ensuring connections and mapplets are bundled with the mapping.
*   **File Identification**: The logic specifically looks for files ending in `@3.bin` (the internal binary representation of mapping logic) and `.json` (for connection metadata) within the exported ZIP.

### 3. What is Configurable
*   **Mapping Name**: The specific mapping to be migrated is provided by the user (e.g., `get mapping using iics_fetcher m_Sales_Extract`).
*   **Prompt Template**: The final output structure is driven by `prompt_template.txt`. If this file is missing, an embedded fallback template is used.
*   **Credentials**: The `USERNAME` and `PASSWORD` are defined as constants in the fetcher script (though these can be moved to environment variables).
*   **Session Persistence**: The `session.json` file caches the `icSessionId` and `serverUrl` to avoid redundant logins.

### 4. Impact of Changing It
*   **Changing `mapping_name`**: Directly changes the source logic passed to the LLM. If the name is incorrect or partial, the tool will return a "Mapping not found" error.
*   **Changing `includeDependencies`**: If set to `False`, the system would fail to retrieve "Connection JSON," resulting in generic dbt sources without specific database/schema context.

### 5. Example
*   **Current Behavior**: 
    User: `get mapping m_STG_Daily_Sales`
    Output: Fetches `m_STG_Daily_Sales`, includes its source connection names, and injects them into the dbt conversion template.
*   **Modified Behavior** (Changing Template):
    If the template is modified to require "BigQuery" instead of "Snowflake," the tool will still fetch the same Informatica logic but will instruct the AI to generate GoogleSQL syntax instead.

---

## 2.3 Stage 2 — Metadata Preprocessing

### 1. Description
The Preprocessing stage takes the raw, verbose JSON extracted from the IICS binary (`@3.bin`) and strips away non-logical noise. It converts Informatica-specific metadata into a "Logic JSON" structure that focuses exclusively on data transformations, field mappings, and flow dependencies.

### 2. What is Hardcoded
*   **Datatype Mapping**: Rules for converting Informatica types to SQL types (e.g., `decimal` → `number`, `string` → `varchar`, `date` → `timestamp`) are hardcoded in the `get_dtype` helper.
*   **Noise Removal**: UI-specific fields (like `x/y` coordinates) and class-28 fields (redundant expression outputs) are automatically excluded.
*   **Transformation Coverage**: The specific extraction logic for 15+ transformation types (e.g., `ROUTER`, `JOINER`, `AGGREGATOR`) is defined in a static `TYPE_EXTRACTORS` map.
*   **Data Flow Resolution**: The logic that links transformations by resolving `##ID` references to human-readable names is a fixed part of the processing pipeline.

### 3. What is Configurable
*   **Input JSON**: The raw content of the mapping binary extracted during Stage 1.
*   **Extractor Map**: New transformation types (e.g., a custom Java Transformation) can be supported by adding a new entry to the `TYPE_EXTRACTORS` dictionary in `preprocessor.py`.
*   **Output Format**: The structure of the "Logic JSON" (e.g., including or excluding `sql_override`) is determined by the specific extraction functions.

### 4. Impact of Changing It
*   **Token Efficiency**: Preprocessing reduces metadata size by ~82%. Disabling this would cause the LLM to hit context limits or "hallucinate" by trying to interpret UI layout metadata as business logic.
*   **Transformation Support**: If a transformation type (e.g., `UNION`) is removed from the `TYPE_EXTRACTORS` map, the preprocessor falls back to a generic extractor, which might miss crucial join/filter conditions in the final dbt model.

### 5. Example
*   **Current Behavior**:
    Raw Metadata: Contains `$$classInfo`, `layoutData`, and hundreds of audit timestamps.
    Logic JSON: Contains `{"name": "Filter_Active", "type": "FILTER", "condition": "IS_ACTIVE = 1"}`.
*   **Modified Behavior** (Adding Type Support):
    If `extract_java` is extended to include full source code instead of a 300-char snippet, the dbt model will have more context but might consume more tokens in complex mappings.
