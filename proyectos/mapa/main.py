import ast, json, os, sys, time, sqlite3, importlib.util, pathlib
from typing import Dict, List
GENOMA_PATH="genoma_evolutivo.json"; DB_PATH="accesos.db"; BLACKLIST_PATH="lista_negra.json"; EVOLUTIVO_PATH="evolutivo_real.py"
_GENOMA_ACTUAL={"umbral_bloqueo":5,"rate_limit_umbral":6,"rate_limit_ventana":32}
def genoma_actual():
    global _GENOMA_ACTUAL
    if os.path.exists(GENOMA_PATH):
        try:
            data=json.loads(pathlib.Path(GENOMA_PATH).read_text()); _GENOMA_ACTUAL=data.get("genoma",_GENOMA_ACTUAL)
        except: pass
    return dict(_GENOMA_ACTUAL)
def cargar_memoria_inmunologica():
    if os.path.exists(BLACKLIST_PATH):
        try: return json.loads(pathlib.Path(BLACKLIST_PATH).read_text())
        except: return {}
    return {}
def guardar_memoria_inmunologica(mem): pathlib.Path(BLACKLIST_PATH).write_text(json.dumps(mem, indent=2, ensure_ascii=False), encoding="utf-8")
def esta_bloqueada(ip: str) -> bool:
    mem=cargar_memoria_inmunologica(); return mem.get(ip,0) >= genoma_actual().get("umbral_bloqueo",5)
def registrar_memoria_inmunologica(ip: str, anomalo: bool):
    mem=cargar_memoria_inmunologica()
    if anomalo and ip:
        mem[ip]=mem.get(ip,0)+1
        if mem[ip] >= genoma_actual().get("umbral_bloqueo",5):
            print(f"[BLOQUEO REAL 403] IP {ip} bloqueada - {mem[ip]} intentos")
        guardar_memoria_inmunologica(mem)
def _evaluar_reglas(registro: Dict, store: Dict) -> Dict:
    genoma=genoma_actual(); ip=registro.get("ip","")
    if ip and esta_bloqueada(ip):
        return {"anomalo":True,"bloqueado":True,"status":403,"motivos":["ip_bloqueada_403"],"genoma":genoma,"detectores":0}
    detectores=[]
    try:
        codigo=pathlib.Path(EVOLUTIVO_PATH).read_text(); ast.parse(codigo)
        spec=importlib.util.spec_from_file_location("evolutivo_real",EVOLUTIVO_PATH); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        for name in dir(mod):
            if name.startswith("detectar_"): detectores.append(getattr(mod,name))
    except: detectores=[]
    anomalo=False; motivos=[]
    for det in detectores:
        try:
            if "rate_limit" in det.__name__:
                if det(ip,store): anomalo=True; motivos.append(det.__name__)
            else:
                if det(registro): anomalo=True; motivos.append(det.__name__)
        except: continue
    if ip and ip in store:
        ventana=genoma.get("rate_limit_ventana",32); umbral=genoma.get("rate_limit_umbral",6)
        recent=[t for t in store[ip] if time.time()-t < ventana]
        if len(recent) >= umbral and "rate_limit_genetico" not in motivos:
            anomalo=True; motivos.append("rate_limit_genetico")
    bloqueado=False; status=200
    if ip and esta_bloqueada(ip):
        bloqueado=True; status=403; anomalo=True
        if "ip_bloqueada_403" not in motivos: motivos.append("ip_bloqueada_403")
    return {"anomalo":anomalo,"bloqueado":bloqueado,"status":status,"motivos":motivos,"genoma":genoma,"detectores":len(detectores)}
class MotorEvolutivoNivel10:
    def __init__(self): self.ciclos=0
    def ciclo(self, auto=False):
        self.ciclos+=1; store={}; registro={"rol":"user","recurso":"/admin/panel","ip":"10.10.10.1","hora":"02:00:00"}
        resultado=_evaluar_reglas(registro,store); registrar_memoria_inmunologica(registro.get("ip"),resultado["anomalo"])
        return {"nivel":13,"fitness":500 if resultado["detectores"]>=20 else 200 if resultado["detectores"]>=8 else 150,"detectores_dinamicos":resultado["detectores"],"genoma":genoma_actual(),"recarga_aplicada":False,"motivos":resultado["motivos"],"bloqueado":resultado.get("bloqueado",False)}
def init_db():
    con=sqlite3.connect(DB_PATH); con.execute("CREATE TABLE IF NOT EXISTS accesos (id INTEGER PRIMARY KEY, usuario TEXT, rol TEXT, recurso TEXT, ip TEXT, hora TEXT, fecha TEXT)"); con.commit(); con.close(); print(f"DB {DB_PATH} OK")
def health():
    genoma=genoma_actual(); mem=cargar_memoria_inmunologica()
    try: codigo=pathlib.Path(EVOLUTIVO_PATH).read_text(); ast.parse(codigo); detectores=len([l for l in codigo.splitlines() if "def detectar_" in l])
    except: detectores=0
    bloqueadas=sum(1 for v in mem.values() if v >= genoma.get("umbral_bloqueo",5))
    return {"nivel":13,"fitness":500 if detectores>=20 else 200 if detectores>=8 else 150,"detectores_dinamicos":detectores,"genoma":genoma,"ips_bloqueadas":bloqueadas,"memoria_total":len(mem)}
if __name__=="__main__":
    if "--init-db" in sys.argv: init_db()
    elif "--check" in sys.argv: print(json.dumps(health(), indent=2, ensure_ascii=False))
    elif "--tarea" in sys.argv:
        import tareas_complejas as tc; print(json.dumps(tc.ejecutar(sys.argv[sys.argv.index("--tarea")+1] if len(sys.argv)>sys.argv.index("--tarea")+1 else "analizar_logs"), indent=2, ensure_ascii=False))
    else: print(json.dumps(health(), indent=2, ensure_ascii=False))
