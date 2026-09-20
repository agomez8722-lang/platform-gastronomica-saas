import { Router } from 'express';
import { Pool } from 'pg';

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 10,
});

const router = Router();

router.post('/', async (req, res) => {
  const tenant_id = req.headers['x-tenant-id'] as string;
  const { sede_id, mesa_id, mensaje, confirmado } = req.body;
  if (!confirmado) return res.json({ reply: "¿Confirmas?" });

  const client = await pool.connect();
  try {
    const kw = mensaje.toLowerCase().includes('bbq')? 'bbq' : mensaje.split(' ')[0];
    let prod = await client.query(`SELECT id FROM productos WHERE tenant_id=$1 AND name ILIKE '%'||$2||'%' LIMIT 1`, [tenant_id, kw]);
    if (prod.rows.length === 0) prod = await client.query(`SELECT id FROM productos WHERE tenant_id=$1 LIMIT 1`, [tenant_id]);
    const producto_id = prod.rows[0].id;

    await client.query('BEGIN');
    try {
      const pr = await client.query(`INSERT INTO pedidos (id, tenant_id, sede_id, mesa_id, estado) VALUES (gen_random_uuid(), $1, $2, $3, 'pendiente') RETURNING id`, [tenant_id, sede_id, mesa_id]);
      const pedidoId = pr.rows[0].id;
      await client.query(`INSERT INTO pedido_items (tenant_id, pedido_id, producto_id, cantidad, precio) VALUES ($1,$2,$3,1,(SELECT price FROM productos WHERE id=$3))`, [tenant_id, pedidoId, producto_id]);
      await client.query(`INSERT INTO estados_pedido (tenant_id, pedido_id, estado) VALUES ($1,$2,'COCINA')`, [tenant_id, pedidoId]);
      await client.query(`INSERT INTO inventario_movimientos (tenant_id, insumo_id, tipo, cantidad, pedido_id) SELECT $1, insumo_id, 'CONSUMO', cantidad, $2 FROM recetas WHERE producto_id=$3 AND tenant_id=$1`, [tenant_id, pedidoId, producto_id]);
      await client.query('COMMIT');
      res.json({ pedido_id: pedidoId, estado: 'COCINA', producto: kw });
    } catch (e) {
      await client.query('ROLLBACK');
      throw e;
    }
  } catch (err:any) {
    console.error(err);
    res.status(500).json({ error: err.message });
  } finally {
    client.release();
  }
});

export default router;
