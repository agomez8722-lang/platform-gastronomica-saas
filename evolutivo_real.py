import time
from typing import Dict, List


def detectar_privilegio_v10(r: Dict) -> bool:
    admin_paths = ["/admin", "/config", "/users", "/dashboard", "/api/admin"]
    return r.get("rol") == "user" and any(p in r.get("recurso", "").lower() for p in admin_paths)


def detectar_horario_v10(r: Dict) -> bool:
    try:
        h = int(r.get("hora", "00:00:00").split(":")[0])
        return r.get("rol") == "admin" and (h >= 22 or h <= 6) and "/admin" in r.get("recurso", "")
    except Exception:
        return False


def detectar_brute_force_v10(r: Dict) -> bool:
    return "/admin" in r.get("recurso", "") and r.get("rol") in ["user", "guest", ""]


def detectar_rate_limit_v10(ip: str, store: Dict) -> bool:
    if not ip or ip not in store:
        return False
    recent = [t for t in store.get(ip, []) if time.time() - t < 60]
    return len(recent) >= 8


def detectar_2fa_bypass_v10(r: Dict) -> bool:
    return "/admin" in r.get("recurso", "") and r.get("ip") in ["10.0.0.4", "10.0.0.99"]


# --- Nuevos detectores Nivel 11: firmas de payload sospechosas ---

def detectar_sqli_v11(r: Dict) -> bool:
    patrones = ["' or '1'='1", "union select", "drop table", "--", "; select"]
    recurso = r.get("recurso", "").lower()
    return any(p in recurso for p in patrones)


def detectar_path_traversal_v11(r: Dict) -> bool:
    recurso = r.get("recurso", "")
    return "../" in recurso or "..%2f" in recurso.lower() or "%2e%2e" in recurso.lower()


def detectar_user_agent_v11(r: Dict) -> bool:
    ua = r.get("user_agent", "").lower()
    sospechosos = ["sqlmap", "nikto", "nmap", "masscan", "curl/7.0-scanner"]
    return any(s in ua for s in sospechosos)
