import 'dotenv/config'; import { Pool } from 'pg';
export const pool = new Pool({ connectionString: process.env.DATABASE_URL || 'postgres://postgres:postgres@localhost:5433/saas_restaurantes', max: 20 });
