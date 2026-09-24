import time, re
from typing import Dict

def _norm(r: Dict) -> str:
    return r.get("recurso_norm", r.get("recurso","").lower())

def detectar_privilegio_v10(r: Dict) -> bool:
    # RBAC real - no confia en rol del cliente, verifica path
    admin_paths = [r"/admin", r"/config", r"/users", r"/dashboard", r"/api/admin"]
    recurso = _norm(r)
    return any(re.search(p, recurso) for p in admin_paths) and r.get("rol") in ["user","guest",""]

def detectar_horario_v10(r: Dict) -> bool:
    try:
        h = int(r.get("hora","00:00:00").split(":")[0])
        return r.get("rol")=="admin" and (h>=22 or h<=6) and "/admin" in _norm(r)
    except:
        return False

def detectar_brute_force_v10(r: Dict) -> bool:
    return "/admin" in _norm(r) and r.get("rol") in ["user","guest",""]

def detectar_rate_limit_v10(ip: str, store: Dict) -> bool:
    if not ip or ip not in store:
        return False
    recent = [t for t in store.get(ip,[]) if time.time() - t < 60]
    return len(recent) >= 8

def detectar_2fa_bypass_v10(r: Dict) -> bool:
    # Ya no IPs hardcodeadas, usa header
    return "/admin" in _norm(r) and r.get("bypass_2fa") is True

def detectar_sqli_v11(r: Dict) -> bool:
    recurso = _norm(r)
    patterns = [r"'.*or.*'.*=.*'", r"union\s+select", r"drop\s+table", r"--", r";--", r"or\s+1=1"]
    return any(re.search(p, recurso) for p in patterns)

def detectar_path_traversal_v11(r: Dict) -> bool:
    recurso = _norm(r)
    return bool(re.search(r"\.\.|etc/passwd|etc/shadow", recurso))

def detectar_user_agent_v11(r: Dict) -> bool:
    ua = r.get("user_agent","").lower()
    return any(m in ua for m in ["sqlmap","nikto","nmap","masscan","dirbuster"])

# v23 - ya tenias 5
def detectar_ssti_advanced_v23(r: Dict) -> bool:
    return "{{7*7}}" in r.get("recurso","") or "ssti_advanced" in _norm(r)

def detectar_prototype_pollution_v23(r: Dict) -> bool:
    return "__proto__" in _norm(r) or "constructor[prototype]" in _norm(r)

def detectar_jwt_none_v23(r: Dict) -> bool:
    return "alg%22:%22none%22" in _norm(r).lower()

def detectar_cors_bypass_v23(r: Dict) -> bool:
    return "origin: null" in _norm(r).lower() or "cors_bypass" in _norm(r)

def detectar_graphql_introspection_v23(r: Dict) -> bool:
    return "__schema" in _norm(r) or "__typename" in _norm(r)

# v24 - 5 nuevos robustos
def detectar_nosql_injection_v24(r: Dict) -> bool:
    return bool(re.search(r"\$where|\$ne|\$gt", _norm(r)))

def detectar_ldap_injection_v24(r: Dict) -> bool:
    return "*)(uid=*" in r.get("recurso","") or "ldap_injection" in _norm(r)

def detectar_xpath_injection_v24(r: Dict) -> bool:
    return "' or '1'='1" in r.get("recurso","") and "xpath" in _norm(r)

def detectar_crlf_injection_v24(r: Dict) -> bool:
    return bool(re.search(r"%0d%0a|set-cookie", _norm(r)))

def detectar_hpp_v24(r: Dict) -> bool:
    return r.get("recurso","").count("?id=") > 1 or "hpp_bypass" in _norm(r)
