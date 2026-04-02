#!/usr/bin/env python3
"""
IICS Mapping JSON Extractor - Full Coverage Version
Handles: Source, Target, Expression, Lookup, Filter, Sorter, Joiner,
         Router, Sequence, Aggregator, Rank, Union, Normalizer,
         Mapplet, Java, SQL, and any unknown types (graceful fallback).
Usage: python3 iics_extractor.py input.bin output.json
"""
import json, sys

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_dtype(field):
    pt = field.get('platformType', {})
    sid = pt.get('##SID', '')
    if 'decimal' in sid:       t = 'number'
    elif 'string' in sid:      t = 'varchar'
    elif 'date' in sid or 'time' in sid: t = 'timestamp'
    elif 'integer' in sid:     t = 'integer'
    elif 'boolean' in sid:     t = 'boolean'
    elif 'binary' in sid:      t = 'binary'
    elif 'double' in sid or 'float' in sid: t = 'float'
    else:                      t = sid.split('/')[-1] if sid else 'unknown'
    p = field.get('precision', '')
    s = field.get('scale', 0)
    if t == 'varchar':   return f"varchar({p})"
    if t == 'number':    return f"number({p},{s})"
    if t == 'integer':   return f"integer({p})"
    return t

def slim_fields(fields):
    return [{"name": f['name'], "type": get_dtype(f)} for f in fields
            if f.get('$$class') != 28]   # exclude expression-output fields

def slim_expr_fields(fields):
    return [{"name": f['name'],
             "expr": f.get('expression', ''),
             "type": get_dtype(f)}
            for f in fields if f.get('$$class') == 28]

def resolve_field_mappings(orig_tx):
    """Resolve ##ID references to actual field names."""
    id_to_name = {f['$$ID']: f['name'] for f in orig_tx.get('fields', [])}
    mm = orig_tx.get('manualMappings', {}).get('mappingList', [])
    return [{"from": m['fromFieldName'],
             "to":   id_to_name.get(m['toField'].get('##ID'), '?')}
            for m in mm]

# ── Class ID → type name ──────────────────────────────────────────────────────
# Classes 1-15 are defined in the file metadata; additional ones from IICS docs.
BASE_CLASS_MAP = {
    7:  "EXPRESSION",
    8:  "LOOKUP",
    9:  "FILTER",
    10: "SORTER",
    11: "SOURCE",
    12: "JOINER",
    13: "ROUTER",
    14: "SEQUENCE",
    15: "TARGET",
    # Extended IICS types (class IDs vary by export version; matched by class name below)
}

# Some IICS versions assign different $$class numbers.
# Use the Java class name from $$classInfo as a fallback.
CLASS_NAME_MAP = {
    "TmplExpression":      "EXPRESSION",
    "TmplLookup":          "LOOKUP",
    "TmplFilter":          "FILTER",
    "TmplSorter":          "SORTER",
    "TmplSource":          "SOURCE",
    "TmplJoiner":          "JOINER",
    "TmplRouter":          "ROUTER",
    "TmplGenerator":       "SEQUENCE",
    "TmplTarget":          "TARGET",
    "TmplAggregator":      "AGGREGATOR",
    "TmplRank":            "RANK",
    "TmplUnion":           "UNION",
    "TmplNormalizer":      "NORMALIZER",
    "TmplMapplet":         "MAPPLET",
    "TmplJavaExpression":  "JAVA",
    "TmplSQLTransformation":"SQL",
    "TmplDataMasking":     "DATA_MASKING",
    "TmplWebService":      "WEB_SERVICE",
    "TmplHierarchyParser": "HIERARCHY_PARSER",
    "TmplHierarchyBuilder":"HIERARCHY_BUILDER",
    "TmplAssociation":     "ASSOCIATION",
    "TmplDeduplicate":     "DEDUPLICATE",
    "TmplUpdateStrategy":  "UPDATE_STRATEGY",
}

def resolve_type(tx, class_info):
    cls_id  = tx.get('$$class')
    if cls_id in BASE_CLASS_MAP:
        return BASE_CLASS_MAP[cls_id]
    java_cls = class_info.get(str(cls_id), '')
    short    = java_cls.split('.')[-1]
    if short in CLASS_NAME_MAP:
        return CLASS_NAME_MAP[short]
    return f"UNKNOWN_CLASS_{cls_id}({short})"

# ── Per-type logic extractors ─────────────────────────────────────────────────

def extract_source(tx):
    da  = tx.get('dataAdapter', {})
    obj = da.get('object', {})
    e   = {}
    if obj.get('objectName'):
        e['table']  = obj['objectName']
        e['fields'] = slim_fields(tx.get('fields', []))
    sql = next((p['value'] for p in tx.get('advancedProperties', [])
                if p.get('name') == 'Sql Override' and p.get('value')), None)
    if sql: e['sql_override'] = sql
    ro = tx.get('readOptions', {})
    if ro.get('filterCondition'): e['source_filter'] = ro['filterCondition']
    return e

def extract_target(tx):
    e = extract_source(tx)   # table + fields same structure
    mm = resolve_field_mappings(tx)
    if mm: e['field_mappings'] = mm
    wo = tx.get('writeOptions', {})
    ops = wo.get('operations', [])
    if ops: e['write_operations'] = ops
    uc = tx.get('updateColumns', [])
    if uc: e['update_key_columns'] = uc
    return e

def extract_expression(tx):
    e = {}
    exprs = slim_expr_fields(tx.get('fields', []))
    if exprs: e['expressions'] = exprs
    return e

def extract_lookup(tx):
    e = extract_source(tx)
    lc = tx.get('lookupConditions', [])
    if lc:
        e['lookup_on'] = [f"{c['leftOperand']} {c['operator']} {c['rightOperand']}"
                          for c in lc]
    policy = next((p['value'] for p in tx.get('advancedProperties', [])
                   if p.get('name') == 'Lookup caching enabled'), None)
    if policy: e['cache_enabled'] = policy
    e['multiple_match'] = tx.get('multipleMatchPolicy', 'Use First Value')
    return e

def extract_filter(tx):
    e = {}
    fc = tx.get('filterConditions', [])
    if fc:
        e['filter'] = [f"{f['fieldName']} {f['operator']} {f['filterValue']}"
                       for f in fc]
    adv = tx.get('advancedFilterCondition', '')
    if adv: e['advanced_filter'] = adv
    return e

def extract_sorter(tx):
    e = {}
    se = tx.get('sortEntries', [])
    if se:
        e['sort_by'] = [{"field": s.get('fieldName',''),
                         "asc":   s.get('ascending', True)} for s in se]
    return e

def extract_joiner(tx):
    e = {}
    jc = tx.get('joinConditions', [])
    if jc:
        e['join_on'] = [f"{c['leftOperand']} {c['operator']} {c['rightOperand']}"
                        for c in jc]
    e['join_type'] = tx.get('joinType', 'Normal Join')
    adv = tx.get('advancedJoinCondition', '')
    if adv: e['advanced_join'] = adv
    return e

def extract_router(tx):
    e = {}
    gfc = tx.get('groupFilterConditions', [])
    if gfc:
        e['router_groups'] = [{"group":     g['name'],
                                "condition": g['advancedFilterCondition']}
                               for g in gfc]
    return e

def extract_aggregator(tx):
    e = {}
    fields = tx.get('fields', [])
    group_by = [f['name'] for f in fields if f.get('groupByField') == 'true'
                or f.get('isGroupByKey') == 'true']
    if group_by: e['group_by'] = group_by
    exprs = slim_expr_fields(fields)
    if exprs: e['aggregate_expressions'] = exprs
    return e

def extract_rank(tx):
    e = {}
    fields = tx.get('fields', [])
    rank_port = next((f['name'] for f in fields if f.get('rankPort') == 'true'
                      or f.get('isRankPort') == 'true'), None)
    if rank_port: e['rank_port'] = rank_port
    e['rank_type'] = tx.get('rankType', '')
    e['top_bottom'] = tx.get('topOrBottom', '')
    rc = tx.get('rankCount', '')
    if rc: e['rank_count'] = rc
    return e

def extract_normalizer(tx):
    e = {}
    fields = tx.get('fields', [])
    gcid   = [f['name'] for f in fields if f.get('gcidPort') == 'true']
    if gcid: e['gcid_ports'] = gcid
    occur  = tx.get('numberOfOccurrences', '')
    if occur: e['occurrences'] = occur
    return e

def extract_union(tx):
    e = {}
    groups = tx.get('groups', [])
    input_groups = [g['name'] for g in groups if g.get('input') == 'true']
    if input_groups: e['input_groups'] = input_groups
    return e

def extract_mapplet(tx):
    e = {}
    e['mapplet_name'] = tx.get('mappletPath', tx.get('name', ''))
    params = tx.get('mappletParameters', [])
    if params:
        e['parameters'] = [{"name": p.get('name',''), "value": p.get('value','')}
                           for p in params]
    return e

def extract_java(tx):
    e = {}
    code = tx.get('javaCode', tx.get('code', ''))
    if code: e['java_code_snippet'] = code[:300] + ('...' if len(code) > 300 else '')
    return e

def extract_sql(tx):
    e = {}
    sql = tx.get('sqlQuery', tx.get('sqlExpression', ''))
    if sql: e['sql_query'] = sql
    return e

def extract_generic(tx):
    """Fallback: capture fields and any properties as-is."""
    e = {}
    fields = slim_fields(tx.get('fields', []))
    if fields: e['fields'] = fields
    props = tx.get('advancedProperties', [])
    if props:
        e['properties'] = {p['name']: p['value'] for p in props if p.get('value')}
    return e

TYPE_EXTRACTORS = {
    "SOURCE":          extract_source,
    "TARGET":          extract_target,
    "EXPRESSION":      extract_expression,
    "LOOKUP":          extract_lookup,
    "FILTER":          extract_filter,
    "SORTER":          extract_sorter,
    "JOINER":          extract_joiner,
    "ROUTER":          extract_router,
    "AGGREGATOR":      extract_aggregator,
    "RANK":            extract_rank,
    "NORMALIZER":      extract_normalizer,
    "UNION":           extract_union,
    "MAPPLET":         extract_mapplet,
    "JAVA":            extract_java,
    "SQL":             extract_sql,
    "SEQUENCE":        lambda tx: {},   # no extra logic needed
    "DATA_MASKING":    extract_generic,
    "WEB_SERVICE":     extract_generic,
    "HIERARCHY_PARSER":extract_generic,
    "HIERARCHY_BUILDER":extract_generic,
    "ASSOCIATION":     extract_generic,
    "DEDUPLICATE":     extract_generic,
    "UPDATE_STRATEGY": extract_generic,
}

# ── Main extractor ────────────────────────────────────────────────────────────

def process_mapping_dict(raw):
    content    = raw.get('content', {})
    class_info = raw.get('metadata', {}).get('$$classInfo', {})

    result = {
        "mapping":         content.get('name', ''),
        "document_type":   content.get('documentType', ''),
        "transformations": []
    }

    for tx in content.get('transformations', []):
        kind  = resolve_type(tx, class_info)
        entry = {"name": tx['name'], "type": kind}

        extractor = TYPE_EXTRACTORS.get(kind, extract_generic)
        entry.update(extractor(tx))

        result['transformations'].append(entry)

    # Data flow
    tx_id_to_name = {tx['$$ID']: tx['name'] for tx in content.get('transformations', [])}
    links = list(dict.fromkeys(
        f"{tx_id_to_name.get(lk.get('fromTransformation',{}).get('##ID'),'?')} -> "
        f"{tx_id_to_name.get(lk.get('toTransformation',{}).get('##ID'),'?')}"
        for lk in content.get('links', [])
    ))
    result['data_flow'] = links
    return result

def extract(input_path, output_path):
    with open(input_path) as f:
        raw = json.load(f)

    result = process_mapping_dict(raw)

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)

    orig = len(json.dumps(raw))
    comp = len(json.dumps(result))
    print(f"✅  {input_path}")
    print(f"    Original : {orig:>10,} chars")
    print(f"    Compact  : {comp:>10,} chars  ({100 - comp*100//orig}% reduction)")
    print(f"    Saved to : {output_path}")

def process_mapping_text(mapping_text):
    """Parses a mapping JSON string and returns the processed dictionary."""
    raw = json.loads(mapping_text)
    return process_mapping_dict(raw)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python3 iics_extractor.py input.bin output.json")
        sys.exit(1)
    extract(sys.argv[1], sys.argv[2])
