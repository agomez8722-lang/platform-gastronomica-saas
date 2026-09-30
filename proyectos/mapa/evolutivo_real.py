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
    if not ip or ip not in store:
        return False
    recent = [t for t in store.get(ip,[]) if time.time() - t < 60]
    return len(recent) >= 8

def detectar_2fa_bypass_v10(r: Dict) -> bool:
    return "/admin" in r.get("recurso","") and r.get("ip") in ["10.0.0.4","10.0.0.99"]

def detectar_sqli_v11(r: Dict) -> bool:
    payloads = ["' or '1'='1", "union select", "drop table", "' or 1=1", "--", ";--"]
    recurso = r.get("recurso","").lower()
    return any(p in recurso for p in payloads)

def detectar_path_traversal_v11(r: Dict) -> bool:
    recurso = r.get("recurso","").lower()
    return ".." in recurso or "etc/passwd" in recurso or "etc/shadow" in recurso

def detectar_user_agent_v11(r: Dict) -> bool:
    maliciosos = ["sqlmap", "nikto", "nmap", "masscan", "dirbuster"]
    ua = r.get("user_agent","").lower()
    return any(m in ua for m in maliciosos)

def detectar_xss_v12(r: Dict) -> bool:
    payloads = ["<script", "javascript:", "onerror=", "onload=", "<img", "alert("]
    recurso = r.get("recurso","").lower()
    return any(p in recurso for p in payloads)

def detectar_command_injection_v12(r: Dict) -> bool:
    payloads = ["; ls", "| cat", "&&", "`", "$(", "||", "; id"]
    recurso = r.get("recurso","").lower()
    return any(p in recurso for p in payloads)

def detectar_lfi_v12(r: Dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "php://" in recurso or "file://" in recurso or "zip://" in recurso

def detectar_rfi_v12(r: Dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "http://" in recurso and ("include" in recurso or "require" in recurso)

def detectar_xxe_v12(r: Dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "<!entity" in recurso or "xxe" in recurso

def detectar_ssrf_v12(r: Dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "169.254.169.254" in recurso or "metadata" in recurso

def detectar_open_redirect_v12(r: Dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "redirect" in recurso and ("//" in recurso or "http" in recurso)

def detectar_idor_v12(r: Dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "/user/" in recurso and r.get("rol") == "user" and "id=" in recurso

def detectar_csrf_v12(r: Dict) -> bool:
    return r.get("method","GET").upper() == "POST" and "/transfer" in r.get("recurso","").lower() and not r.get("csrf_token")

def detectar_file_upload_v12(r: Dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "/upload" in recurso and any(ext in recurso for ext in [".php", ".exe", ".sh", ".jsp"])

def detectar_ldap_injection_v12(r: Dict) -> bool:
    payloads = ["*()","*)(|", ")(cn=", "admin*)"]
    recurso = r.get("recurso","").lower()
    return any(p in recurso for p in payloads)

def detectar_nosql_injection_v12(r: Dict) -> bool:
    payloads = ["$ne", "$gt", "$where", "[$"]
    recurso = r.get("recurso","").lower()
    return any(p in recurso for p in payloads) and "/api/" in recurso
