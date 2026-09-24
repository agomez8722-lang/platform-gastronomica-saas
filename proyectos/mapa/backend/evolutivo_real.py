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
    return "%0d%0a" in recurso or "crlf" in recurso

def detectar_host_header_v15(r: dict) -> bool:
    host = r.get("host","").lower()
    recurso = r.get("recurso","").lower()
    return "evil.com" in host or "host_header" in recurso

def detectar_prototype_pollution_v16(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "__proto__" in recurso or "prototype" in recurso

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

def detectar_jwt_v18(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    auth = r.get("authorization","").lower()
    return "eyj" in recurso or "eyj" in auth or "jwt" in recurso or "alg:none" in recurso

def detectar_csrf_v18(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "csrf" in recurso or "xsrf" in recurso

def detectar_file_upload_v19(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return ("upload" in recurso and ".php" in recurso) or "file_upload" in recurso or "shell.php" in recurso

def detectar_xxe_billion_laughs_v19(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "billion" in recurso or "xxe_billion" in recurso

def detectar_open_redirect_data_uri_v19(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "data:text" in recurso or "data:application" in recurso or "redirect_data" in recurso

def detectar_graphql_introspection_v20(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "graphql" in recurso or "__schema" in recurso or "introspection" in recurso

def detectar_java_deserialization_v20(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "rO0AB" in recurso or "deserialization" in recurso or "objectinputstream" in recurso

def detectar_advanced_ssti_v20(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "self.__class__" in recurso or "mro()" in recurso or "subclasses" in recurso

def detectar_jwt_kid_injection_v20(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "kid=" in recurso or "jwt_kid" in recurso or "jku" in recurso or "x5u" in recurso

def detectar_http_request_smuggling_v20(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "smuggling" in recurso or "cl.te" in recurso or "te.cl" in recurso

def detectar_xxe_advanced_v21(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "expect:" in recurso and "xxe" in recurso or "xinclude" in recurso

def detectar_ssrf_bypass_v21(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "0.0.0.0" in recurso or "127.0.0.1%09" in recurso or "ssrf_bypass" in recurso

def detectar_open_redirect_js_v21(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "javascript:window.location" in recurso or "data:text/html;base64" in recurso

def detectar_host_header_injection_v21(r: dict) -> bool:
    host = r.get("host","").lower()
    return "evil.com%09" in host or "host_injection" in host

def detectar_log4shell_bypass_v21(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "${jndi:ldap://${env:" in recurso or "log4shell_bypass" in recurso


def detectar_xxe_advanced_v22(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "<!entity" in recurso and "system" in recurso or "xxe_advanced" in recurso

def detectar_ssrf_bypass_v22(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "0.0.0.0" in recurso or "127.0.0.1%09" in recurso or "ssrf_bypass" in recurso

def detectar_open_redirect_js_v22(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "javascript:window.location" in recurso or "data:text/html;base64" in recurso

def detectar_host_header_injection_v22(r: dict) -> bool:
    host = r.get("host","").lower()
    return "evil.com%09" in host or "host_injection" in host

def detectar_log4shell_bypass_v22(r: dict) -> bool:
    recurso = r.get("recurso","").lower()
    return "${jndi:ldap://${env:" in recurso or "log4shell_bypass" in recurso

def detectar_ssti_advanced_v23(r: dict) -> bool:
    return "{{7*7}}" in r.get("recurso","") or "ssti_advanced" in r.get("recurso","")

def detectar_prototype_pollution_v23(r: dict) -> bool:
    return "__proto__" in r.get("recurso","") or "constructor[prototype]" in r.get("recurso","")

def detectar_jwt_none_v23(r: dict) -> bool:
    return "alg%22:%22none%22" in r.get("recurso","").lower()

def detectar_cors_bypass_v23(r: dict) -> bool:
    return "origin: null" in r.get("recurso","").lower() or "cors_bypass" in r.get("recurso","")

def detectar_graphql_introspection_v23(r: dict) -> bool:
    return "__schema" in r.get("recurso","") or "__typename" in r.get("recurso","")

def detectar_nosql_injection_v24(r: dict) -> bool:
    return "$where" in r.get("recurso","") or "nosql_injection" in r.get("recurso","")

def detectar_ldap_injection_v24(r: dict) -> bool:
    return "*)(uid=*" in r.get("recurso","") or "ldap_injection" in r.get("recurso","")

def detectar_xpath_injection_v24(r: dict) -> bool:
    return "' or '1'='1" in r.get("recurso","") and "xpath" in r.get("recurso","").lower()

def detectar_crlf_injection_v24(r: dict) -> bool:
    return "%0d%0aSet-Cookie" in r.get("recurso","") or "crlf_injection" in r.get("recurso","")

def detectar_hpp_v24(r: dict) -> bool:
    return r.get("recurso","").count("?id=") > 1 or "hpp_bypass" in r.get("recurso","")
