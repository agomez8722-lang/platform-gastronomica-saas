
import time, json, requests
from datetime import datetime
# Supervisor Nivel 8 - Rate Limiting + 2FA + auto-evolucion
API="http://localhost:8001"
print("Supervisor Nivel 8 - Rate Limiting 10 req/min + 2FA activo - cada 30s")
while True:
    try:
        # Check health Nivel 8
        r=requests.get(f"{API}/health", timeout=5)
        health=r.json()
        nivel=health.get('nivel',7)
        bloqueos=health.get('bloqueos',0)
        rate_ips=health.get('rate_limit',{}).get('ips_monitoreadas',0)
        
        # Decidir con auto-bloqueo
        r=requests.get(f"{API}/decidir?auto=true", timeout=5)
        data=r.json()
        
        # Rate limit status
        try:
            r2=requests.get(f"{API}/rate_limit/status", timeout=5)
            rate_data=r2.json()
        except:
            rate_data={}
            
        print(f"[{datetime.now().isoformat()}] NIVEL {nivel} | Anomalias:{len(data.get('anomalias',[]))} Bloqueos nuevos:{data.get('bloqueos_nuevos')} Fitness:{data.get('fitness',{}).get('fitness')} | RateLimit IPs:{rate_ips} Bloqueos tot:{bloqueos}")
        
        # Alerta si rate limiting activo
        if rate_ips > 0:
            print(f"  -> Rate limiting activo: {rate_data.get('rate_limit',{})}")
            
    except Exception as e:
        print(f"Supervisor error {e} - intentando local")
        try:
            from main import proponer_siguiente_orden
            result=proponer_siguiente_orden(True)
            print(f"  Local: {result['texto'][:150]}")
        except Exception as e2:
            print(f"  Local fail: {e2}")
    time.sleep(30)
