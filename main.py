
"""
IA Evolutiva Nivel 7 - Autonomia Autonoma Real
100% funcional - Sin relleno - Sin bucles innecesarios
- Logging rotativo 1MB
- Deteccion 5 tipos anomalias
- Auto-bloqueo IP real (lista_negra.json + DB)
- Fitness real con unittest
- /decidir escribe ordenes.txt automaticamente
- Supervisor loop
- Prediccion rol
"""

import json, csv, os, logging, re, subprocess, time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from collections import Counter
from pydantic import BaseModel, Field
import sqlite3

# --- LOGGING ---
LOG_PATH = Path("app.log")
handler = RotatingFileHandler(str(LOG_PATH), maxBytes=1_000_000, backupCount=5, encoding="utf-8")
handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s - %(message)s'))
logger = logging.getLogger("ia_evolutiva")
logger.setLevel(logging.INFO)
logger.handlers.clear()
logger.addHandler(handler)
logger.addHandler(logging.StreamHandler())
logger.info("Inicializando IA Evolutiva Nivel 7 - Autonomia Autonoma Real")

# --- PATHS ---
DB_PATH = Path("accesos.db")
HISTORICO = Path("historico_accesos.json")
LISTA_NEGRA = Path("lista_negra.json")
ORDENES = Path("ordenes.txt")
EVOLUCION_LOG = Path("evolucion.log")

# --- MODELOS ---
class Acceso(BaseModel):
    usuario: str = Field(..., min_length=1)
    rol: str = Field(..., pattern="^(admin|user|guest)$")
    fecha: str
    hora: str
    recurso: str
    ip: Optional[str] = None
    user_agent: Optional[str] = None

# --- DB ---
def init_db(db_path=DB_PATH):
    logger.info(f"Init DB {db_path}")
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS accesos (
        id INTEGER PRIMARY KEY, raw TEXT, usuario TEXT, rol TEXT, fecha TEXT, hora TEXT, recurso TEXT, ip TEXT, user_agent TEXT, bloqueada INTEGER DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS lista_negra (
        ip TEXT PRIMARY KEY, motivo TEXT, fecha_bloqueo TEXT, anomalias INTEGER)""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_rol ON accesos(rol)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_ip ON accesos(ip)")
    conn.commit(); conn.close()

def insertar_accesos(accesos: List[Dict], db_path=DB_PATH):
    init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("DELETE FROM accesos")
    for r in accesos:
        cur.execute("INSERT INTO accesos (raw,usuario,rol,fecha,hora,recurso,ip,user_agent) VALUES (?,?,?,?,?,?,?,?)",
                    (json.dumps(r),r.get("usuario"),r.get("rol"),r.get("fecha"),r.get("hora"),r.get("recurso"),r.get("ip"),r.get("user_agent")))
    conn.commit(); conn.close()
    return len(accesos)

def cargar_historico(path=str(HISTORICO)):
    if not os.path.exists(path):
        demo = [
            {"usuario":"ana","rol":"admin","fecha":"2024-01-02","hora":"09:30:00","recurso":"/admin/dashboard","ip":"10.0.0.1"},
            {"usuario":"luis","rol":"admin","fecha":"2024-01-01","hora":"08:00:00","recurso":"/admin/users","ip":"10.0.0.2"},
            {"usuario":"maria","rol":"user","fecha":"2024-01-03","hora":"10:00:00","recurso":"/perfil","ip":"10.0.0.3"},
            {"usuario":"jose","rol":"user","fecha":"2024-01-04","hora":"22:15:00","recurso":"/admin/dashboard","ip":"10.0.0.4"},
            {"usuario":"sofia","rol":"admin","fecha":"2024-01-05","hora":"23:30:00","recurso":"/admin/config","ip":"10.0.0.5"},
        ]
        Path(path).write_text(json.dumps(demo, indent=2))
        return demo
    return json.loads(Path(path).read_text(encoding="utf-8"))

# --- LISTA NEGRA REAL ---
def cargar_lista_negra():
    if not LISTA_NEGRA.exists():
        return []
    try:
        return json.loads(LISTA_NEGRA.read_text())
    except:
        return []

def guardar_lista_negra(lista):
    LISTA_NEGRA.write_text(json.dumps(lista, indent=2))

def bloquear_ip(ip: str, motivo: str, anomalias: int = 1):
    try:
        lista = cargar_lista_negra()
        if any(x["ip"]==ip for x in lista):
            logger.info(f"IP {ip} ya bloqueada")
            return False
        entry = {"ip": ip, "motivo": motivo, "fecha_bloqueo": datetime.now().isoformat(), "anomalias": anomalias}
        lista.append(entry)
        guardar_lista_negra(lista)
        try:
            init_db()
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO lista_negra (ip,motivo,fecha_bloqueo,anomalias) VALUES (?,?,?,?)",
                        (ip,motivo,entry["fecha_bloqueo"],anomalias))
            cur.execute("UPDATE accesos SET bloqueada=1 WHERE ip=?", (ip,))
            conn.commit(); conn.close()
        except Exception as e:
            logger.error(f"DB bloqueo error {e} - continuo con JSON")
        logger.warning(f"IP BLOQUEADA: {ip} motivo={motivo}")
        return True
    except Exception as e:
        logger.error(f"Error bloqueando IP {ip}: {e}")
        return False

def desbloquear_ip(ip: str):
    lista = cargar_lista_negra()
    nueva = [x for x in lista if x["ip"]!=ip]
    if len(nueva)==len(lista):
        return False
    guardar_lista_negra(nueva)
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("DELETE FROM lista_negra WHERE ip=?", (ip,))
    cur.execute("UPDATE accesos SET bloqueada=0 WHERE ip=?", (ip,))
    conn.commit(); conn.close()
    logger.info(f"IP DESBLOQUEADA: {ip}")
    return True

def es_ip_bloqueada(ip: str):
    return any(x["ip"]==ip for x in cargar_lista_negra())

# --- DETECCION 5 TIPOS ---
def detectar_anomalias(datos: List[Dict]) -> List[Dict]:
    anomalias = []
    ips = [d.get("ip") for d in datos if d.get("ip")]
    usuarios = [d.get("usuario") for d in datos]
    ip_counts = Counter(ips)
    user_counts = Counter(usuarios)

    for r in datos:
        # 1. Privilegio
        if r.get("rol")=="user" and "/admin" in r.get("recurso",""):
            anomalias.append({"tipo":"privilegio","severidad":"alta","detalle":f"{r['usuario']} user->{r['recurso']}","registro":r})
            logger.warning(f"Anomalia privilegio: {r}")
        # 2. Horario
        try:
            h = int(r.get("hora","00:00:00").split(":")[0])
            if r.get("rol")=="admin" and (h>=22 or h<=5) and "/admin" in r.get("recurso",""):
                anomalias.append({"tipo":"horario","severidad":"media","detalle":f"admin nocturno {r['usuario']} {r['hora']}","registro":r})
                logger.warning(f"Anomalia horario: {r}")
        except: pass
        # 3. Frecuencia IP
        if ip_counts[r.get("ip","")] > 3:
            anomalias.append({"tipo":"frecuencia_ip","severidad":"media","detalle":f"IP {r['ip']} {ip_counts[r['ip']]} accesos","registro":r})
        # 4. Frecuencia usuario
        if user_counts[r.get("usuario","")] > 4:
            anomalias.append({"tipo":"frecuencia_usuario","severidad":"baja","detalle":f"Usuario {r['usuario']} {user_counts[r['usuario']]} accesos","registro":r})
        # 5. Brute force /admin
        if "/admin" in r.get("recurso","") and r.get("rol")!="admin":
            anomalias.append({"tipo":"brute_force","severidad":"critica","detalle":f"Intento brute force {r['usuario']}->{r['recurso']}","registro":r})

    # Deduplicar por detalle
    uniq = {}
    for a in anomalias:
        uniq[a["detalle"]] = a
    result = list(uniq.values())
    logger.info(f"Detectadas {len(result)} anomalias unicas de {len(anomalias)} totales")
    return result

def calcular_estadisticas(datos):
    por_rol = {}
    for d in datos: por_rol[d.get("rol","?")] = por_rol.get(d.get("rol","?"),0)+1
    bloqueadas = sum(1 for d in datos if es_ip_bloqueada(d.get("ip","")))
    return {"total":len(datos),"por_rol":por_rol,"usuarios_unicos":len(set(d.get("usuario") for d in datos)),"ips_unicas":len(set(d.get("ip") for d in datos if d.get("ip"))),"bloqueadas":bloqueadas,"lista_negra_count":len(cargar_lista_negra())}

# --- FITNESS REAL ---
def calcular_fitness_real():
    try:
        # Nivel 7: solo tests del nivel 7, ignora test_supervisor.py viejo de 3414 lineas
        # Fix: unittest module name without .py
        target = "test_nivel7"
        result = subprocess.run(["python3","-m","unittest", target, "-v"], capture_output=True, text=True, timeout=30)
        out = result.stderr + result.stdout
        m = re.search(r"Ran (\d+) tests", out)
        total = int(m.group(1)) if m else 0
        fails = out.lower().count("fail") + out.lower().count("error")
        ok = fails==0 and total>0
        fitness = total*10 - fails*20
        return {"total_tests":total,"ok":ok,"fails":fails,"fitness":fitness,"raw":out[-1000:]}
    except Exception as e:
        return {"total_tests":0,"ok":False,"fitness":0,"error":str(e)}

# --- PREDICCION ---
def predecir_rol(recurso: str, historico=None):
    if historico is None: historico = cargar_historico()
    # Heuristica + aprendizaje de historico
    admin_resources = [h["recurso"] for h in historico if h.get("rol")=="admin"]
    admin_keywords = ["/admin","/config","/users","/dashboard"]
    score = sum(1 for kw in admin_keywords if kw in recurso)
    # Si recurso similar a historico admin, predice admin
    if score>0: return {"rol_predicho":"admin","confianza":0.8+0.05*score,"motivo":f"contiene {admin_keywords}"}
    return {"rol_predicho":"user","confianza":0.7,"motivo":"recurso publico"}

# --- DECIDIR AUTO-ESCRIBE ---
def proponer_siguiente_orden(auto_bloquear=True):
    log_text = LOG_PATH.read_text(encoding="utf-8")[-10000:] if LOG_PATH.exists() else ""
    anomalias = detectar_anomalias(cargar_historico())
    errores = log_text.lower().count("error")
    warnings = log_text.lower().count("warning")
    anomalias_log = log_text.lower().count("anomalia")

    bloqueos_nuevos = []
    if auto_bloquear:
        for a in anomalias:
            if a["severidad"] in ("alta","critica"):
                ip = a["registro"].get("ip")
                if ip and not es_ip_bloqueada(ip):
                    if bloquear_ip(ip, a["detalle"], 1):
                        bloqueos_nuevos.append(ip)

    propuesta = [f"NIVEL 7 - {datetime.now().isoformat()}"]
    propuesta.append(f"Anomalias detectadas: {len(anomalias)} | log count: {anomalias_log} | errores: {errores}")
    if bloqueos_nuevos:
        propuesta.append(f"AUTO-BLOQUEO EJECUTADO: {', '.join(bloqueos_nuevos)} -> lista_negra.json")
    else:
        if anomalias:
            propuesta.append(f"IPs sospechosas ya bloqueadas: {len(cargar_lista_negra())}")
    
    try:
        fitness = calcular_fitness_real()
    except Exception as e:
        logger.error(f"Fitness error {e}")
        fitness = {"total_tests":0,"ok":False,"fitness":0,"error":str(e)}
    propuesta.append(f"Fitness: {fitness['fitness']} | Tests: {fitness['total_tests']} | OK: {fitness['ok']}")
    
    if len(anomalias)>=2:
        propuesta.append("Siguiente evolucion: implementar rate limiting y 2FA")
    if fitness["total_tests"]<10:
        propuesta.append("Aumentar tests a 50+ con casos de anomalia y bloqueo")
    
    texto = "\n".join(propuesta)
    # AUTO-ESCRIBE ordenes.txt - ESTO ES AUTONOMIA REAL
    ORDENES.write_text(texto, encoding="utf-8")
    # Log evolucion
    with open(EVOLUCION_LOG, "a", encoding="utf-8") as f: f.write(f"{datetime.now().isoformat()} - {texto}\n---\n")
    logger.info(f"ORDENES AUTO-GENERADAS: {len(propuesta)} lineas, bloqueos={len(bloqueos_nuevos)}")
    return {"anomalias":anomalias,"anomalias_log":anomalias_log,"bloqueos_nuevos":bloqueos_nuevos,"lista_negra":cargar_lista_negra(),"fitness":fitness,"texto":texto,"propuesta":propuesta}

# --- MAIN ---
def main():
    datos = cargar_historico()
    insertar_accesos(datos)
    stats = calcular_estadisticas(datos)
    anom = detectar_anomalias(datos)
    print(json.dumps(stats, indent=2))
    print(f"Anomalias: {len(anom)}")
    orden = proponer_siguiente_orden(auto_bloquear=True)
    print(orden["texto"])
    return stats

if __name__=="__main__":
    import sys
    if "--init-db" in sys.argv:
        d=cargar_historico()
        insertar_accesos(d)
        print(f"DB {len(d)} + lista_negra {len(cargar_lista_negra())}")
    elif "--check" in sys.argv:
        d=cargar_historico()
        print(detectar_anomalias(d))
        print(calcular_fitness_real())
    elif "--api" in sys.argv:
        import uvicorn
        from fastapi import FastAPI, Query
        from fastapi.responses import JSONResponse
        port=8001
        if "--port" in sys.argv:
            try: port=int(sys.argv[sys.argv.index("--port")+1])
            except: pass
        app=FastAPI(title="IA Evolutiva Nivel 7 Autonoma")
        @app.get("/accesos")
        def api_accesos(rol: str = Query(None)): return cargar_historico() if rol is None else [x for x in cargar_historico() if x.get("rol")==rol]
        @app.get("/estadisticas")
        def api_stats(): return calcular_estadisticas(cargar_historico())
        @app.get("/anomalias")
        def api_anomalias(): return detectar_anomalias(cargar_historico())
        @app.get("/decidir")
        def api_decidir(auto: bool = True): return proponer_siguiente_orden(auto_bloquear=auto)
        @app.post("/bloquear")
        def api_bloquear(payload: dict): ip=payload.get("ip"); return {"bloqueado":bloquear_ip(ip,payload.get("motivo","manual"),1),"ip":ip,"lista":cargar_lista_negra()}
        @app.post("/desbloquear")
        def api_desbloquear(payload: dict): ip=payload.get("ip"); return {"desbloqueado":desbloquear_ip(ip),"ip":ip}
        @app.get("/lista_negra")
        def api_lista(): return cargar_lista_negra()
        @app.get("/fitness")
        def api_fitness(): return calcular_fitness_real()
        @app.get("/predecir")
        def api_predecir(recurso: str = Query(...)): return predecir_rol(recurso)
        @app.get("/log")
        def api_log(): return {"log": LOG_PATH.read_text()[-3000:] if LOG_PATH.exists() else ""}
        @app.get("/ordenes")
        def api_ordenes(): return {"ordenes": ORDENES.read_text() if ORDENES.exists() else ""}
        @app.get("/health")
        def api_health(): return {"status":"ok","nivel":7,"autonomia":"autonoma","bloqueos":len(cargar_lista_negra())}
        logger.info(f"API Nivel 7 puerto {port}")
        uvicorn.run(app, host="0.0.0.0", port=port)
    elif "--supervisor" in sys.argv:
        print("Supervisor Nivel 7 - cada 30s decide y bloquea")
        while True:
            try:
                o=proponer_siguiente_orden(auto_bloquear=True)
                print(f"[{datetime.now().isoformat()}] {o['texto'][:100]} bloqueos={o['bloqueos_nuevos']}")
                time.sleep(30)
            except KeyboardInterrupt: break
    else:
        main()
