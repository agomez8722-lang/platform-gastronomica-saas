from roles import ROLES
def validar_rol(registro, rol_requerido):
    if not registro or not rol_requerido: return False
    r = registro.get("rol")
    if not r or r not in ROLES or rol_requerido not in ROLES: return False
    return ROLES[r] >= ROLES[rol_requerido]

def filtrar_por_rol(datos, rol):
    if not datos or not rol: return []
    return [d for d in datos if d.get("rol") == rol]
