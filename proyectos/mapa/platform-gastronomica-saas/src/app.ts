import express from 'express';
import cors from 'cors';
export const app = express();
app.use(cors()); app.use(express.json());
app.get('/', (_,res)=>res.send(`<html><body style="background:#111;color:#eee;text-align:center;padding:40px;font-family:sans-serif">
<h1>🍔 Gastronomica SaaS Chipre Manizales</h1>
<img src="https://images.unsplash.com/photo-1550547660-d9450f859349?w=600&h=400&fit=crop" style="border-radius:16px;max-width:90%"/>
<p><a href="/health" style="color:#f59e0b">/health</a> | <a href="http://localhost:8001/docs">KDS docs 8001</a> | <a href="http://localhost:8001/restaurantes">/restaurantes</a> | <a href="http://localhost:8001/restaurantes/1/platos">/platos</a> | <a href="http://localhost:8001/api/cocina/pedidos">/api/cocina/pedidos</a></p>
<p>12 tablas | 2 pedidos COCINA T10 T11 | 8 pedidos sqlite KDS con foto 16:9 + sonido</p></body></html>`));
app.get('/health',(_,res)=>res.json({ok:true,service:'gastronomica-saas',port:3001,image:'https://images.unsplash.com/photo-1550547660-d9450f859349?w=400',restaurantes:'http://localhost:8001/restaurantes',platos:'http://localhost:8001/restaurantes/1/platos'}));
