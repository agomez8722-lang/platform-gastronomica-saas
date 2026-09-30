import time
from typing import Dict

def detectar_privilegio_v10(r: Dict) -> bool:
    admin_paths = ["/admin", "/config", "/users", "/dashboard", "/api/admin"]
    return r.get("rol") == "user" and any(p in r.get("recurso","").lower() for p in admin_paths)

def detectar_horario_v10(r: Dict) -> bool:
    try:
        h = int(r.get("hora","00:00:00").split(":")[0])
        return r.get("rol")=="admin" and (h>=22 or h<=6) and "/admin" in r.get("recurso","")
    except:
        return False

def detectar_brute_force_v10(r: Dict) -> bool:
    return "/admin" in r.get("recurso","") and r.get("rol") in ["user","guest",""]

def detectar_rate_limit_v10(ip: str, store: Dict) -> bool:
    if not ip or ip not in store: return False
    recent = [t for t in store.get(ip,[]) if time.time() - t < 60]
    return len(recent) >= 8

def detectar_2fa_bypass_v10(r: Dict) -> bool:
    return "/admin" in r.get("recurso","") and r.get("ip") in ["10.0.0.4","10.0.0.99"]

def detectar_sqli_v11(r: Dict) -> bool:
    payloads = ["' or '1'='1", "union select", "drop table", "' or 1=1", "--", ";--"]
    return any(p in r.get("recurso","").lower() for p in payloads)

def detectar_path_traversal_v11(r: Dict) -> bool:
    recurso = r.get("recurso","").lower()
    return ".." in recurso or "etc/passwd" in recurso or "etc/shadow" in recurso

def detectar_user_agent_v11(r: Dict) -> bool:
    maliciosos = ["sqlmap", "nikto", "nmap", "masscan", "dirbuster"]
    return any(m in r.get("user_agent","").lower() for m in maliciosos)

def detectar_xss_v11(r: Dict) -> bool:
    return "<script" in r.get("recurso","").lower() or "onerror=" in r.get("recurso","").lower()

def detectar_csrf_v11(r: Dict) -> bool:
    return r.get("metodo","").upper() == "POST" and "/transfer" in r.get("recurso","").lower()

def detectar_lfi_v11(r: Dict) -> bool:
    return "file=" in r.get("recurso","").lower() and ".." in r.get("recurso","")

def detectar_rfi_v11(r: Dict) -> bool:
    return "http://" in r.get("recurso","").lower() and "url=" in r.get("recurso","").lower()

def detectar_command_injection_v12(r: Dict) -> bool:
    return any(c in r.get("recurso","") for c in ["; ls", "| cat", "&& whoami", "`id`"])

def detectar_xxe_v12(r: Dict) -> bool:
    return "<!ENTITY" in r.get("recurso","") or "<!DOCTYPE" in r.get("recurso","")

def detectar_ssrf_v12(r: Dict) -> bool:
    return "169.254.169.254" in r.get("recurso","") or "metadata.google" in r.get("recurso","")

def detectar_open_redirect_v12(r: Dict) -> bool:
    return "redirect=" in r.get("recurso","").lower() and "http" in r.get("recurso","").lower()

def detectar_file_upload_v12(r: Dict) -> bool:
    return r.get("recurso","").lower().endswith((".php",".exe",".sh")) and r.get("metodo","") == "POST"

def detectar_ldap_injection_v12(r: Dict) -> bool:
    return "*)(uid=*" in r.get("recurso","") or ")(cn=" in r.get("recurso","")

def detectar_ssti_v12(r: Dict) -> bool:
    return "{{7*7}}" in r.get("recurso","") or "${7*7}" in r.get("recurso","")

def detectar_idor_v12(r: Dict) -> bool:
    return "/api/user/" in r.get("recurso","") and r.get("rol") == "user"
