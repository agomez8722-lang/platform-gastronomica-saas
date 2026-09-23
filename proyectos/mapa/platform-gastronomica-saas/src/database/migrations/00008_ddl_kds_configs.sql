CREATE TABLE IF NOT EXISTS kds_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  tipo_negocio TEXT NOT NULL,
  nombre TEXT NOT NULL,
  config JSONB NOT NULL,
  activo BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(tenant_id, tipo_negocio)
);
INSERT INTO kds_configs (tenant_id, tipo_negocio, nombre, config) VALUES
('00000000-0000-0000-0000-000000000001','restaurante','Restaurante Parrilla','{"layout":"startup","timers":{"rojo":900,"sonido":true,"amarillo":600},"mostrar":{"mesa":true,"notas":true},"columnas":[{"id":"COCINA","color":"#FF5C00","label":"En Fuego"},{"id":"EN_PREP","color":"#EAB308","label":"En Prep"},{"id":"LISTO","color":"#22C55E","label":"Listo"}],"estetica":{"fondo":"#09090B","acento":"#FF5C00"}}'::jsonb),
('00000000-0000-0000-0000-000000000001','cafeteria','Cafetería','{"layout":"minimal","timers":{"rojo":600,"amarillo":300},"columnas":[{"id":"COCINA","color":"#000","label":"Pedidos"},{"id":"LISTO","color":"#22C55E","label":"Listo"}]}'::jsonb),
('00000000-0000-0000-0000-000000000001','bar','Bar','{"layout":"startup","columnas":[{"id":"COCINA","color":"#8B5CF6","label":"Barra"},{"id":"LISTO","color":"#22C55E","label":"Entregado"}]}'::jsonb)
ON CONFLICT (tenant_id, tipo_negocio) DO NOTHING;
