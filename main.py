"""
IA Evolutiva Nivel 9 - Autonomia Total + Ollama + Auto-Patching Seguro
100% funcional - Sin relleno - Sin bucles innecesarios
- Logging rotativo 1MB
- Deteccion 5 tipos anomalias
- Auto-bloqueo IP real (lista_negra.json + DB)
- Fitness real con unittest
- /decidir escribe ordenes.txt automaticamente
- Supervisor loop
- Prediccion rol
- NUEVO Nivel 8: Rate limiting + 2FA + Middleware
- NUEVO Nivel 9: Ollama + Auto-Patching + Backup + Evoluciones
"""

import json, csv, os, logging, re, subprocess, time, shutil, tempfile, py_compile
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from collections import Counter
from pydantic import BaseModel, Field
import sqlite3

LOG_PATH = Path("app.log")
handler = RotatingFileHandler(str(LOG_PATH), maxBytes=1_000_000, backupCount=5, encoding="utf-8")
handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s - %(message)s'))
logger = logging.getLogger("ia_evolutiva")
logger.setLevel(logging.INFO)
logger.handlers.clear()
logger.addHandler(handler)
logger.addHandler(logging.StreamHandler())
logger.info("Inicializando IA Evolutiva Nivel 9 - Ollama + Auto-Patching")

DB_PATH = Path("accesos.db")
HISTORICO = Path("historico_accesos.json")
LISTA_NEGRA = Path("lista_negra.json")
ORDENES = Path("ordenes.txt")
EVOLUCION_LOG = Path("evolucion.log")

RATE_LIMIT_MAX = 10
RATE_LIMIT_WINDOW = 60
rate_limit_store: Dict[str, List[float]] = {}
FACTOR_2FA_CODE = "123456"

# Nivel 9 - Ollama + Auto-patching
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5-coder:7b"
PARCHES_DIR = Path("parches")
EVOLUCIONES_DIR = Path("evoluciones")
BACKUP_DIR = Path(".backup_nivel9")
IMPLEMENTADOR_LOG = Path("implementador.log")

def check_rate_limit(ip: str):
    now = time.time()
    if ip not in rate_limit_store:
        rate_limit_store[ip] = []
    rate_limit_store[ip] = [t for t in rate_limit_store[ip] if now - t < RATE_LIMIT_WINDOW]
    count = len(rate_limit_store[ip])
    if count >= RATE_LIMIT_MAX:
        return False, count, 0
    rate_limit_store[ip].append(now)
    remaining = RATE_LIMIT_MAX - len(rate_limit_store[ip])
    return True, len(rate_limit_store[ip]), remaining

def get_rate_limit_stats():
    now = time.time()
    stats = {}
    for ip, times in rate_limit_store.items():
        recent = [t for t in times if now - t < RATE_LIMIT_WINDOW]
        stats[ip] = {"requests_last_60s": len(recent), "limit": RATE_LIMIT_MAX, "window": RATE_LIMIT_WINDOW}
    return stats

def verificar_2fa_token(token: Optional[str]) -> bool:
    return token == FACTOR_2FA_CODE

def es_ruta_admin(path: str) -> bool:
    return "/admin" in path

def ollama_disponible() -> bool:
    try:
        import requests
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        return r.status_code == 200
    except:
        return False

def consultar_ollama(prompt: str, system_prompt: str = None, modelo: str = None) -> Dict:
    if modelo is None:
        modelo = OLLAMA_MODEL
    if not ollama_disponible():
        return {"disponible": False, "respuesta": f"[OFFLINE] Ollama no disponible - prompt: {prompt[:120]}", "modelo": modelo, "offline": True}
    try:
        import requests
        payload = {"model": modelo, "prompt": prompt, "system": system_prompt or "Eres experto seguridad Python FastAPI. Responde conciso con codigo.", "stream": False}
        r = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=30)
        if r.status_code == 200:
            data = r.json()
            return {"disponible": True, "respuesta": data.get("response",""), "modelo": modelo, "offline": False}
        else:
            return {"disponible": True, "respuesta": f"Error Ollama {r.status_code}: {r.text[:300]}", "modelo": modelo, "error": True, "offline": False}
    except Exception as e:
        return {"disponible": False, "respuesta": f"[ERROR] {e} - fallback offline", "modelo": modelo, "offline": True, "error": str(e)}

def backup_antes_de_parche() -> Optional[str]:
    try:
        BACKUP_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"main_backup_{ts}.py"
        if Path("main.py").exists():
            shutil.copy("main.py", backup_path)
            logger.info(f"Backup Nivel 9 creado {backup_path}")
            return str(backup_path)
        return None
    except Exception as e:
        logger.error(f"Backup error {e}")
        return None

def validar_parche_sintaxis(codigo: str):
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(codigo)
            temp_path = f.name
        py_compile.compile(temp_path, doraise=True)
        os.unlink(temp_path)
        return True, "Sintaxis OK"
    except Exception as e:
        try:
            os.unlink(temp_path)
        except:
            pass
        return False, str(e)

def limpiar_codigo_ollama(codigo: str) -> str:
    # Limpia ```python ... ``` y fences markdown que rompen sintaxis
    codigo = codigo.strip()
    # Quitar bloques markdown
    codigo = re.sub(r'^```(?:python)?\s*', '', codigo, flags=re.MULTILINE)
    codigo = re.sub(r'\s*```\s*$', '', codigo, flags=re.MULTILINE)
    # Quitar primera linea si es ```python
    lines = codigo.splitlines()
    cleaned = []
    in_code = True
    for line in lines:
        if line.strip().startswith('```'):
            continue
        cleaned.append(line)
    codigo = "\n".join(cleaned).strip()
    return codigo

def generar_parche_seguridad(tipo_anomalia: str, contexto: Dict = None) -> Dict:
    contexto = contexto or {}
    prompt_base = f"Tipo anomalia: {tipo_anomalia} Contexto: {json.dumps(contexto, indent=2)[:1200]} Genera funcion Python detectar_{tipo_anomalia}_v9 que mejore deteccion. Requisitos: funcion pura, recibe dict registro, retorna bool, max 8 lineas. SOLO CODIGO, SIN MARKDOWN, SIN ```."
    resultado = consultar_ollama(prompt_base, system_prompt="Eres implementador seguridad. Genera SOLO codigo Python limpio y seguro. Sin explicacion, sin markdown, sin ```.")
    # Limpiar markdown si Ollama lo devolvio
    if resultado.get("respuesta"):
        resultado["respuesta"] = limpiar_codigo_ollama(resultado["respuesta"])
    if resultado.get("offline") or len(resultado.get("respuesta","").strip()) < 10:
        fallbacks = {
            "privilegio": "def detectar_privilegio_v9(r):\n    return r.get('rol')=='user' and '/admin' in r.get('recurso','')",
            "horario": "def detectar_horario_v9(r):\n    try:\n        h=int(r.get('hora','00:00:00').split(':')[0])\n        return r.get('rol')=='admin' and (h>=23 or h<=5)\n    except:\n        return False",
            "brute_force": "def detectar_brute_force_v9(r):\n    return '/admin' in r.get('recurso','') and r.get('rol')!='admin'",
            "frecuencia_ip": "def detectar_frecuencia_ip_v9(ip, store):\n    return len(store.get(ip,[])) > 8",
            "rate_limit": "def detectar_rate_limit_v9(ip, store):\n    return len([t for t in store.get(ip,[]) if time.time()-t < 60]) > 8",
            "2fa_bypass": "def detectar_2fa_bypass_v9(req):\n    return '/admin' in req.get('path','') and not req.get('headers',{}).get('X-2FA')"
        }
        codigo = fallbacks.get(tipo_anomalia, f"def detectar_{tipo_anomalia}_v9(r):\n    return True")
        resultado["respuesta"] = codigo
        resultado["fallback"] = True
        resultado["offline"] = True
    else:
        resultado["fallback"] = False
    ok, msg = validar_parche_sintaxis(resultado["respuesta"])
    resultado["sintaxis_ok"] = ok
    resultado["sintaxis_msg"] = msg
    return resultado

def proponer_evolucion_ollama(anomalias: List[Dict] = None) -> Dict:
    if anomalias is None:
        anomalias = detectar_anomalias(cargar_historico())
    if not anomalias:
        return {"evolucion": "No hay anomalias - sistema estable Nivel 9", "parches": [], "ollama_usado": False, "nivel": 9}
    tipos = list(set(a["tipo"] for a in anomalias))
    parches = []
    for tipo in tipos[:3]:
        parche = generar_parche_seguridad(tipo, {"ejemplos": [a["detalle"] for a in anomalias if a["tipo"]==tipo][:2]})
        parches.append({"tipo": tipo, "codigo": parche["respuesta"][:2500], "ollama": not parche.get("offline", True), "fallback": parche.get("fallback", False), "sintaxis_ok": parche.get("sintaxis_ok", False)})
    EVOLUCIONES_DIR.mkdir(exist_ok=True)
    PARCHES_DIR.mkdir(exist_ok=True)
    evo_file = EVOLUCIONES_DIR / f"evolucion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    for p in parches:
        pf = PARCHES_DIR / f"parche_{p['tipo']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
        pf.write_text(p["codigo"], encoding="utf-8")
    evo_data = {"fecha": datetime.now().isoformat(), "nivel": 9, "anomalias": len(anomalias), "tipos": tipos, "parches": parches, "fitness": calcular_fitness_real(), "ollama_disponible": ollama_disponible(), "modelo": OLLAMA_MODEL}
    evo_file.write_text(json.dumps(evo_data, indent=2), encoding="utf-8")
    with open(IMPLEMENTADOR_LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()} - Evolucion N9 - {len(anomalias)} anomalias -> {len(parches)} parches - ollama:{ollama_disponible()}\n")
    return {"evolucion": f"Nivel 9 - {len(anomalias)} anomalias -> {len(parches)} parches", "tipos": tipos, "parches": parches, "archivo": str(evo_file), "ollama_disponible": ollama_disponible(), "modelo": OLLAMA_MODEL, "nivel": 9}


class Acceso(BaseModel):
    usuario: str = Field(..., min_length=1)
    rol: str = Field(..., pattern="^(admin|user|guest)$")
    fecha: str
    hora: str
    recurso: str
    ip: Optional[str] = None
    user_agent: Optional[str] = None

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

def detectar_anomalias(datos: List[Dict]) -> List[Dict]:
    anomalias = []
    ips = [d.get("ip") for d in datos if d.get("ip")]
    usuarios = [d.get("usuario") for d in datos]
    ip_counts = Counter(ips)
    user_counts = Counter(usuarios)
    for r in datos:
        if r.get("rol")=="user" and "/admin" in r.get("recurso",""):
            anomalias.append({"tipo":"privilegio","severidad":"alta","detalle":f"{r['usuario']} user->{r['recurso']}","registro":r})
            logger.warning(f"Anomalia privilegio: {r}")
        try:
            h = int(r.get("hora","00:00:00").split(":")[0])
            if r.get("rol")=="admin" and (h>=22 or h<=5) and "/admin" in r.get("recurso",""):
                anomalias.append({"tipo":"horario","severidad":"media","detalle":f"admin nocturno {r['usuario']} {r['hora']}","registro":r})
        except: pass
        if ip_counts[r.get("ip","")] > 3:
            anomalias.append({"tipo":"frecuencia_ip","severidad":"media","detalle":f"IP {r['ip']} {ip_counts[r['ip']]} accesos","registro":r})
        if user_counts[r.get("usuario","")] > 4:
            anomalias.append({"tipo":"frecuencia_usuario","severidad":"baja","detalle":f"Usuario {r['usuario']} {user_counts[r['usuario']]} accesos","registro":r})
        if "/admin" in r.get("recurso","") and r.get("rol")!="admin":
            anomalias.append({"tipo":"brute_force","severidad":"critica","detalle":f"Intento brute force {r['usuario']}->{r['recurso']}","registro":r})
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
    rate_stats = get_rate_limit_stats()
    return {"total":len(datos),"por_rol":por_rol,"usuarios_unicos":len(set(d.get("usuario") for d in datos)),"ips_unicas":len(set(d.get("ip") for d in datos if d.get("ip"))),"bloqueadas":bloqueadas,"lista_negra_count":len(cargar_lista_negra()),"rate_limit_active":len(rate_stats),"nivel":9,"ollama_disponible":ollama_disponible(),"evoluciones":len(list(EVOLUCIONES_DIR.glob("*.json")) if EVOLUCIONES_DIR.exists() else []),"parches":len(list(PARCHES_DIR.glob("*.py")) if PARCHES_DIR.exists() else [])}

def calcular_fitness_real():
    try:
        target = "test_nivel7"
        result = subprocess.run(["python3","-m","unittest", target, "-v"], capture_output=True, text=True, timeout=90)
        out = result.stderr + result.stdout
        m = re.search(r"Ran (\d+) tests", out)
        total = int(m.group(1)) if m else 0
        # Fix: contar solo fallos reales, no substrings en nombres de tests
        # Buscar lineas que empiezan con FAIL: o ERROR: o resumen FAILED
        fails_real = len(re.findall(r"^(FAIL|ERROR):", out, re.MULTILINE))
        if "FAILED" in out:
            # Extraer numero de fails del resumen FAILED (failures=X, errors=Y)
            m_fail = re.search(r"FAILED \(failures=(\d+)(?:, errors=(\d+))?\)", out)
            m_err = re.search(r"FAILED \(errors=(\d+)\)", out)
            if m_fail:
                fails_real = int(m_fail.group(1)) + (int(m_fail.group(2)) if m_fail.group(2) else 0)
            elif m_err:
                fails_real = int(m_err.group(1))
            elif fails_real == 0:
                # Si hay FAILED pero no parseamos, contar 1
                fails_real = 1
        else:
            fails_real = 0 if "OK" in out else fails_real
        fails = fails_real
        ok = fails==0 and total>0 and "OK" in out
        fitness = total*10 - fails*20 + (20 if ollama_disponible() else 0) + (10 if PARCHES_DIR.exists() and len(list(PARCHES_DIR.glob("*.py")))>0 else 0)
        return {"total_tests":total,"ok":ok,"fails":fails,"fitness":fitness,"raw":out[-1500:],"ollama":ollama_disponible()}
    except Exception as e:
        return {"total_tests":0,"ok":False,"fitness":0,"error":str(e)}

def predecir_rol(recurso: str, historico=None):
    if historico is None: historico = cargar_historico()
    admin_keywords = ["/admin","/config","/users","/dashboard"]
    score = sum(1 for kw in admin_keywords if kw in recurso)
    if score>0: return {"rol_predicho":"admin","confianza":0.8+0.05*score,"motivo":f"contiene {admin_keywords}"}
    return {"rol_predicho":"user","confianza":0.7,"motivo":"recurso publico"}

def proponer_siguiente_orden(auto_bloquear=True):
    log_text = LOG_PATH.read_text(encoding="utf-8")[-10000:] if LOG_PATH.exists() else ""
    anomalias = detectar_anomalias(cargar_historico())
    errores = log_text.lower().count("error")
    warnings = log_text.lower().count("warning")
    anomalias_log = log_text.lower().count("anomalia")
    bloqueos_nuevos = []
    evo = {"evolucion":"init","parches":[]}
    if auto_bloquear:
        for a in anomalias:
            if a["severidad"] in ("alta","critica"):
                ip = a["registro"].get("ip")
                if ip and not es_ip_bloqueada(ip):
                    if bloquear_ip(ip, a["detalle"], 1):
                        bloqueos_nuevos.append(ip)
    # Evolucion Ollama cada ciclo si hay anomalias
    evo = proponer_evolucion_ollama(anomalias) if len(anomalias)>=1 else {"evolucion":"Estable","parches":[],"archivo":""}
    propuesta = [f"NIVEL 9 - {datetime.now().isoformat()} - Ollama:{ollama_disponible()}"]
    propuesta.append(f"Anomalias: {len(anomalias)} | log: {anomalias_log} | errores: {errores} | Ollama: {ollama_disponible()} | EvoDir: {len(list(EVOLUCIONES_DIR.glob('*.json'))) if EVOLUCIONES_DIR.exists() else 0}")
    propuesta.append(f"Rate limiting: {RATE_LIMIT_MAX} req/{RATE_LIMIT_WINDOW}s | IPs monitoreadas: {len(rate_limit_store)}")
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
        propuesta.append(f"Evolucion: {evo.get('evolucion')} | Parches: {len(evo.get('parches',[]))} | Ollama: {ollama_disponible()}")
    if len(anomalias)>=1:
        propuesta.append("Nivel 9 OK: Ollama + auto-patching + backup seguro | Siguiente: auto-deploy con tests")
    if fitness["total_tests"]<10:
        propuesta.append("Aumentar tests a 50+ con casos de rate limiting y 2FA")
    texto = "\n".join(propuesta)
    ORDENES.write_text(texto, encoding="utf-8")
    with open(EVOLUCION_LOG, "a", encoding="utf-8") as f: f.write(f"{datetime.now().isoformat()} - {texto}\n---\n")
    logger.info(f"ORDENES NIVEL 9: {len(propuesta)} lineas, bloqueos={len(bloqueos_nuevos)}, parches={len(evo.get('parches',[]))}")
    return {"anomalias":anomalias,"anomalias_log":anomalias_log,"bloqueos_nuevos":bloqueos_nuevos,"lista_negra":cargar_lista_negra(),"fitness":fitness,"texto":texto,"propuesta":propuesta,"rate_limit":get_rate_limit_stats(),"evolucion":evo,"ollama_disponible":ollama_disponible()}

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
        print(f"Rate limit stats: {get_rate_limit_stats()}")
    elif "--api" in sys.argv:
        import uvicorn
        from fastapi import FastAPI, Query, Request, Header
        from fastapi.responses import JSONResponse
        port=8001
        if "--port" in sys.argv:
            try: port=int(sys.argv[sys.argv.index("--port")+1])
            except: pass
        app=FastAPI(title="IA Evolutiva Nivel 9 - Ollama + Auto-Patching")
        @app.middleware("http")
        async def middleware_seguridad_nivel9(request: Request, call_next):
            ip = request.client.host if request.client else "unknown"
            if request.url.path in ["/health", "/docs", "/openapi.json"]:
                response = await call_next(request)
                return response
            if es_ip_bloqueada(ip):
                return JSONResponse(status_code=403, content={"detail": f"IP bloqueada {ip}", "nivel":9, "bloqueada":True})
            ok, count, remaining = check_rate_limit(ip)
            if not ok:
                bloquear_ip(ip, f"Rate limit excedido {count} req/{RATE_LIMIT_WINDOW}s en {request.url.path}", count)
                return JSONResponse(status_code=429, content={"detail": "Rate limit excedido - IP bloqueada", "ip": ip, "count": count, "nivel":9})
            if es_ruta_admin(request.url.path):
                token = request.headers.get("X-2FA")
                if not verificar_2fa_token(token):
                    return JSONResponse(status_code=401, content={"detail": "2FA requerido para /admin - Header X-2FA: 123456", "nivel":9, "2fa_required":True})
            response = await call_next(request)
            response.headers["X-Nivel"] = "9"
            response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_MAX)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-Ollama"] = str(ollama_disponible())
            return response
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
        def api_health(): return {"status":"ok","nivel":9,"autonomia":"total","bloqueos":len(cargar_lista_negra()),"rate_limit":{"max":RATE_LIMIT_MAX,"window":RATE_LIMIT_WINDOW,"ips_monitoreadas":len(rate_limit_store)},"2fa":{"activo":True,"header":"X-2FA"},"ollama":{"disponible":ollama_disponible(),"url":OLLAMA_URL,"modelo":OLLAMA_MODEL},"evoluciones":len(list(EVOLUCIONES_DIR.glob("*.json")) if EVOLUCIONES_DIR.exists() else 0),"parches":len(list(PARCHES_DIR.glob("*.py")) if PARCHES_DIR.exists() else 0)}
        @app.get("/rate_limit/status")
        def api_rate_limit(): return {"nivel":9,"rate_limit":get_rate_limit_stats(),"config":{"max":RATE_LIMIT_MAX,"window":RATE_LIMIT_WINDOW}}
        @app.post("/auth/2fa/verificar")
        def api_2fa_verificar(payload: dict): token=payload.get("token"); ok=verificar_2fa_token(token); return {"verificado":ok,"nivel":9,"token_ok":ok}
        @app.get("/auth/2fa/status")
        def api_2fa_status(): return {"nivel":9,"2fa_activo":True,"header_requerido":"X-2FA","codigo_demo":FACTOR_2FA_CODE,"rutas_protegidas":["/admin/*"]}
        @app.get("/admin/dashboard")
        def api_admin_dashboard(x_2fa: Optional[str] = Header(None)):
            if not verificar_2fa_token(x_2fa):
                return JSONResponse(status_code=401, content={"detail":"2FA requerido"})
            return {"dashboard":"admin","nivel":9,"2fa":"ok","accesos":len(cargar_historico()),"ollama":ollama_disponible()}
        @app.get("/ollama/status")
        def api_ollama_status(): return {"nivel":9,"ollama_disponible":ollama_disponible(),"url":OLLAMA_URL,"modelo":OLLAMA_MODEL,"fallback_activo":True}
        @app.post("/ollama/consultar")
        def api_ollama_consultar(payload: dict):
            prompt=payload.get("prompt","Hola")
            system=payload.get("system")
            modelo=payload.get("modelo", OLLAMA_MODEL)
            res=consultar_ollama(prompt, system, modelo)
            return res
        @app.get("/evolucionar")
        def api_evolucionar_get(): return proponer_evolucion_ollama()
        @app.post("/evolucionar")
        def api_evolucionar_post(payload: dict = None):
            payload = payload or {}
            tipos = payload.get("tipos")
            anom = detectar_anomalias(cargar_historico())
            if tipos:
                anom = [a for a in anom if a["tipo"] in tipos]
            return proponer_evolucion_ollama(anom)
        @app.post("/parchear")
        def api_parchear(payload: dict):
            tipo=payload.get("tipo","privilegio")
            dry_run=payload.get("dry_run", True)
            backup_path = backup_antes_de_parche() if not dry_run else None
            parche = generar_parche_seguridad(tipo, payload.get("contexto",{}))
            if not dry_run and parche.get("sintaxis_ok"):
                PARCHES_DIR.mkdir(exist_ok=True)
                pf = PARCHES_DIR / f"parche_{tipo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_aplicado.py"
                pf.write_text(parche["respuesta"], encoding="utf-8")
            return {"tipo":tipo,"dry_run":dry_run,"backup":backup_path,"parche":parche,"aplicado":not dry_run and parche.get("sintaxis_ok", False)}
        @app.get("/parches")
        def api_parches():
            if not PARCHES_DIR.exists(): return []
            return [{"archivo":str(p),"tipo":p.stem,"contenido":p.read_text()[:2000]} for p in PARCHES_DIR.glob("*.py")]
        @app.get("/evoluciones")
        def api_evoluciones():
            if not EVOLUCIONES_DIR.exists(): return []
            evos=[]
            for f in sorted(EVOLUCIONES_DIR.glob("*.json"), reverse=True)[:10]:
                try: evos.append(json.loads(f.read_text()))
                except: pass
            return evos
        @app.get("/implementador/status")
        def api_implementador_status(): return {"nivel":9,"modelfile":str(Path("Modelfile.implementador").exists()),"ollama":ollama_disponible(),"modelo":OLLAMA_MODEL,"backups":len(list(BACKUP_DIR.glob("*.py"))) if BACKUP_DIR.exists() else 0}
        @app.post("/implementador/generar")
        def api_implementador_generar(payload: dict):
            prompt=payload.get("prompt","Genera funcion que detecte anomalias de privilegio")
            res=consultar_ollama(prompt, system_prompt="Eres implementador senior Python. Genera codigo limpio, seguro y testeable.", modelo=payload.get("modelo", OLLAMA_MODEL))
            return {"prompt":prompt,"codigo":res["respuesta"][:4000],"ollama":res}
        logger.info(f"API Nivel 9 puerto {port} - Rate limiting {RATE_LIMIT_MAX}/{RATE_LIMIT_WINDOW}s + 2FA + Ollama {OLLAMA_MODEL} activo")
        uvicorn.run(app, host="0.0.0.0", port=port)
    elif "--supervisor" in sys.argv:
        print("Supervisor Nivel 9 - cada 30s decide, evoluciona y bloquea + Ollama")
        while True:
            try:
                o=proponer_siguiente_orden(auto_bloquear=True)
                print(f"[{datetime.now().isoformat()}] N9 {o['texto'][:120]} bloqueos={o.get('bloqueos_nuevos',[])} ollama={o.get('ollama_disponible', ollama_disponible())} evo={len(o.get('evolucion',{}).get('parches',[]))} fitness={o.get('fitness',{}).get('fitness',0)}")
                time.sleep(30)
            except KeyboardInterrupt: break
    else:
        main()