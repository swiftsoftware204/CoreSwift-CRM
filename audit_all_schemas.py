#!/usr/bin/env python3
"""Comprehensive schema audit: compare 204 Rust model structs with actual DB columns."""
import subprocess, os, re, json

# ── 1. Get all DB columns per table ──────────────────────────────────────────
def get_db_columns():
    result = subprocess.run(
        ['docker', 'exec', '-i', 'swift-postgres-1', 'psql', '-U', 'swift', '-d', 'coreswift', '-t', '-A'],
        input=r"""SELECT c.table_name, c.column_name, c.data_type
FROM information_schema.columns c
JOIN information_schema.tables t ON c.table_name = t.table_name AND c.table_schema = t.table_schema
WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
  AND c.table_name NOT LIKE '\_%'
ORDER BY c.table_name, c.ordinal_position;
""",
        capture_output=True, text=True, timeout=10
    ).stdout.strip()
    
    cols = {}
    for line in result.split('\n'):
        if not line.strip():
            continue
        parts = line.split('|')
        if len(parts) >= 2:
            table, col = parts[0].strip(), parts[1].strip()
            dtype = parts[2].strip() if len(parts) >= 3 else ''
            if table not in cols:
                cols[table] = {}
            cols[table][col] = dtype
    return cols

# ── 2. Extract model-struct to table mapping from Rust code ──────────────────
def extract_model_tables():
    """Returns {tablename: [field_names]}. We'll build this from models.rs files
    and also by scanning for literal SQL table name references."""
    models_fields = {}  # {tablename: [field_name, ...]}
    model_structs = {}  # {struct_name: [field_name, ...]}
    
    for root, dirs, files in os.walk('/opt/swift/coreswift/src'):
        for f in files:
            if f == 'models.rs':
                path = os.path.join(root, f)
                with open(path) as fh:
                    content = fh.read()
                # Extract struct definitions
                structs = re.findall(r'pub struct (\w+)\s*\{([^}]+)\}', content, re.DOTALL)
                for name, fields in structs:
                    fields_list = re.findall(r'pub\s+(\w+)\s*:', fields)
                    model_structs[name] = fields_list
    
    # Map struct names to likely table names
    struct_to_table = {}
    for s in model_structs:
        # Common patterns
        t = s.lower()
        if t.endswith('y'):
            t = t[:-1] + 'ies'
        elif t.endswith('s'):
            pass  # already plural
        elif t.endswith('x'):
            pass
        else:
            t = t + 's'
        struct_to_table[s] = t
    
    # Also scan all .rs files for FROM clauses to confirm table names
    table_refs = set()
    for root, dirs, files in os.walk('/opt/swift/coreswift/src'):
        for f in files:
            if f.endswith('.rs'):
                path = os.path.join(root, f)
                with open(path) as fh:
                    content = fh.read()
                # Find all FROM <table> and FROM ONLY <table> patterns
                for m in re.finditer(r'(?:FROM|JOIN|INTO|UPDATE)\s+(?:ONLY\s+)?(?:[".]?\w+[".]?\.)?([a-z_]+)', content, re.IGNORECASE):
                    tbl = m.group(1).lower()
                    if tbl not in ('select', 'where', 'and', 'or', 'on', 'as', 'set', 'values', 'returning', 'true', 'false', 'null', 'not', 'in', 'exists', 'is', 'like', 'between', 'order', 'group', 'limit', 'offset', 'having', 'distinct', 'from', 'join', 'into', 'update'):
                        table_refs.add(tbl)
    
    # Build actual mapping
    for s, fields in model_structs.items():
        t = struct_to_table[s]
        # Use actual table refs if ambiguous
        models_fields[t] = fields
    
    return models_fields, model_structs, table_refs

# ── 3. Also scan SQL queries for explicit column references ─────────────────
def extract_query_columns():
    """Extract SELECT column lists from all .rs files."""
    query_cols = {}  # {tablename: set(column_names)}
    
    for root, dirs, files in os.walk('/opt/swift/coreswift/src'):
        for f in files:
            if f.endswith('.rs'):
                path = os.path.join(root, f)
                with open(path) as fh:
                    content = fh.read()
                
                # Find SELECT ... FROM <table> patterns with explicit column lists
                # (ignore SELECT *)
                selects = re.finditer(
                    r'SELECT\s+(.+?)\s+FROM\s+(?:ONLY\s+)?(?:[".]?\w+[".]?\.)?([a-z_]+)',
                    content, re.IGNORECASE | re.DOTALL
                )
                for m in selects:
                    cols_str = m.group(1).strip()
                    tbl = m.group(2).lower()
                    if cols_str.strip() == '*':
                        continue
                    # Extract column names from the select list
                    # Split by comma but be careful with functions, subqueries
                    cols = set()
                    # Simple split - works for basic cases
                    for part in cols_str.split(','):
                        part = part.strip()
                        # Remove aliases
                        part = re.sub(r'\s+AS\s+\w+', '', part, flags=re.IGNORECASE)
                        # Handle function calls: COUNT(*), MAX(col), etc.
                        part = re.sub(r'\w+\([^)]*\)', '', part)
                        # Remove leading quotes/schema
                        part = part.replace('"', '').replace("'", '')
                        if part and part != ' ' and not part.startswith('$') and not part.startswith('('):
                            # Check if it's a simple column name
                            if re.match(r'^[a-z_][a-z0-9_]*$', part.strip(), re.IGNORECASE):
                                cols.add(part.strip())
                    
                    if tbl not in query_cols:
                        query_cols[tbl] = set()
                    query_cols[tbl] |= cols
    
    return query_cols

# ── MAIN ────────────────────────────────────────────────────────────────────
db_cols = get_db_columns()
print("=== DB HAS TABLES:", sorted(db_cols.keys()), "\n")

model_fields, model_structs, table_refs = extract_model_tables()
print("=== MODEL STRUCTS FOUND:", len(model_structs), "===")
for s, f in sorted(model_structs.items()):
    print(f"  {s}: {f}")

# Unify: tables needed by code = model-field tables + query-column tables
query_cols = extract_query_columns()

print("\n\n=== TABLES REFERENCED IN SQL ===")
for t in sorted(table_refs):
    print(f"  {t}")

print("\n\n=== STRUCT-TO-TABLE MAPPING ===")
model_tables_used = set()
for s, fields in model_structs.items():
    # Find actual table name
    t = s.lower()
    if t.endswith('y'): t = t[:-1] + 'ies'
    elif t.endswith('ss'): pass
    elif not t.endswith('s'): t = t + 's'
    
    # Check if table exists
    if t in db_cols:
        model_tables_used.add(t)
        print(f"  {s} → {t} ✓ ({len(fields)} fields)")
        
        # Compare fields
        db_table_cols = set(db_cols[t].keys())
        model_set = set(fields)
        
        missing_in_db = model_set - db_table_cols
        extra_in_db = db_table_cols - model_set
        
        if missing_in_db:
            print(f"      ⚠️  DB MISSING: {sorted(missing_in_db)}")
        if extra_in_db:
            print(f"      ℹ️  DB extra: {sorted(extra_in_db)[:10]}{'...' if len(extra_in_db) > 10 else ''}")
    else:
        # Try to find real table
        found = False
        for dt in sorted(db_cols.keys()):
            if t in dt or dt in t:
                print(f"  {s} → '{t}' NOT FOUND, closest: '{dt}'")
                found = True
                break
        if not found:
            print(f"  {s} → '{t}' NOT FOUND in DB")

# Show query columns per table
print("\n\n=== QUERY COLUMN REFERENCES (table columns used in SELECT without *) ===")
for t in sorted(query_cols.keys()):
    if t in db_cols:
        qcols = query_cols[t]
        db_table_cols = set(db_cols[t].keys())
        missing = qcols - db_table_cols
        if missing:
            print(f"  {t}: MISSNG IN DB: {sorted(missing)}")
        else:
            print(f"  {t}: all column refs exist ✓")
    else:
        print(f"  {t}: TABLE NOT FOUND in DB")

# Summary of ALL missing columns across model structs
print("\n\n=== SUMMARY: ALL MISSING MODEL COLUMNS ===")
all_missing = {}
for s, fields in model_structs.items():
    t = s.lower()
    if t.endswith('y'): t = t[:-1] + 'ies'
    elif t.endswith('ss'): pass
    elif not t.endswith('s'): t = t + 's'
    
    if t not in db_cols:
        continue
    
    db_table_cols = set(db_cols[t].keys())
    model_set = set(fields)
    missing = model_set - db_table_cols
    if missing:
        all_missing[t] = missing

for t in sorted(all_missing.keys()):
    print(f"  {t}: {sorted(all_missing[t])}")

# Also check for views
print("\n\n=== VIEWS ===")
result = subprocess.run(
    ['docker', 'exec', '-i', 'swift-postgres-1', 'psql', '-U', 'swift', '-d', 'coreswift', '-t', '-A'],
    input=r"SELECT table_name FROM information_schema.views WHERE table_schema = 'public' ORDER BY table_name;",
    capture_output=True, text=True, timeout=10
).stdout.strip()
print(result)
