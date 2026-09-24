import ast, json, os, time, pathlib, fcntl, re, urllib.parse
from typing import Dict, List
import importlib.util

# ENV + Genoma - lee de.env
from dotenv import load_dotenv
load_dotenv()
GENOMA_PATH = os.getenv("GENOMA_PATH", "genoma_evolutivo.json")
BLACKLIST_PATH = os.getenv("BLACKLIST_PATH", "lista_negra.json")
EVOLUTIVO_PATH = os.getenv("EVOLUTIVO_PATH", "evolutivo_real.py")
BLACKLIST_TTL = int(os.getenv("BLACKLIST_TTL", "3600"))

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

def cargar_memoria_inmunologica() -> Dict:
    if not os.path.exists(BLACKLIST_PATH):
        return {}
    try:
        # Lock para evitar race condition
        with open(BLACKLIST_PATH, "r") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            data = json.load(f)
            fcntl.flock(f, fcntl.LOCK_UN)
            # TTL - limpia viejas
            now = time.time()
            cleaned = {ip: v for ip, v in data.items() if isinstance(v, dict) and now - v.get("ts", 0) < BLACKLIST_TTL or isinstance(v, int)}
            return cleaned
    except:
        return {}

def guardar_memoria_inmunologica(mem: Dict):
    with open(BLACKLIST_PATH, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(mem, indent=2, ensure_ascii=False))
        fcntl.flock(f, fcntl.LOCK_UN)

def registrar_memoria_inmunologica(ip: str, anomalo: bool):
    if not anomalo or not ip:
        return
    mem = cargar_memoria_inmunologica()
    entry = mem.get(ip, {"count":0,"ts":time.time()})
    if isinstance(entry, int):
        entry = {"count": entry, "ts": time.time()}
    entry["count"] = entry.get("count",0) + 1
    entry["ts"] = time.time()
    mem[ip] = entry
    if entry["count"] >= genoma_actual().get("umbral_bloqueo", 5):
        guardar_memoria_inmunologica(mem)
    else:
        guardar_memoria_inmunologica(mem)

def normalizar_recurso(recurso: str) -> str:
    # Decodifica %20, doble encode, lower
    try:
        r = urllib.parse.unquote_plus(urllib.parse.unquote_plus(recurso)).lower()
        return r
    except:
        return recurso.lower()

def _evaluar_reglas(registro: Dict, store: Dict) -> Dict:
    genoma = genoma_actual()
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
    ip = registro.get("ip","")
    # Normaliza recurso una vez
    if "recurso" in registro:
        registro["recurso_norm"] = normalizar_recurso(registro.get("recurso",""))

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

def health():
    genoma = genoma_actual()
    mem = cargar_memoria_inmunologica()
    try:
        codigo = pathlib.Path(EVOLUTIVO_PATH).read_text(encoding="utf-8")
        ast.parse(codigo)
        detectores = len([l for l in codigo.splitlines() if "def detectar_" in l])
    except:
        detectores = 0
    # Nivel 24 -> 50 detectores = 500
    if detectores >= 50:
        nivel, fitness = 24, 500
    elif detectores >= 45:
        nivel, fitness = 23, 450
    elif detectores >= 40:
        nivel, fitness = 22, 400
    else:
        nivel, fitness = 12, 200
    return {"nivel": nivel, "fitness": fitness, "detectores_dinamicos": detectores, "genoma": genoma, "ips_bloqueadas": len(mem)}

if __name__ == "__main__":
    import sys
    if "--check" in sys.argv:
        print(json.dumps(health(), indent=2, ensure_ascii=False))
