import time, json, requests, pathlib
from datetime import datetime
# Supervisor Nivel 9 - Autonomia Total + Ollama + Auto-Patching + Backup Seguro
API="http://localhost:8001"
OLLAMA_URL="http://localhost:11434"
print("Supervisor Nivel 9 - Autonomia Total - Rate Limiting + 2FA + Ollama + Auto-Patching - cada 30s")
ciclo=0
while True:
    ciclo+=1
    try:
        r=requests.get(f"{API}/health", timeout=5)
        health=r.json()
        nivel=health.get('nivel',8)
        bloqueos=health.get('bloqueos',0)
        rate_ips=health.get('rate_limit',{}).get('ips_monitoreadas',0)
        ollama_disp=health.get('ollama',{}).get('disponible', False)
        evoluciones=health.get('evoluciones',0)
        parches=health.get('parches',0)
        r=requests.get(f"{API}/decidir?auto=true", timeout=8)
        data=r.json()
        if ciclo % 3 == 0:
            try:
                revo=requests.post(f"{API}/evolucionar", json={}, timeout=15)
                evo_data=revo.json()
                print(f"[{datetime.now().isoformat()}] EVOLUCION: {evo_data.get('evolucion')} parches={len(evo_data.get('parches',[]))} ollama={evo_data.get('ollama_disponible')}")
            except Exception as e:
                print(f" Evolucion error {e}")
        try:
            r2=requests.get(f"{API}/rate_limit/status", timeout=5)
            rate_data=r2.json()
        except:
            rate_data={}
        try:
            ro=requests.get(f"{API}/ollama/status", timeout=5)
            ollama_status=ro.json()
        except:
            ollama_status={"ollama_disponible": False}
        print(f"[{datetime.now().isoformat()}] NIVEL {nivel} | Anomalias:{len(data.get('anomalias',[]))} Bloqueos nuevos:{data.get('bloqueos_nuevos')} Fitness:{data.get('fitness',{}).get('fitness')} | RateLimit IPs:{rate_ips} Bloqueos tot:{bloqueos} | Ollama:{ollama_disp} Evo:{evoluciones} Parches:{parches} Ciclo:{ciclo}")
        if rate_ips > 0:
            print(f"  -> Rate limiting activo: {rate_data.get('rate_limit',{})}")
        if not ollama_disp:
            print(f"  -> Ollama OFFLINE - usando fallback rule-based (normal si no tienes Ollama)")
        fitness=data.get('fitness',{}).get('fitness',0)
        if fitness < 100:
            print(f"  -> ALERTA Fitness bajo {fitness} - ejecutar tests")
    except Exception as e:
        print(f"Supervisor Nivel 9 error {e} - intentando local")
        try:
            from main import proponer_siguiente_orden, ollama_disponible
            result=proponer_siguiente_orden(True)
            print(f"  Local: {result['texto'][:180]} ollama={ollama_disponible()}")
        except Exception as e2:
            print(f"  Local fail: {e2}")
    time.sleep(30)
