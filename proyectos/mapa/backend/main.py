import ast, json, pathlib, importlib.util
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

def health():
    genoma=genoma_actual()
    mem=cargar_memoria_inmunologica()
    try:
        codigo=EVOLUTIVO_PATH.read_text()
        ast.parse(codigo)
        detectores=len([l for l in codigo.splitlines() if "def detectar_" in l])
    except:
        detectores=0
    if detectores>=35:
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
    print(json.dumps(health(), indent=2, ensure_ascii=False))
