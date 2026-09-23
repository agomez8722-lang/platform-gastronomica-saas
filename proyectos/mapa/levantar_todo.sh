#!/bin/bash
lsof -ti:8000,3001,5173 | xargs kill -9 2>/dev/null; pkill -f tsx 2>/dev/null; sleep 1
cd ~/ia_evolutiva/proyectos/mapa/backend && nohup python3 -m uvicorn app:app --reload --port 8000 > /tmp/8000.log 2>&1 &
cd ~/ia_evolutiva/proyectos/mapa/platform-gastronomica-saas && nohup npm run dev > /tmp/3001.log 2>&1 &
cd ~/ia_evolutiva/proyectos/mapa/platform-gastronomica-saas && nohup npx vite --port 5173 --host 0.0.0.0 > /tmp/5173.log 2>&1 &
sleep 3
curl -s http://localhost:8000/health | python3 -m json.tool
curl -s http://localhost:3001/health
echo "Frontend KDS con imagen: http://localhost:5173/"
echo "Backend con imagen: http://localhost:8000/ - http://localhost:8000/api/cocina/pedidos"
