-- CRMSwift Database Schema
-- Everything metadata-driven and configurable

-- ============================================
-- TENANTS & PLANS
-- ============================================

CREATE TABLE IF NOT EXISTS crm_tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  plan_id TEXT NOT NULL DEFAULT 'starter',
  plan_features JSONB DEFAULT '{}',
  metadata JSONB DEFAULT '{}',
  branding JSONB DEFAULT '{}',
  integrations JSONB DEFAULT '{}',
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================
-- PIPELINES & STAGES (Configurable per tenant)
-- ============================================

CREATE TABLE IF NOT EXISTS crm_pipelines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES crm_tenants(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  is_default BOOLEAN DEFAULT false,
  order_index INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS crm_pipeline_stages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  pipeline_id UUID NOT NULL REFERENCES crm_pipelines(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  color TEXT DEFAULT '#94a3b8',
  order_index INTEGER NOT NULL,
  probability INTEGER DEFAULT 0,
  metadata_fields JSONB DEFAULT '[]',
  created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================
-- CONTACTS
-- ============================================

CREATE TABLE IF NOT EXISTS crm_contacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES crm_tenants(id) ON DELETE CASCADE,
  
  -- Core fields
  first_name TEXT,
  last_name TEXT,
  email TEXT,
  phone TEXT,
  
  -- Company
  company_id UUID,
  company_name TEXT,
  job_title TEXT,
  
  -- Source & attribution
  source TEXT,
  source_details JSONB DEFAULT '{}',
  affiliate_code TEXT,
  tracking_token TEXT,
  
  -- Custom metadata
  metadata JSONB DEFAULT '{}',
  tags TEXT[] DEFAULT '{}',
  
  -- Status
  status TEXT DEFAULT 'active',
  last_activity_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_crm_contacts_tenant ON crm_contacts(tenant_id);
CREATE INDEX idx_crm_contacts_email ON crm_contacts(email);
CREATE INDEX idx_crm_contacts_company ON crm_contacts(company_id);

-- ============================================
-- COMPANIES
-- ============================================

CREATE TABLE IF NOT EXISTS crm_companies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES crm_tenants(id) ON DELETE CASCADE,
  
  name TEXT NOT NULL,
  website TEXT,
  industry TEXT,
  company_size TEXT,
  address TEXT,
  
  metadata JSONB DEFAULT '{}',
  tags TEXT[] DEFAULT '{}',
  
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================
-- DEALS
-- ============================================

CREATE TABLE IF NOT EXISTS crm_deals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES crm_tenants(id) ON DELETE CASCADE,
  
  -- Core fields
  title TEXT NOT NULL,
  value DECIMAL(12,2) DEFAULT 0,
  currency TEXT DEFAULT 'USD',
  
  -- Relationships
  contact_id UUID REFERENCES crm_contacts(id),
  company_id UUID REFERENCES crm_companies(id),
  
  -- Pipeline
  pipeline_id UUID REFERENCES crm_pipelines(id),
  stage_id UUID REFERENCES crm_pipeline_stages(id),
  
  -- Deal details
  deal_type TEXT DEFAULT 'new_business',
  priority TEXT DEFAULT 'medium',
  expected_close_date DATE,
  
  -- Source & attribution
  source TEXT,
  affiliate_code TEXT,
  tracking_token TEXT,
  
  -- Custom metadata
  metadata JSONB DEFAULT '{}',
  tags TEXT[] DEFAULT '{}',
  
  -- Status & tracking
  status TEXT DEFAULT 'open',
  won_at TIMESTAMPTZ,
  lost_at TIMESTAMPTZ,
  lost_reason TEXT,
  
  -- Follow-up
  follow_up_at TIMESTAMPTZ,
  follow_up_note TEXT,
  
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_crm_deals_tenant ON crm_deals(tenant_id);
CREATE INDEX idx_crm_deals_stage ON crm_deals(stage_id);
CREATE INDEX idx_crm_deals_contact ON crm_deals(contact_id);
CREATE INDEX idx_crm_deals_follow_up ON crm_deals(follow_up_at);
CREATE INDEX idx_crm_deals_status ON crm_deals(status);

-- ============================================
-- ACTIVITIES
-- ============================================

CREATE TABLE IF NOT EXISTS crm_activities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES crm_tenants(id) ON DELETE CASCADE,
  
  -- Relationships
  deal_id UUID REFERENCES crm_deals(id) ON DELETE CASCADE,
  contact_id UUID REFERENCES crm_contacts(id),
  
  -- Activity details
  activity_type TEXT NOT NULL,
  subject TEXT,
  notes TEXT,
  
  -- Outcome
  outcome TEXT,
  outcome_notes TEXT,
  
  -- Scheduling
  scheduled_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  duration_minutes INTEGER,
  
  -- Custom metadata
  metadata JSONB DEFAULT '{}',
  
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_crm_activities_deal ON crm_activities(deal_id);
CREATE INDEX idx_crm_activities_contact ON crm_activities(contact_id);
CREATE INDEX idx_crm_activities_scheduled ON crm_activities(scheduled_at);

-- ============================================
-- WEBHOOK EVENTS (for n8n integration)
-- ============================================

CREATE TABLE IF NOT EXISTS crm_webhook_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES crm_tenants(id) ON DELETE CASCADE,
  
  event_type TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id UUID,
  
  payload JSONB NOT NULL,
  processed BOOLEAN DEFAULT false,
  processed_at TIMESTAMPTZ,
  error_message TEXT,
  
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_crm_webhook_events_tenant ON crm_webhook_events(tenant_id);
CREATE INDEX idx_crm_webhook_events_processed ON crm_webhook_events(processed);

-- ============================================
-- FUNCTIONS
-- ============================================

-- Update timestamps
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for updated_at
CREATE TRIGGER update_crm_contacts_updated_at
  BEFORE UPDATE ON crm_contacts
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_crm_companies_updated_at
  BEFORE UPDATE ON crm_companies
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_crm_deals_updated_at
  BEFORE UPDATE ON crm_deals
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_crm_activities_updated_at
  BEFORE UPDATE ON crm_activities
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Webhook event creator
CREATE OR REPLACE FUNCTION create_webhook_event(
  p_tenant_id UUID,
  p_event_type TEXT,
  p_entity_type TEXT,
  p_entity_id UUID,
  p_payload JSONB
)
RETURNS UUID AS $$
DECLARE
  v_event_id UUID;
BEGIN
  INSERT INTO crm_webhook_events (
    tenant_id,
    event_type,
    entity_type,
    entity_id,
    payload
  ) VALUES (
    p_tenant_id,
    p_event_type,
    p_entity_type,
    p_entity_id,
    p_payload
  )
  RETURNING id INTO v_event_id;
  
  RETURN v_event_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Deal stage change trigger
CREATE OR REPLACE FUNCTION on_deal_stage_change()
RETURNS TRIGGER AS $$
BEGIN
  IF OLD.stage_id IS DISTINCT FROM NEW.stage_id THEN
    PERFORM create_webhook_event(
      NEW.tenant_id,
      'deal.stage_changed',
      'deal',
      NEW.id,
      jsonb_build_object(
        'deal_id', NEW.id,
        'old_stage_id', OLD.stage_id,
        'new_stage_id', NEW.stage_id,
        'timestamp', now()
      )
    );
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER deal_stage_change_webhook
  AFTER UPDATE ON crm_deals
  FOR EACH ROW
  WHEN (OLD.stage_id IS DISTINCT FROM NEW.stage_id)
  EXECUTE FUNCTION on_deal_stage_change();

-- Get pipeline stats
CREATE OR REPLACE FUNCTION get_pipeline_stats(p_pipeline_id UUID)
RETURNS TABLE (
  stage_id UUID,
  stage_name TEXT,
  deal_count BIGINT,
  total_value DECIMAL,
  weighted_value DECIMAL
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    s.id as stage_id,
    s.name as stage_name,
    COUNT(d.id) as deal_count,
    COALESCE(SUM(d.value), 0) as total_value,
    COALESCE(SUM(d.value * s.probability / 100), 0) as weighted_value
  FROM crm_pipeline_stages s
  LEFT JOIN crm_deals d ON d.stage_id = s.id AND d.status = 'open'
  WHERE s.pipeline_id = p_pipeline_id
  GROUP BY s.id, s.name, s.order_index
  ORDER BY s.order_index;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get overdue follow-ups
CREATE OR REPLACE FUNCTION get_overdue_followups(p_tenant_id UUID)
RETURNS TABLE (
  deal_id UUID,
  deal_title TEXT,
  company_name TEXT,
  contact_name TEXT,
  follow_up_at TIMESTAMPTZ,
  days_overdue INTEGER
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    d.id as deal_id,
    d.title as deal_title,
    d.company_name,
    CONCAT(c.first_name, ' ', c.last_name) as contact_name,
    d.follow_up_at,
    EXTRACT(DAY FROM now() - d.follow_up_at)::INTEGER as days_overdue
  FROM crm_deals d
  LEFT JOIN crm_contacts c ON c.id = d.contact_id
  WHERE d.tenant_id = p_tenant_id
  AND d.status = 'open'
  AND d.follow_up_at < now()
  ORDER BY d.follow_up_at ASC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Enable RLS
ALTER TABLE crm_tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE crm_pipelines ENABLE ROW LEVEL SECURITY;
ALTER TABLE crm_pipeline_stages ENABLE ROW LEVEL SECURITY;
ALTER TABLE crm_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE crm_companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE crm_deals ENABLE ROW LEVEL SECURITY;
ALTER TABLE crm_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE crm_webhook_events ENABLE ROW LEVEL SECURITY;

-- RLS Policies (simplified - tenant isolation)
CREATE POLICY tenant_isolation ON crm_contacts
  USING (tenant_id = current_setting('app.current_tenant')::UUID);

CREATE POLICY tenant_isolation ON crm_companies
  USING (tenant_id = current_setting('app.current_tenant')::UUID);

CREATE POLICY tenant_isolation ON crm_deals
  USING (tenant_id = current_setting('app.current_tenant')::UUID);

CREATE POLICY tenant_isolation ON crm_activities
  USING (tenant_id = current_setting('app.current_tenant')::UUID);

CREATE POLICY tenant_isolation ON crm_pipelines
  USING (tenant_id = current_setting('app.current_tenant')::UUID);

CREATE POLICY tenant_isolation ON crm_pipeline_stages
  USING (pipeline_id IN (
    SELECT id FROM crm_pipelines 
    WHERE tenant_id = current_setting('app.current_tenant')::UUID
  ));

SELECT 'CRMSwift schema created successfully' as status;
