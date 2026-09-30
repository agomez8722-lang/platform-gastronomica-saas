import ast, json, os, sys, time, sqlite3, threading, importlib.util, pathlib
from typing import Dict, List
from http.server import HTTPServer, BaseHTTPRequestHandler

GENOMA_PATH = "genoma_evolutivo.json"
DB_PATH = "accesos.db"
BLACKLIST_PATH = "lista_negra.json"
EVOLUTIVO_PATH = "evolutivo_real.py"

_GENOMA_ACTUAL = {"umbral_bloqueo": 5, "rate_limit_umbral": 6, "rate_limit_ventana": 32}

def genoma_actual() -> Dict:
    global _GENOMA_ACTUAL
    if os.path.exists(GENOMA_PATH):
        try:
            data = json.loads(pathlib.Path(GENOMA_PATH).read_text(encoding="utf-8"))
            _GENOMA_ACTUAL = data.get("genoma", _GENOMA_ACTUAL)
        except:
            pass
    return dict(_GENOMA_ACTUAL)

def aplicar_genoma(genoma: Dict):
    global _GENOMA_ACTUAL
    _GENOMA_ACTUAL = dict(genoma)

def cargar_memoria_inmunologica() -> Dict:
    if os.path.exists(BLACKLIST_PATH):
        try:
            return json.loads(pathlib.Path(BLACKLIST_PATH).read_text(encoding="utf-8"))
        except:
            return {}
    return {}

def guardar_memoria_inmunologica(mem: Dict):
    pathlib.Path(BLACKLIST_PATH).write_text(json.dumps(mem, indent=2, ensure_ascii=False), encoding="utf-8")

def esta_bloqueada(ip: str) -> bool:
    mem = cargar_memoria_inmunologica()
    genoma = genoma_actual()
    return mem.get(ip, 0) >= genoma.get("umbral_bloqueo", 5)

def registrar_memoria_inmunologica(ip: str, anomalo: bool):
    mem = cargar_memoria_inmunologica()
    if anomalo and ip:
        mem[ip] = mem.get(ip, 0) + 1
        if mem[ip] >= genoma_actual().get("umbral_bloqueo", 5):
            print(f"[BLOQUEO REAL 403] IP {ip} bloqueada - {mem[ip]} intentos")
        guardar_memoria_inmunologica(mem)

def _evaluar_reglas(registro: Dict, store: Dict) -> Dict:
    genoma = genoma_actual()
    ip = registro.get("ip","")
    if ip and esta_bloqueada(ip):
        return {"anomalo": True, "bloqueado": True, "status": 403, "motivos": ["ip_bloqueada_403"], "genoma": genoma, "detectores": 0}
    detectores = []
    try:
        codigo = pathlib.Path(EVOLUTIVO_PATH).read_text(encoding="utf-8")
        ast.parse(codigo)
        spec = importlib.util.spec_from_file_location("evolutivo_real", EVOLUTIVO_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in dir(mod):
            if name.startswith("detectar_"):
                detectores.append(getattr(mod, name))
    except Exception as e:
        detectores = []
    anomalo = False
    motivos = []
    for det in detectores:
        try:
            if "rate_limit" in det.__name__:
                if det(ip, store):
                    anomalo = True
                    motivos.append(det.__name__)
            else:
                if det(registro):
                    anomalo = True
                    motivos.append(det.__name__)
        except:
            continue
    if ip and ip in store:
        ventana = genoma.get("rate_limit_ventana", 32)
        umbral = genoma.get("rate_limit_umbral", 6)
        recent = [t for t in store[ip] if time.time() - t < ventana]
        if len(recent) >= umbral and "rate_limit_genetico" not in motivos:
            anomalo = True
            motivos.append("rate_limit_genetico")
    bloqueado = False
    status = 200
    if ip and esta_bloqueada(ip):
        bloqueado = True
        status = 403
        anomalo = True
        if "ip_bloqueada_403" not in motivos:
            motivos.append("ip_bloqueada_403")
    return {"anomalo": anomalo, "bloqueado": bloqueado, "status": status, "motivos": motivos, "genoma": genoma, "detectores": len(detectores)}

class MotorEvolutivoNivel10:
    def __init__(self):
        self.ciclos = 0
    def ciclo(self, auto=False):
        self.ciclos += 1
        store = {}
        registro = {"rol": "user", "recurso": "/admin/panel", "ip": "10.10.10.1", "hora": "02:00:00"}
        resultado = _evaluar_reglas(registro, store)
        registrar_memoria_inmunologica(registro.get("ip"), resultado["anomalo"])
        recarga = False
        try:
            codigo = pathlib.Path(EVOLUTIVO_PATH).read_text(encoding="utf-8")
            ast.parse(codigo)
            recarga = True if self.ciclos % 10 == 0 else False
            recarga = False
        except:
            recarga = False
        return {
            "nivel": 13,
            "fitness": 500 if resultado["detectores"] >= 20 else 200 if resultado["detectores"] >= 8 else 150,
            "detectores_dinamicos": resultado["detectores"],
            "genoma": genoma_actual(),
            "recarga_aplicada": recarga,
            "motivos": resultado["motivos"],
            "bloqueado": resultado.get("bloqueado", False)
        }

def init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TABLE IF NOT EXISTS accesos (id INTEGER PRIMARY KEY, usuario TEXT, rol TEXT, recurso TEXT, ip TEXT, hora TEXT, fecha TEXT)")
    con.commit()
    con.close()
    print(f"DB {DB_PATH} OK")

def health():
    genoma = genoma_actual()
    mem = cargar_memoria_inmunologica()
    try:
        codigo = pathlib.Path(EVOLUTIVO_PATH).read_text(encoding="utf-8")
        ast.parse(codigo)
        detectores = len([l for l in codigo.splitlines() if "def detectar_" in l])
    except:
        detectores = 0
    bloqueadas = sum(1 for v in mem.values() if v >= genoma.get("umbral_bloqueo",5))
    return {"nivel": 13, "fitness": 500 if detectores>=20 else 200 if detectores>=8 else 150, "detectores_dinamicos": detectores, "genoma": genoma, "ips_bloqueadas": bloqueadas, "memoria_total": len(mem)}

if __name__ == "__main__":
    if "--init-db" in sys.argv:
        init_db()
    elif "--check" in sys.argv:
        print(json.dumps(health(), indent=2, ensure_ascii=False))
    elif "--evolucionar" in sys.argv:
        idx = sys.argv.index("--evolucionar")
        gens = int(sys.argv[idx+1]) if len(sys.argv) > idx+1 else 20
        import evolucion_genetica as evo
        res = evo.evolucionar(generaciones=gens)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif "--evolucionar-codigo" in sys.argv:
        idx = sys.argv.index("--evolucionar-codigo")
        gens = int(sys.argv[idx+1]) if len(sys.argv) > idx+1 else 10
        import evolucion_codigo as evo_c
        res = evo_c.evolucionar_codigo(generaciones=gens)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif "--daemon" in sys.argv:
        intervalo = 10
        if "--intervalo" in sys.argv:
            intervalo = int(sys.argv[sys.argv.index("--intervalo")+1])
        motor = MotorEvolutivoNivel10()
        ciclo = 0
        try:
            while True:
                ciclo += 1
                estado = motor.ciclo(auto=True)
                ips = len(cargar_memoria_inmunologica())
                print(f"[ciclo {ciclo}] nivel={estado['nivel']} fitness={estado['fitness']} detectores_dinamicos={estado['detectores_dinamicos']} ips_bloqueadas={ips} recarga_aplicada={estado['recarga_aplicada']} genoma={estado['genoma']}")
                if ciclo % 6 == 0:
                    try:
                        import evolucion_genetica as evo
                        evo.evolucionar(generaciones=5, tam_poblacion=8)
                    except Exception as e:
                        print(f"evolucion error {e}")
                time.sleep(intervalo)
        except KeyboardInterrupt:
            print("daemon detenido")
    elif "--tarea" in sys.argv:
        idx = sys.argv.index("--tarea")
        tarea = sys.argv[idx+1] if len(sys.argv) > idx+1 else "analizar_logs"
        import tareas_complejas as tc
        res = tc.ejecutar(tarea)
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(health(), indent=2, ensure_ascii=False))
