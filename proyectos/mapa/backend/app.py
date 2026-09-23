import asyncio, json, sqlite3, time, pathlib, ast, importlib.util
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

DB_PATH = "pedidos.db"
BLACKLIST_PATH = "lista_negra.json"
GENOMA_PATH = "genoma_evolutivo.json"
EVOLUTIVO_PATH = "evolutivo_real.py"

app = FastAPI(title="KDS Real + IA Nivel 12")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)

# --- IA Nivel 12 ---
_GENOMA = {"umbral_bloqueo":5,"rate_limit_umbral":6,"rate_limit_ventana":32}
STORE = {} # ip -> [timestamps]

def genoma_actual():
    global _GENOMA
    if pathlib.Path(GENOMA_PATH).exists():
        try:
            data=json.loads(pathlib.Path(GENOMA_PATH).read_text())
            _GENOMA=data.get("genoma",_GENOMA)
        except: pass
    return _GENOMA

def cargar_memoria():
    if pathlib.Path(BLACKLIST_PATH).exists():
        try: return json.loads(pathlib.Path(BLACKLIST_PATH).read_text())
        except: return {}
    return {}

def guardar_memoria(mem):
    pathlib.Path(BLACKLIST_PATH).write_text(json.dumps(mem,indent=2,ensure_ascii=False))

def evaluar_ia(registro: dict):
    # carga dinamica como en tu main.py
    detectores=[]
    try:
        codigo=pathlib.Path(EVOLUTIVO_PATH).read_text()
        ast.parse(codigo)
        spec=importlib.util.spec_from_file_location("evolutivo_real",EVOLUTIVO_PATH)
        mod=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in dir(mod):
            if name.startswith("detectar_"):
                detectores.append(getattr(mod,name))
    except Exception as e:
        print(f"IA load error {e}")
        detectores=[]
    anomalo=False; motivos=[]; ip=registro.get("ip","")
    # rate_limit store
    if ip:
        now=time.time()
        STORE.setdefault(ip,[]).append(now)
        STORE[ip]=[t for t in STORE[ip] if now - t < 60]
    for det in detectores:
        try:
            if "rate_limit" in det.__name__:
                if det(ip, STORE):
                    anomalo=True; motivos.append(det.__name__)
            else:
                if det(registro):
                    anomalo=True; motivos.append(det.__name__)
        except: continue
    # genoma check
    gen=genoma_actual()
    if ip and ip in STORE:
        recent=[t for t in STORE[ip] if time.time()-t < gen.get("rate_limit_ventana",32)]
        if len(recent)>=gen.get("rate_limit_umbral",6):
            anomalo=True; motivos.append("rate_limit_genetico")
    # memoria inmunologica
    if anomalo and ip:
        mem=cargar_memoria()
        mem[ip]=mem.get(ip,0)+1
        guardar_memoria(mem)
    return {"anomalo":anomalo,"motivos":motivos,"detectores":len(detectores),"genoma":gen,"memoria":cargar_memoria()}

# --- SSE Manager ---
class ConnectionManager:
    def __init__(self): self.active_connections: List[asyncio.Queue] = []
    async def connect(self):
        q=asyncio.Queue(); self.active_connections.append(q); return q
    def disconnect(self,q):
        if q in self.active_connections: self.active_connections.remove(q)
    async def broadcast(self, event, data):
        for q in self.active_connections:
            await q.put({"event":event,"data":json.dumps(data,ensure_ascii=False)})

manager=ConnectionManager()

def init_db():
    con=sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS pedidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, numero TEXT, mesa TEXT,
        estado TEXT DEFAULT 'nuevo', items TEXT, total INTEGER,
        estacion TEXT, notas TEXT, created_at TEXT, updated_at TEXT, ip TEXT, motivos TEXT)""")
    con.commit(); con.close()

class Item(BaseModel):
    nombre:str; qty:int=1; notas:Optional[str]=""
class PedidoCreate(BaseModel):
    mesa:str; items:List[Item]; total:int=0; estacion:str="caliente"; notas:Optional[str]=""
class PedidoUpdate(BaseModel):
    estado:str

def get_all():
    con=sqlite3.connect(DB_PATH); con.row_factory=sqlite3.Row
    rows=con.execute("SELECT * FROM pedidos ORDER BY created_at DESC").fetchall(); con.close()
    out=[]
    for r in rows:
        d=dict(r)
        try: d["items"]=json.loads(d["items"])
        except: d["items"]=[]
        out.append(d)
    return out

@app.on_event("startup")
def startup(): init_db(); print(f"KDS + IA Nivel 12 listo - DB {DB_PATH}")

@app.get("/")
def root(): return {"status":"ok","nivel":12,"fitness":200,"ia":True}

@app.get("/health")
def health():
    mem=cargar_memoria()
    return {"status":"ok","nivel":12,"fitness":200,"genoma":genoma_actual(),"ips_bloqueadas":len(mem),"pedidos":len(get_all()),"sse":len(manager.active_connections)}

@app.get("/api/cocina/pedidos")
def listar(): return get_all()

@app.post("/api/cocina/pedidos")
async def crear(p: PedidoCreate, request: Request):
    ip=request.client.host if request.client else "0.0.0.0"
    # si esta bloqueada por genoma
    mem=cargar_memoria()
    if mem.get(ip,0)>=genoma_actual().get("umbral_bloqueo",5):
        return {"detail":f"IP {ip} bloqueada por IA","bloqueada":True,"motivos":["lista_negra"]}

    registro={"rol":"user","recurso":f"/api/cocina/pedidos mesa:{p.mesa}","ip":ip,"hora":datetime.now().strftime("%H:%M:%S"),"user_agent":request.headers.get("user-agent","")}
    ia=evaluar_ia(registro)

    numero=f"PED-{int(time.time())%100000:05d}"; now=datetime.now().isoformat()
    con=sqlite3.connect(DB_PATH); cur=con.cursor()
    cur.execute("INSERT INTO pedidos (numero,mesa,estado,items,total,estacion,notas,created_at,updated_at,ip,motivos) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (numero,p.mesa,"nuevo" if not ia["anomalo"] else "bloqueado",json.dumps([i.dict() for i in p.items],ensure_ascii=False),p.total,p.estacion,p.notas,now,now,ip,json.dumps(ia["motivos"])))
    con.commit(); pid=cur.lastrowid; con.close()
    pedido={"id":pid,"numero":numero,"mesa":p.mesa,"estado":"nuevo" if not ia["anomalo"] else "bloqueado","items":[i.dict() for i in p.items],"total":p.total,"estacion":p.estacion,"notas":p.notas,"created_at":now,"updated_at":now,"ia":ia}

    if ia["anomalo"]:
        await manager.broadcast("pedido_bloqueado",pedido)
        print(f"[IA BLOQUEO] IP {ip} motivos {ia['motivos']} -> {numero}")
    else:
        await manager.broadcast("pedido_nuevo",pedido)
        print(f"[IA OK] {numero} mesa {p.mesa} detectores {ia['detectores']}")

    return pedido

@app.put("/api/cocina/pedidos/{pedido_id}/estado")
@app.patch("/api/cocina/pedidos/{pedido_id}/estado")
@app.patch("/api/cocina/pedidos/{pedido_id}")
@app.put("/api/cocina/pedidos/{pedido_id}")
async def actualizar(pedido_id:int, upd:PedidoUpdate):
    now=datetime.now().isoformat()
    con=sqlite3.connect(DB_PATH); con.execute("UPDATE pedidos SET estado=?, updated_at=? WHERE id=?",(upd.estado,now,pedido_id)); con.commit()
    con.row_factory=sqlite3.Row; r=con.execute("SELECT * FROM pedidos WHERE id=?",(pedido_id,)).fetchone(); con.close()
    if not r: return {"detail":"Not Found"}
    d=dict(r)
    try: d["items"]=json.loads(d["items"])
    except: d["items"]=[]
    await manager.broadcast("pedido_update",d)
    return d

@app.get("/api/cocina/stream")
async def stream(request: Request):
    q=await manager.connect()
    async def gen():
        try:
            yield {"event":"conectado","data":json.dumps({"msg":"KDS+IA conectado","genoma":genoma_actual()})}
            while True:
                if await request.is_disconnected(): break
                try:
                    msg=await asyncio.wait_for(q.get(),timeout=15)
                    yield msg
                except asyncio.TimeoutError:
                    yield {"event":"ping","data":json.dumps({"time":datetime.now().isoformat()})}
        finally: manager.disconnect(q)
    return EventSourceResponse(gen())

@app.get("/api/admin/kds-configs")
def configs(): return [{"id":1,"nombre":"Cocina Principal","estacion":"caliente","sonido":True}]

@app.get("/api/ia/memoria")
def memoria(): return cargar_memoria()
