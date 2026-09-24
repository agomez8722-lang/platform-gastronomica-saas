import ast, json, os, sys, time, sqlite3, threading, importlib.util, pathlib
from typing import Dict, List
from http.server import HTTPServer, BaseHTTPRequestHandler

BASE_DIR = pathlib.Path(__file__).parent
GENOMA_PATH = BASE_DIR / "genoma_evolutivo.json"
DB_PATH = BASE_DIR / "accesos.db"
BLACKLIST_PATH = BASE_DIR / "lista_negra.json"
EVOLUTIVO_PATH = BASE_DIR / "evolutivo_real.py"

_GENOMA_ACTUAL = {"umbral_bloqueo": 5, "rate_limit_umbral": 6, "rate_limit_ventana": 32}

def genoma_actual() -> Dict:
    global _GENOMA_ACTUAL
    if GENOMA_PATH.exists():
        try:
            data = json.loads(GENOMA_PATH.read_text(encoding="utf-8"))
            _GENOMA_ACTUAL = data.get("genoma", _GENOMA_ACTUAL)
        except:
            pass
    return dict(_GENOMA_ACTUAL)

def aplicar_genoma(genoma: Dict):
    global _GENOMA_ACTUAL
    _GENOMA_ACTUAL = dict(genoma)

def cargar_memoria_inmunologica() -> Dict:
    if BLACKLIST_PATH.exists():
        try:
            return json.loads(BLACKLIST_PATH.read_text(encoding="utf-8"))
        except:
            return {}
    return {}

def guardar_memoria_inmunologica(mem: Dict):
    BLACKLIST_PATH.write_text(json.dumps(mem, indent=2, ensure_ascii=False), encoding="utf-8")

def registrar_memoria_inmunologica(ip: str, anomalo: bool):
    mem = cargar_memoria_inmunologica()
    if anomalo and ip:
        mem[ip] = mem.get(ip, 0) + 1
        guardar_memoria_inmunologica(mem)

def _evaluar_reglas(registro: Dict, store: Dict) -> Dict:
    genoma = genoma_actual()
    detectores = []
    try:
        codigo = EVOLUTIVO_PATH.read_text(encoding="utf-8")
        ast.parse(codigo)
        spec = importlib.util.spec_from_file_location("evolutivo_real", str(EVOLUTIVO_PATH))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in dir(mod):
            if name.startswith("detectar_"):
                detectores.append(getattr(mod, name))
    except Exception as e:
        detectores = []

    anomalo = False
    motivos = []
    ip = registro.get("ip","")
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

    return {"anomalo": anomalo, "motivos": motivos, "genoma": genoma, "detectores": len(detectores)}

class MotorEvolutivoNivel10:
    def __init__(self):
        self.ciclos = 0
    def ciclo(self, auto=False):
        self.ciclos += 1
        store = {}
        registro = {"rol": "user", "recurso": "/admin/panel", "ip": "10.10.10.1", "hora": "02:00:00"}
        resultado = _evaluar_reglas(registro, store)
        registrar_memoria_inmunologica(registro.get("ip"), resultado["anomalo"])
        return {
            "nivel": 21,
            "fitness": 350 if resultado["detectores"] >= 35 else 300 if resultado["detectores"] >= 30 else 250 if resultado["detectores"] >=25 else 200 if resultado["detectores"] >=8 else 150,
            "detectores_dinamicos": resultado["detectores"],
            "genoma": genoma_actual(),
            "recarga_aplicada": False,
            "motivos": resultado["motivos"]
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
        codigo = EVOLUTIVO_PATH.read_text(encoding="utf-8")
        ast.parse(codigo)
        detectores = len([l for l in codigo.splitlines() if "def detectar_" in l])
    except:
        detectores = 0
    fitness = 300 if detectores>=30 else 250 if detectores>=25 else 200 if detectores>=8 else 150
    return {"nivel": 21, "fitness": fitness, "detectores_dinamicos": detectores, "genoma": genoma, "ips_bloqueadas": len(mem)}

if __name__ == "__main__":
    if "--init-db" in sys.argv:
        init_db()
    elif "--check" in sys.argv:
        print(json.dumps(health(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(health(), indent=2, ensure_ascii=False))
