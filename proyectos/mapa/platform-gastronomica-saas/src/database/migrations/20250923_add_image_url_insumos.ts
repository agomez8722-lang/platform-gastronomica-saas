import { pool } from '../../config/database';

export const up = async () => {
  await pool.query(`ALTER TABLE insumos ADD COLUMN IF NOT EXISTS image_url TEXT;`);
  await pool.query(`ALTER TABLE insumos ADD COLUMN IF NOT EXISTS categoria TEXT;`);
  await pool.query(`ALTER TABLE insumos ADD COLUMN IF NOT EXISTS foto TEXT;`);
};

export const down = async () => {
  await pool.query(`ALTER TABLE insumos DROP COLUMN IF EXISTS image_url;`);
  await pool.query(`ALTER TABLE insumos DROP COLUMN IF EXISTS categoria;`);
  await pool.query(`ALTER TABLE insumos DROP COLUMN IF EXISTS foto;`);
};
