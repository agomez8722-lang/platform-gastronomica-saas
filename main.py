import json, csv, os
from datetime import datetime
from db import AccessRepository
from auth import filtrar_por_rol

def cargar_historico(path="historico_accesos.json"):
    if not os.path.exists(path):
        ejemplo=[
            {"usuario":"ana","rol":"admin","fecha":"2024-01-01","hora":"08:00:00","recurso":"/admin"},
            {"usuario":"luis","rol":"admin","fecha":"2024-01-02","hora":"09:30:00","recurso":"/admin/dashboard"},
            {"usuario":"maria","rol":"user","fecha":"2024-01-03","hora":"10:00:00","recurso":"/home"},
            {"usuario":"pedro","rol":"auditor","fecha":"2024-01-04","hora":"11:00:00","recurso":"/audit"},
            {"usuario":"juan","rol":"invitado","fecha":"2024-01-05","hora":"12:00:00","recurso":"/public"},
        ]
        with open(path,"w",encoding="utf-8") as f: json.dump(ejemplo,f,indent=2,ensure_ascii=False)
        return ejemplo
    with open(path,"r",encoding="utf-8") as f:
        data=json.load(f)
        if isinstance(data,dict) and "registros" in data: return data["registros"]
        if isinstance(data,list): return data
        return []

def filtrar_y_ordenar_accesos(datos, rol="admin"):
    if not datos: return []
    filtrados=[d for d in datos if d.get("rol")==rol]
    def k(x):
        try: return datetime.strptime(f"{x.get('fecha','')} {x.get('hora','')}", "%Y-%m-%d %H:%M:%S")
        except: return datetime.min
    filtrados.sort(key=k); return filtrados

def guardar_csv(datos, path="accesos_filtrados.csv"):
    if not datos: return False
    with open(path,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=datos[0].keys()); w.writeheader(); w.writerows(datos)
    return os.path.exists(path)

def guardar_json(datos, path="accesos_filtrados.json"):
    with open(path,"w",encoding="utf-8") as f: json.dump(datos,f,indent=2,ensure_ascii=False)
    return os.path.exists(path)

def calcular_estadisticas(datos):
    return {"total":len(datos) if datos else 0,
            "por_rol":{r:len([d for d in datos if d.get("rol")==r]) for r in ["admin","auditor","user","invitado"]} if datos else {},
            "usuarios_unicos":len(set(d.get("usuario") for d in datos)) if datos else 0}

if __name__=="__main__":
    d=cargar_historico(); repo=AccessRepository()
    if len(repo.listar())==0: repo.guardar(d)
    f=filtrar_y_ordenar_accesos(d,"admin"); guardar_csv(f); guardar_json(f)
    print(calcular_estadisticas(d))
