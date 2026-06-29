#!/usr/bin/env python3
"""
CoreSwift schema alignment script.
Compare Rust model struct fields vs actual DB columns, generate ALTER TABLE statements.
"""

import subprocess
import re
import os
import json

# ── 1. Fetch all DB columns ──
def get_db_columns():
    """Returns {tablename: {column_name: {'type':...}}}"""
    result = subprocess.run(
        ['docker', 'exec', '-i', 'swift-postgres-1', 'psql', '-U', 'swift', '-d', 'coreswift'],
        input="""\\t \\a \\f '~'
SELECT table_name, column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_schema='public' AND table_name NOT LIKE '\\_%'
ORDER BY table_name, ordinal_position;""",
        capture_output=True, text=True, timeout=15
    )
    db = {}
    for line in result.stdout.strip().split('\n'):
        if not line.strip() or '~' not in line:
            continue
        parts = line.split('~')
        if len(parts) < 4:
            continue
        tbl, col, dtype, nullable = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
        if tbl not in db:
            db[tbl] = {}
        db[tbl][col] = {'type': dtype, 'nullable': nullable}
    return db

# ── 2. Extract model fields ──
db_columns = get_db_columns()

# Struct-to-table mapping
S2T = {
    'Contact': 'contacts',
    'Company': 'companies',
    'Pipeline': 'pipelines',
    'PipelineStage': 'pipeline_stages',
    'StageHistory': 'opportunity_stage_history',
    'TagCategory': 'tag_categories',
    'Tag': 'tags',
    'TagAssignment': 'tag_assignments',
    'Tenant': 'tenants',
    'User': 'users',
    'List': 'lists',
    'ListMember': 'list_members',
    'ScoreRule': 'score_rules',
    'Score': 'contact_scores',
    'ScoreHistory': 'score_history',
    'AutomationRule': 'automation_rules',
    'Integration': 'integrations',
    'TagMapping': 'tag_mappings',
    'Webhook': 'webhook_endpoints',
    'Event': 'events',
    'DelayedAction': 'delayed_actions',
    'NativeApp': 'native_apps',
    'AppConnection': 'app_connections',
    'AppSyncLog': 'app_sync_logs',
    'AdaCampaignTrigger': 'ada_campaign_triggers',
    'AccountHealth': 'account_health',
    'HealthThreshold': 'health_thresholds',
    'ChecklistTemplate': 'checklist_templates',
    'ChecklistStage': 'checklist_stages',
    'ChecklistInstance': 'checklist_instances',
    'ChecklistProgress': 'checklist_progress',
    'AutomationWebhook': 'automation_webhooks',
    'AutomationWebhookLog': 'automation_webhook_logs',
    'EmailCampaign': 'email_campaigns',
    'CampaignStep': 'email_campaign_steps',
    'CampaignTrigger': 'email_campaign_triggers',
    'CampaignEnrollment': 'email_campaign_enrollments',
    'PortfolioCompany': 'portfolio_companies',
    'IntegrationTarget': 'integration_targets',
    'Affiliate': 'affiliates',
    'Referral': 'referrals',
    'CommissionPayout': 'commission_payouts',
    'AffiliateProduct': 'affiliate_products',
    'AffiliateProductSelection': 'affiliate_product_selections',
    'Plan': 'plans',
    'TenantPlan': 'tenant_plans',
}

model_fields = {}
for root, dirs, files in os.walk('/opt/swift/coreswift/src'):
    for f in files:
        if f == 'models.rs':
            path = os.path.join(root, f)
            with open(path) as fh:
                content = fh.read()
            structs = re.findall(
                r'#\[derive\(.*?sqlx::FromRow.*?\)\]\s*\n\s*pub struct (\w+)\s*\{([^}]+)\}',
                content, re.DOTALL
            )
            for name, fields in structs:
                table = S2T.get(name)
                if table:
                    field_names = re.findall(r'pub\s+(\w+)\s*:', fields)
                    model_fields[table] = field_names

# ── 3. Find mismatches ──
# Also track field->rust type for proper SQL types
# Hand-coded from reading the model files:
rust_types = {
    'contacts': {
        'id': 'UUID', 'tenant_id': 'UUID', 'email': 'VARCHAR(255)', 'phone': 'VARCHAR(50)',
        'first_name': 'VARCHAR(100)', 'last_name': 'VARCHAR(100)',
        'title': 'VARCHAR(255)', 'company_id': 'UUID',
        'gender': 'VARCHAR(20)', 'address_line1': 'TEXT', 'address_line2': 'TEXT',
        'city': 'VARCHAR(100)', 'state': 'VARCHAR(100)', 'postal_code': 'VARCHAR(20)',
        'country': 'VARCHAR(100)', 'notes': 'TEXT',
        'metadata': 'JSONB', 'is_active': 'BOOLEAN',
        'created_at': 'TIMESTAMPTZ', 'updated_at': 'TIMESTAMPTZ',
    },
    'companies': {
        'id': 'UUID', 'tenant_id': 'UUID', 'name': 'VARCHAR(255)',
        'domain': 'VARCHAR(255)', 'industry': 'VARCHAR(100)', 'size': 'VARCHAR(50)',
        'phone': 'VARCHAR(50)', 'address_line1': 'TEXT', 'address_line2': 'TEXT',
        'city': 'VARCHAR(100)', 'state': 'VARCHAR(100)', 'postal_code': 'VARCHAR(20)',
        'country': 'VARCHAR(100)', 'website': 'TEXT', 'notes': 'TEXT',
        'metadata': 'JSONB', 'is_active': 'BOOLEAN',
        'created_at': 'TIMESTAMPTZ', 'updated_at': 'TIMESTAMPTZ',
    },
    'pipelines': {},
    'pipeline_stages': {
        'description': 'TEXT', 'position': 'TEXT', 'is_won_stage': 'BOOLEAN', 'is_lost_stage': 'BOOLEAN',
    },
    'tags': {},
    'tag_assignments': {},
    'tag_categories': {},
    'tenants': {},
    'users': {},
    'lists': {'rules': 'JSONB'},
    'list_members': {'tenant_id': 'UUID', 'added_manually': 'BOOLEAN'},
    'score_rules': {},
    'contact_scores': {'last_event_type': 'VARCHAR(100)', 'last_event_at': 'TIMESTAMPTZ', 'updated_at': 'TIMESTAMPTZ', 'created_at': 'TIMESTAMPTZ'},
    'score_history': {},
    'automation_rules': {},
    'integrations': {},
    'tag_mappings': {'tenant_id': 'UUID', 'local_tag_id': 'UUID', 'direction': 'VARCHAR(20)', 'updated_at': 'TIMESTAMPTZ'},
    'webhook_endpoints': {},
    'events': {},
    'delayed_actions': {'action_type': 'VARCHAR(50)', 'action_config': 'JSONB', 'execute_at': 'TIMESTAMPTZ', 'executed': 'BOOLEAN', 'cancelled': 'BOOLEAN', 'result': 'JSONB', 'updated_at': 'TIMESTAMPTZ'},
    'native_apps': {'access_level': 'VARCHAR(20)', 'is_active': 'BOOLEAN', 'created_at': 'TIMESTAMPTZ', 'updated_at': 'TIMESTAMPTZ'},
    'app_connections': {},
    'app_sync_logs': {},
    'ada_campaign_triggers': {},
    'account_health': {},
    'health_thresholds': {},
    'checklist_templates': {},
    'checklist_stages': {},
    'checklist_instances': {},
    'checklist_progress': {},
    'automation_webhooks': {},
    'automation_webhook_logs': {},
    'email_campaigns': {},
    'email_campaign_steps': {},
    'email_campaign_triggers': {},
    'campaign_enrollments': {},
    'portfolio_companies': {},
    'integration_targets': {},
    'affiliates': {},
    'referrals': {},
    'commission_payouts': {},
    'affiliate_products': {},
    'affiliate_product_selections': {},
    'plans': {},
    'tenant_plans': {},
}

# Patch with types from actual model analysis
for tbl, fields in model_fields.items():
    if tbl not in rust_types:
        rust_types[tbl] = {}

# ── 4. Now do the detailed semantic comparison ──
# For each table, compare field names (allowing for known renames)
rename_map = {
    # (model_field, db_field) -> model_field maps to db_field
    # We note these as "need renaming" rather than "missing"
    'contacts': {
        'title': ('title', 'job_title'),  # code uses 'title', DB has 'job_title' 
    },
    'pipeline_stages': {
        'position': ('position', 'sort_order'),
        'is_won_stage': ('is_won_stage', 'is_won'),
        'is_lost_stage': ('is_lost_stage', 'is_lost'),
        'description': ('description', ''),  # DB doesn't have description
    },
    'opportunity_stage_history': {
        'created_at': ('created_at', 'moved_at'),
    },
    'tag_categories': {
        'updated_at': ('updated_at', ''),  # DB doesn't have updated_at
    },
    'tag_assignments': {
        'created_at': ('created_at', 'assigned_at'),
        'tenant_id': ('tenant_id', ''),  # DB doesn't have tenant_id (derived from tag)
    },
    'list_members': {
        'tenant_id': ('tenant_id', ''),  # DB doesn't have tenant_id (derived from list)
        'created_at': ('created_at', 'added_at'),
        'added_manually': ('added_manually', ''),  # DB doesn't have added_manually
    },
    'lists': {
        'rules': ('rules', 'dynamic_rules'),  # model expects 'rules', DB has 'dynamic_rules'
    },
    'contact_scores': {
        'last_event_type': ('last_event_type', ''),
        'last_event_at': ('last_event_at', ''),
        'updated_at': ('updated_at', ''),
        'created_at': ('created_at', 'calculated_at'),  # model expects created_at, DB has calculated_at
    },
    'score_history': {
        'score_id': ('score_id', ''),  # model expects score_id, DB doesn't have it
        'tenant_id': ('tenant_id', ''),  # DB doesn't have tenant_id
    },
    'automation_rules': {
        'is_enabled': ('is_enabled', 'is_active'),  # column rename
    },
    'tag_mappings': {
        'tenant_id': ('tenant_id', ''),  # DB doesn't have tenant_id (derived from integration)
        'local_tag_id': ('local_tag_id', 'tag_id'),  # rename
        'updated_at': ('updated_at', ''),  # DB doesn't have updated_at
    },
    'delayed_actions': {
        # code expects many more fields than DB has
        'action_type': ('action_type', ''),
        'action_config': ('action_config', ''),
        'execute_at': ('execute_at', ''),
        'executed': ('executed', ''),
        'cancelled': ('cancelled', ''),
        'result': ('result', ''),
        'updated_at': ('updated_at', ''),
    },
    'webhook_endpoints': {
        'timeout_seconds': ('timeout_seconds', 'timeout_ms'),  # name mismatch
        'retry_count': ('retry_count', 'retry_count'),  # code uses i32, DB has retry_count
        'failure_count': ('failure_count', ''),  # code expects, DB has it
    },
    'native_apps': {
        'access_level': ('access_level', ''),
        'is_active': ('is_active', ''),
        'created_at': ('created_at', ''),
        'updated_at': ('updated_at', ''),
    },
    'app_connections': {
        'app_id': ('app_id', 'app_slug'),  # code expects UUID app_id, DB has VARCHAR app_slug
    },
    'app_sync_logs': {
        'app_connection_id': ('app_connection_id', 'app_slug'),  # same rename
    },
    'ada_campaign_triggers': {
        'active': ('active', ''), # bool active in code, DB has no 'active' column
    },
    'automation_webhook_logs': {
        'ip_address': ('ip_address', ''), # code has, DB has ip_address
    },
    'portfolio_companies': {
        'email': ('email', ''),
        'description': ('description', ''),
        'is_active': ('is_active', ''),
    },
    'health_thresholds': {
        'created_at': ('created_at', ''),
        'is_active': ('is_active', ''),
    },
}

# Now check fields that are really missing vs just renamed
missing_columns = {}  # {table: {col: type}}

# For each table in model, check each field
for tbl, fields in model_fields.items():
    if tbl not in db_columns:
        print(f"⚠️ Table '{tbl}' not found in DB at all (needs creation)")
        continue
    
    db_cols = set(db_columns[tbl].keys())
    renames = rename_map.get(tbl, {})
    
    for field in fields:
        if field in db_cols:
            continue  # exists, fine
        
        # Check if it's a rename
        renamed_info = renames.get(field)
        if renamed_info:
            model_f, db_f = renamed_info
            if db_f and db_f in db_cols:
                continue  # renamed but exists in DB under different name
            
            # If db_f is empty, this field is truly missing
            # If db_f exists but isn't in db_cols, also missing
            pass
        
        # Track as missing
        if tbl not in missing_columns:
            missing_columns[tbl] = {}
        
        # Determine type
        rtype = rust_types.get(tbl, {}).get(field, 'TEXT')
        missing_columns[tbl][field] = rtype

# Print report
print("=" * 70)
print("CORESWIFT SCHEMA ALIGNMENT REPORT")
print("=" * 70)

# Group the major ALTER TABLE statements needed
all_alters = []

for tbl, cols in sorted(missing_columns.items()):
    print(f"\n--- {tbl} ---")
    for col, coltype in sorted(cols.items()):
        nullable = "NULL" if coltype != 'UUID' else "NULL"
        default = ""
        if coltype == 'BOOLEAN':
            default = " DEFAULT false"
        elif col == 'tenant_id' or col == 'is_active':
            pass
        stmt = f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS {col} {coltype}{default};"
        print(f"  {stmt}")
        all_alters.append(stmt)

# Also check the semantic renames that need column additions 
# (where model uses different name than DB)
print("\n\n=== RENAME/DIFFERENT-NAME COLUMNS (need ALTER TABLE ADD) ===")
for tbl, renames in sorted(rename_map.items()):
    if tbl not in db_columns:
        continue
    db_cols = set(db_columns[tbl].keys())
    for model_f, (mfield, dbfield) in renames.items():
        if dbfield and dbfield not in db_cols:
            print(f"  {tbl}: model uses '{model_f}', DB reference '{dbfield}' also missing")
        if not dbfield or dbfield not in db_cols:
            # Need to add the model field as new column
            rtype = rust_types.get(tbl, {}).get(model_f, 'TEXT')
            nullable = "NULL"
            default = ""
            if rtype == 'BOOLEAN':
                default = " DEFAULT false"
            if rtype == 'INTEGER':
                default = " DEFAULT 0"
            stmt = f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS {model_f} {rtype}{default};"
            print(f"  {tbl}: ADD {model_f} ({rtype}) — model uses this, DB doesn't have it")
            all_alters.append(stmt)

print(f"\n\n{'='*70}")
print(f"Total ALTER TABLE statements: {len(all_alters)}")
print(f"{'='*70}")

# Write the ALTER TABLE script
with open('/tmp/coreswift_alter.sql', 'w') as f:
    f.write("-- CoreSwift schema alignment: add missing columns\n")
    f.write("-- Generated by analyze_mismatches.py\n\n")
    for stmt in all_alters:
        f.write(stmt + "\n")
    f.write("\n")

print(f"\nScript written to /tmp/coreswift_alter.sql")

# Also output the model-to-db field mapping for reference
print("\n\n=== VERIFIED TABLES (model matches DB) ===")
for tbl, fields in sorted(model_fields.items()):
    if tbl not in db_columns:
        continue
    db_cols = set(db_columns[tbl].keys())
    missing = [f for f in fields if f not in db_cols]
    extra = [c for c in db_cols if c not in fields]
    missing_info = f" ({len(missing)} missing: {', '.join(missing[:5])})" if missing else ""
    extra_info = f" ({len(extra)} extra: {', '.join(extra[:5])})" if extra else ""
    print(f"  {tbl}: {len(fields)} fields, {len(db_cols)} db cols{missing_info}{extra_info}")
