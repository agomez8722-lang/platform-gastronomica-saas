import time, json, requests, pathlib, ast
API="http://localhost:8000"
print("Supervisor Nivel 21 REAL - Auto-evolución cada 30s - 35 detectores")
ciclo=0
while True:
    ciclo+=1
    try:
        r=requests.get(f"{API}/health", timeout=10)
        h=r.json()
        print(f"[ciclo {ciclo}] NIVEL {h.get('nivel')} FITNESS {h.get('fitness')} DETECTORES {h.get('detectores_dinamicos')} GENOMA {h.get('genoma')}")
        # Auto-evolución: cada 3 ciclos intenta generar nuevo detector via Ollama
        if ciclo % 3 == 0:
            try:
                # llama a tu evolucion_codigo
                import evolucion_codigo
                evolucion_codigo.evolucionar_codigo(generaciones=1)
                print("  -> Evolución código ejecutada")
            except Exception as e:
                print(f"  Evol error {e}")
    except Exception as e:
        print(f"Supervisor error {e}")
    time.sleep(30)
