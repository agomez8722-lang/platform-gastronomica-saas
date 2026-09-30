from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import main as sec_engine
import urllib.parse
import json, pathlib

app = FastAPI(title="Chipre Manizales - WAF Nivel 14")

@app.get("/health")
def health():
    return sec_engine.health()

@app.get("/restaurantes")
def restaurantes():
    return [{"id":1,"nombre":"Chipre Manizales","mesas":12,"ciudad":"Manizales"}]

@app.get("/restaurantes/{id}/platos")
def platos(id: int):
    return [{"id":1,"nombre":"Bandeja Paisa","precio":28000}]

@app.middleware("http")
async def waf_bloqueo_real(request: Request, call_next):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown").split(",")[0].strip()
    raw_path = str(request.url.path) + ("?" + str(request.url.query) if request.url.query else "")
    path_decoded = urllib.parse.unquote_plus(raw_path)

    if request.url.path in ["/health","/docs","/openapi.json","/favicon.ico","/openapi.json"]:
        return await call_next(request)

    if sec_engine.esta_bloqueada(ip):
        return JSONResponse(status_code=403, content={"bloqueado":True,"ip":ip,"motivo":"ip_bloqueada_403","nivel":14,"fitness":500})

    registro = {"rol":"user","recurso":path_decoded.lower(),"ip":ip,"hora":"12:00:00","user_agent":request.headers.get("user-agent",""),"method":request.method}
    res = sec_engine._evaluar_reglas(registro, {})
    if res["anomalo"]:
        sec_engine.registrar_memoria_inmunologica(ip, True)
        if sec_engine.esta_bloqueada(ip):
            return JSONResponse(status_code=403, content={"bloqueado":True,"ip":ip,"motivos":res["motivos"],"nivel":14})

    return await call_next(request)
