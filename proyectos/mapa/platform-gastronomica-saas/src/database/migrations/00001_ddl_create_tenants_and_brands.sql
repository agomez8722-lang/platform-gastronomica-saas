-- 00001_ddl_create_tenants_and_brands.sql - Multi-tenant base con composite (id, tenant_id)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  plan TEXT DEFAULT 'starter',
  status TEXT DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS brands (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(id, tenant_id),
  UNIQUE(tenant_id, name)
);

CREATE TABLE IF NOT EXISTS sedes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  brand_id UUID NOT NULL,
  name TEXT NOT NULL,
  address TEXT,
  active BOOLEAN DEFAULT true,
  UNIQUE(id, tenant_id),
  UNIQUE(tenant_id, name),
  FOREIGN KEY (brand_id, tenant_id) REFERENCES brands(id, tenant_id)
);

-- RLS igual que tu pg_restaurante en 5433
ALTER TABLE brands ENABLE ROW LEVEL SECURITY;
ALTER TABLE sedes ENABLE ROW LEVEL SECURITY;
CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS UUID AS $$ SELECT NULLIF(current_setting('app.current_tenant_id', true), '')::UUID; $$ LANGUAGE sql STABLE;
DROP POLICY IF EXISTS tenant_isolation ON brands; CREATE POLICY tenant_isolation ON brands FOR ALL USING (tenant_id = current_tenant_id()) WITH CHECK (tenant_id = current_tenant_id());
DROP POLICY IF EXISTS tenant_isolation ON sedes; CREATE POLICY tenant_isolation ON sedes FOR ALL USING (tenant_id = current_tenant_id()) WITH CHECK (tenant_id = current_tenant_id());
