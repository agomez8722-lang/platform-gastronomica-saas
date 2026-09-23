CREATE INDEX IF NOT EXISTS idx_pedidos_tenant_sede_estado ON pedidos(tenant_id, sede_id, estado);
CREATE INDEX IF NOT EXISTS idx_comandas_tenant_pedido ON comandas(tenant_id, pedido_id);
CREATE INDEX IF NOT EXISTS idx_productos_tenant_active ON productos(tenant_id) WHERE true;
