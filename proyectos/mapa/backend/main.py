import ast, json, pathlib, importlib.util, sys
from typing import Dict
BASE_DIR = pathlib.Path(__file__).parent
GENOMA_PATH = BASE_DIR / "genoma_evolutivo.json"
BLACKLIST_PATH = BASE_DIR / "lista_negra.json"
EVOLUTIVO_PATH = BASE_DIR / "evolutivo_real.py"
_GENOMA_ACTUAL = {"umbral_bloqueo": 5, "rate_limit_umbral": 6, "rate_limit_ventana": 32}

def genoma_actual():
    global _GENOMA_ACTUAL
    if GENOMA_PATH.exists():
        try:
            data = json.loads(GENOMA_PATH.read_text())
            _GENOMA_ACTUAL = data.get("genoma", _GENOMA_ACTUAL)
        except: pass
    return dict(_GENOMA_ACTUAL)

def cargar_memoria_inmunologica():
    if BLACKLIST_PATH.exists():
        try: return json.loads(BLACKLIST_PATH.read_text())
        except: return {}
    return {}

def guardar_memoria_inmunologica(mem):
    BLACKLIST_PATH.write_text(json.dumps(mem, indent=2, ensure_ascii=False))

def registrar_memoria_inmunologica(ip, anomalo):
    mem = cargar_memoria_inmunologica()
    if anomalo and ip:
        mem[ip] = mem.get(ip, 0) + 1
        guardar_memoria_inmunologica(mem)

def normalizar_recurso(recurso: str) -> str:
    try:
        return urllib.parse.unquote_plus(urllib.parse.unquote_plus(recurso)).lower()
    except:
        return recurso.lower()

def _evaluar_reglas(registro: Dict, store: Dict):
    genoma = genoma_actual()
    detectores = []
    try:
        codigo = EVOLUTIVO_PATH.read_text()
        ast.parse(codigo)
        spec = importlib.util.spec_from_file_location("evolutivo_real", str(EVOLUTIVO_PATH))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for name in dir(mod):
            if name.startswith("detectar_"):
                detectores.append(getattr(mod, name))
    except: detectores = []
    anomalo=False
    motivos=[]
    ip=registro.get("ip","")
    for det in detectores:
        try:
            if "rate_limit" in det.__name__:
                if det(ip, store):
                    anomalo=True
                    motivos.append(det.__name__)
            else:
                if det(registro):
                    anomalo=True
                    motivos.append(det.__name__)
        except: continue
    return {"anomalo": anomalo, "motivos": motivos, "genoma": genoma, "detectores": len(detectores)}

def health():
    genoma=genoma_actual()
    mem=cargar_memoria_inmunologica()
    try:
        codigo=EVOLUTIVO_PATH.read_text()
        ast.parse(codigo)
        detectores=len([l for l in codigo.splitlines() if "def detectar_" in l])
    except: detectores=0
    if detectores>=50:
        nivel=24
        fitness=500
    elif detectores>=45:
        nivel=23
        fitness=450
    elif detectores>=40:
        nivel=22
        fitness=400
    elif detectores>=35:
        nivel=21
        fitness=350
    elif detectores>=30:
        nivel=20
        fitness=300
    elif detectores>=25:
        nivel=19
        fitness=250
    else:
        nivel=12
        fitness=200 if detectores>=8 else 150
    return {"nivel": nivel, "fitness": fitness, "detectores_dinamicos": detectores, "genoma": genoma, "ips_bloqueadas": len(mem)}

if __name__ == "__main__":
    if "--check" in sys.argv or len(sys.argv)==1:
        print(json.dumps(health(), indent=2, ensure_ascii=False))
