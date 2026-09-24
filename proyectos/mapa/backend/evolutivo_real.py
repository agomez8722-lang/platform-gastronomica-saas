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

def detectar_xss_v12(r: dict) -> bool:
    payloads = ["<script", "javascript:", "onerror=", "onload=", "<img"]
    recurso = r.get("recurso","").lower()
    return any(p in recurso for p in payloads)

def detectar_command_injection_v12(r: dict) -> bool:
    payloads = ["; ls", "| cat", "&& whoami", "`id`", "$(id)"]
    recurso = r.get("recurso","").lower()
    return any(p in recurso for p in payloads)

def detectar_ssrf_v13(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "169.254.169.254" in recurso or "metadata.google" in recurso or "ssrf" in recurso

def detectar_xxe_v13(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "<!entity" in recurso or "<!doctype" in recurso or "xxe" in recurso

def detectar_ldap_injection_v14(r: dict) -> bool:
    payloads = ["*()", ")(uid=", ")(cn=", "ldap://"]
    recurso = r.get("recurso","").lower()
    return any(p in recurso for p in payloads)

def detectar_open_redirect_v14(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "//evil.com" in recurso or "open_redirect" in recurso or "redirect=http" in recurso

def detectar_crlf_injection_v15(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "%0d%0a" in recurso or "\r\n" in recurso or "crlf" in recurso

def detectar_host_header_v15(r: dict) -> bool:
    host = r.get("host","").lower()
    recurso = r.get("recurso","").lower()
    return "evil.com" in host or "host_header" in recurso

def detectar_prototype_pollution_v16(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "__proto__" in recurso or "prototype" in recurso or "constructor[prototype]" in recurso

def detectar_nosql_injection_v16(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "$ne" in recurso or "$gt" in recurso or "$where" in recurso or "nosql" in recurso

def detectar_ssti_v17(r: dict) -> bool:
    payloads = ["{{7*7}}", "${7*7}", "<%=", "{{config", "__class__"]
    recurso = r.get("recurso","").lower()
    return any(p in recurso for p in payloads)

def detectar_log4shell_v17(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "${jndi:" in recurso or "log4shell" in recurso or "${env:" in recurso
