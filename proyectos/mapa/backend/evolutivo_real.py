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


# --- Detectores Nivel 13: XSS y Command Injection ---

def detector_xss(r: Dict) -> bool:
    patrones = ["<script", "javascript:", "onerror=", "onload=", "<img src=x"]
    payload = (r.get("recurso", "") + " " + r.get("notas", "")).lower()
    return any(p in payload for p in patrones)


def detector_command_injection(r: Dict) -> bool:
    patrones = ["; cat ", "&& whoami", "| nc ", "$(", "`id`"]
    payload = (r.get("recurso", "") + " " + r.get("notas", "")).lower()
    return any(p in payload for p in patrones)

def detectar_xss_v12(r: dict) -> bool:
    xss = ["<script", "javascript:", "onerror=", "onload="]
    return any(x in r.get("recurso","").lower() for x in xss)

def detectar_command_injection_v12(r: dict) -> bool:
    cmd = [";cat ", "|cat", "&& ls", "`id`", "$(id)"]
    return any(c in r.get("recurso","").lower() for c in cmd)

def detectar_ssrf_v13(r: dict) -> bool:
    ssrf = ["127.0.0.1", "localhost", "169.254.169.254", "metadata.google", "internal"]
    return any(s in r.get("recurso","").lower() for s in ssrf)

def detectar_xxe_v13(r: dict) -> bool:
    xxe = ["<!entity", "<!doctype", "xxe", "xml external"]
    return any(x in r.get("recurso","").lower() for x in xxe)

def detectar_ldap_injection_v14(r: dict) -> bool:
    return any(x in r.get("recurso","").lower() for x in ["*()","(|","ldap://","uid="])

def detectar_open_redirect_v14(r: dict) -> bool:
    return any(x in r.get("recurso","").lower() for x in ["//evil.com","https://evil","@evil","redirect=http"])

def detectar_crlf_injection_v15(r: dict) -> bool:
    return any(x in r.get("recurso","") for x in ["%0d%0a", "\r\n", "crlf", "%0A%0D"])

def detectar_host_header_v15(r: dict) -> bool:
    return any(x in r.get("recurso","").lower() for x in ["evil.com", "host: evil", "x-forwarded-host: evil"])

def detectar_prototype_pollution_v16(r: dict) -> bool:
    return any(x in r.get("recurso","").lower() for x in ["__proto__", "constructor.prototype", "prototype pollution"])

def detectar_nosql_injection_v16(r: dict) -> bool:
    return any(x in r.get("recurso","").lower() for x in ["$where", "$ne", "$gt", "[$ne]", "nosql"])

def detectar_ssti_v17(r: dict) -> bool:
    payloads = ["{{7*7}}", "${7*7}", "<%=", "{{config", "__class__", "{{self}}"]
    recurso = r.get("recurso","").lower()
    return any(p in recurso for p in payloads)

def detectar_log4shell_v17(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "${jndi:" in recurso or "log4shell" in recurso or "${env:" in recurso or "${sys:" in recurso

def detectar_ssti_v17(r: dict) -> bool:
    payloads = ["{{7*7}}", "${7*7}", "<%=", "{{config", "__class__"]
    recurso = r.get("recurso","").lower()
    return any(p in recurso for p in payloads)

def detectar_log4shell_v17(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "${jndi:" in recurso or "log4shell" in recurso or "${env:" in recurso
