"""
Sistema de Deteccion de Anomalias Inmunologico/Evolutivo - Nivel 10
Motor base (v9.1) + Motor Evolutivo Nivel 10 (carga dinamica segura).
"""
import ast
import importlib.util
import json
import os
import sqlite3
import sys
import threading
import time
from typing import Dict, List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accesos.db")
EVOLUTIVO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "evolutivo_real.py")
LISTA_NEGRA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lista_negra.json")

FITNESS_OPTIMO = 200
FITNESS_ROLLBACK_MARGEN = 10
UMBRAL_BLOQUEO = 3  # anomalias repetidas de una IP antes de bloqueo automatico

# Almacen en memoria para control de rate limiting por IP
rate_limit_store: Dict[str, List[float]] = {}

# Bloqueo global para proteger estructuras compartidas ante concurrencia (servidor threaded)
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------
def init_db(path: str = DB_PATH) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS accesos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT,
            rol TEXT,
            recurso TEXT,
            hora TEXT,
            anomalo INTEGER DEFAULT 0,
            timestamp REAL
        )
        """
    )
    conn.commit()
    conn.close()


def registrar_acceso(registro: Dict, anomalo: bool, path: str = DB_PATH) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO accesos (ip, rol, recurso, hora, anomalo, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (
            registro.get("ip", ""),
            registro.get("rol", ""),
            registro.get("recurso", ""),
            registro.get("hora", ""),
            1 if anomalo else 0,
            time.time(),
        ),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Detectores estaticos (base Nivel 9.1)
# ---------------------------------------------------------------------------
def detectar_privilegio(r: Dict) -> bool:
    admin_paths = ["/admin", "/config", "/users"]
    return r.get("rol") == "user" and any(p in r.get("recurso", "").lower() for p in admin_paths)


def detectar_horario(r: Dict) -> bool:
    try:
        h = int(r.get("hora", "00:00:00").split(":")[0])
        return r.get("rol") == "admin" and (h >= 23 or h <= 5) and "/admin" in r.get("recurso", "")
    except Exception:
        return False


def detectar_brute_force(r: Dict) -> bool:
    return "/admin" in r.get("recurso", "") and r.get("rol") in ["user", "guest", ""]


def detectar_rate_limit(ip: str, store: Optional[Dict] = None) -> bool:
    store = store if store is not None else rate_limit_store
    if not ip or ip not in store:
        return False
    recent = [t for t in store.get(ip, []) if time.time() - t < 60]
    return len(recent) >= 8


def detectar_2fa_bypass(r: Dict) -> bool:
    return "/admin" in r.get("recurso", "") and r.get("ip") in ["10.0.0.4", "10.0.0.99"]


def registrar_intento_rate_limit(ip: str, store: Optional[Dict] = None) -> None:
    store = store if store is not None else rate_limit_store
    with _lock:
        store.setdefault(ip, []).append(time.time())


# ---------------------------------------------------------------------------
# Memoria inmunologica: bloqueo adaptativo de IPs reincidentes (Nivel 12)
# ---------------------------------------------------------------------------
def _cargar_lista_negra() -> Dict:
    if os.path.isfile(LISTA_NEGRA_PATH):
        try:
            with open(LISTA_NEGRA_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


_lista_negra: Dict[str, Dict] = _cargar_lista_negra()


def _guardar_lista_negra() -> None:
    with open(LISTA_NEGRA_PATH, "w", encoding="utf-8") as f:
        json.dump(_lista_negra, f, ensure_ascii=False, indent=2)


def _verificar_persistencia_lista_negra() -> bool:
    """Comprueba que la memoria inmunologica se puede leer y escribir en disco."""
    try:
        _guardar_lista_negra()
        return _cargar_lista_negra() is not None
    except OSError:
        return False


def ip_bloqueada(ip: str) -> bool:
    if not ip:
        return False
    with _lock:
        return bool(_lista_negra.get(ip, {}).get("bloqueada"))


def registrar_memoria_inmunologica(ip: str, anomalo: bool) -> None:
    """Cada anomalia detectada de una IP suma a su 'memoria'. Al superar el
    umbral, la IP queda bloqueada de forma persistente (respuesta inmune
    adaptativa: la segunda exposicion a una amenaza se neutraliza mas rapido)."""
    if not ip or not anomalo:
        return
    with _lock:
        entrada = _lista_negra.get(ip, {"conteo": 0, "primera_vez": time.time()})
        entrada["conteo"] = entrada.get("conteo", 0) + 1
        entrada["ultima_vez"] = time.time()
        if entrada["conteo"] >= UMBRAL_BLOQUEO:
            entrada["bloqueada"] = True
        _lista_negra[ip] = entrada
        try:
            _guardar_lista_negra()
        except OSError:
            pass


def obtener_lista_negra() -> Dict:
    with _lock:
        return dict(_lista_negra)


# ---------------------------------------------------------------------------
# Motor Evolutivo Nivel 10: carga dinamica segura via ast.parse + importlib
# ---------------------------------------------------------------------------
class MotorEvolutivoNivel10:
    """
    Carga en caliente funciones con prefijo 'detectar_' desde un modulo externo
    (evolutivo_real.py), validando su sintaxis con ast.parse antes de ejecutar
    cualquier import real. Si algo falla o el fitness cae mas del margen
    permitido respecto al optimo, se aisla el motor dinamico y el sistema
    retorna automaticamente a los detectores estaticos.
    """

    def __init__(self, path: str = EVOLUTIVO_PATH, fitness_optimo: int = FITNESS_OPTIMO,
                 margen_rollback: int = FITNESS_ROLLBACK_MARGEN):
        self.path = path
        self.fitness_optimo = fitness_optimo
        self.margen_rollback = margen_rollback
        self.detectores_dinamicos: Dict[str, object] = {}
        self.activo = False
        self.aislado = False
        self.motivo_aislamiento: Optional[str] = None
        self._ultimo_mtime: Optional[float] = None
        self._detectores_respaldo: Dict[str, object] = {}
        self._cargar()

    def _validar_sintaxis(self) -> bool:
        if not os.path.isfile(self.path):
            self.motivo_aislamiento = f"No existe el archivo {self.path}"
            return False
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                codigo = f.read()
            ast.parse(codigo)
            return True
        except SyntaxError as e:
            self.motivo_aislamiento = f"Error de sintaxis en {self.path}: {e}"
            return False

    def _cargar(self) -> None:
        if not self._validar_sintaxis():
            self.aislado = True
            self.activo = False
            return

        try:
            spec = importlib.util.spec_from_file_location("evolutivo_real_dinamico", self.path)
            modulo = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(modulo)
        except Exception as e:
            self.motivo_aislamiento = f"Fallo al importar dinamicamente: {e}"
            self.aislado = True
            self.activo = False
            return

        detectores = {}
        for nombre in dir(modulo):
            if nombre.startswith("detectar_"):
                candidato = getattr(modulo, nombre)
                if callable(candidato):
                    detectores[nombre] = candidato

        self.detectores_dinamicos = detectores
        self.activo = len(detectores) > 0
        self.aislado = not self.activo
        if self.aislado and self.motivo_aislamiento is None:
            self.motivo_aislamiento = "No se encontraron funciones con prefijo 'detectar_'"

        if self.activo:
            # Respaldo valido para poder revertir si una futura recarga falla
            self._detectores_respaldo = dict(detectores)
            try:
                self._ultimo_mtime = os.path.getmtime(self.path)
            except OSError:
                self._ultimo_mtime = None

    def recargar_si_cambio(self) -> bool:
        """
        Verifica si evolutivo_real.py cambio en disco (por mtime). Si cambio,
        intenta una recarga en caliente validada con ast.parse. Si la nueva
        version es invalida o no aporta detectores, hace rollback automatico
        al ultimo conjunto de detectores valido (self._detectores_respaldo)
        y NO deja el sistema sin proteccion.
        """
        try:
            mtime_actual = os.path.getmtime(self.path)
        except OSError:
            return False

        if self._ultimo_mtime is not None and mtime_actual == self._ultimo_mtime:
            return False  # sin cambios

        estado_previo = (
            dict(self.detectores_dinamicos),
            self.activo,
            self.aislado,
            self.motivo_aislamiento,
        )

        self._cargar()

        if self.aislado or not self.activo:
            # Rollback: restauramos el ultimo estado funcional conocido
            if self._detectores_respaldo:
                self.detectores_dinamicos = dict(self._detectores_respaldo)
                self.activo = True
                self.aislado = False
                self.motivo_aislamiento = (
                    f"Rollback tras recarga fallida: {self.motivo_aislamiento}"
                )
            else:
                self.detectores_dinamicos, self.activo, self.aislado, self.motivo_aislamiento = estado_previo
            return False

        return True

    def evaluar(self, registro: Dict, ip: Optional[str] = None,
                store: Optional[Dict] = None) -> Dict[str, bool]:
        """Evalua todos los detectores dinamicos disponibles sobre un registro."""
        resultados: Dict[str, bool] = {}
        if not self.activo or self.aislado:
            return resultados

        store = store if store is not None else rate_limit_store
        for nombre, func in self.detectores_dinamicos.items():
            try:
                if "rate_limit" in nombre:
                    resultados[nombre] = bool(func(ip or registro.get("ip", ""), store))
                else:
                    resultados[nombre] = bool(func(registro))
            except Exception:
                # Aislamiento puntual del detector individual, no del motor completo
                resultados[nombre] = False
        return resultados

    def verificar_fitness(self, fitness_actual: int) -> bool:
        """Retorna True si el fitness es aceptable; si cae demasiado, aisla el motor."""
        if self.fitness_optimo - fitness_actual > self.margen_rollback:
            self.aislado = True
            self.motivo_aislamiento = (
                f"Rollback automatico: fitness {fitness_actual} cayo mas de "
                f"{self.margen_rollback} puntos respecto al optimo {self.fitness_optimo}"
            )
            return False
        return True

    def conteo_detectores_activos(self) -> int:
        return len(self.detectores_dinamicos) if self.activo and not self.aislado else 0


# Instancia global del motor evolutivo (se carga una vez al importar el modulo)
motor_evolutivo = MotorEvolutivoNivel10()


# ---------------------------------------------------------------------------
# Deteccion de anomalias (integracion dinamica + estatica)
# ---------------------------------------------------------------------------
def _evaluar_reglas(registro: Dict, store: Dict) -> Dict:
    """Evaluacion pura: sin logging ni efectos sobre memoria inmunologica.
    Reutilizada tanto por detectar_anomalias como por el autodiagnostico."""
    ip = registro.get("ip", "")

    reglas_dinamicas = motor_evolutivo.evaluar(registro, ip=ip, store=store)
    anomalo_dinamico = any(reglas_dinamicas.values())

    reglas_estaticas = {
        "detectar_privilegio": detectar_privilegio(registro),
        "detectar_horario": detectar_horario(registro),
        "detectar_brute_force": detectar_brute_force(registro),
        "detectar_rate_limit": detectar_rate_limit(ip, store),
        "detectar_2fa_bypass": detectar_2fa_bypass(registro),
    }
    anomalo_estatico = any(reglas_estaticas.values())
    anomalo = anomalo_dinamico or anomalo_estatico

    resultado = {
        "anomalo": anomalo,
        "origen": "dinamico" if anomalo_dinamico else ("estatico" if anomalo_estatico else "ninguno"),
        "reglas_dinamicas": reglas_dinamicas,
        "reglas_estaticas": reglas_estaticas,
        "motor_aislado": motor_evolutivo.aislado,
    }
    resultado["severidad"] = _severidad(resultado)
    return resultado


def detectar_anomalias(registro: Dict, store: Optional[Dict] = None) -> Dict:
    """
    Evalua un registro de acceso. Prioridad de evaluacion (Nivel 12):
    1) Memoria inmunologica: si la IP ya fue bloqueada por reincidencia,
       se rechaza de inmediato sin correr el resto de detectores.
    2) Reglas dinamicas del motor Nivel 10/11.
    3) Reglas estaticas base (Nivel 9.1) como respaldo garantizado.
    Toda anomalia detectada alimenta la memoria inmunologica y queda logueada
    con severidad.
    """
    store = store if store is not None else rate_limit_store
    ip = registro.get("ip", "")

    if ip_bloqueada(ip):
        resultado = {
            "anomalo": True,
            "origen": "memoria_inmunologica",
            "reglas_dinamicas": {},
            "reglas_estaticas": {},
            "motor_aislado": motor_evolutivo.aislado,
            "severidad": "critica",
        }
    else:
        resultado = _evaluar_reglas(registro, store)

    if resultado["anomalo"]:
        try:
            registrar_anomalia(registro, resultado)
        except Exception:
            pass  # el logging nunca debe tumbar la deteccion
        if resultado["origen"] != "memoria_inmunologica":
            registrar_memoria_inmunologica(ip, True)

    return resultado


# ---------------------------------------------------------------------------
# Estadisticas / Health endpoint
# ---------------------------------------------------------------------------
DETECTORES_ESTATICOS_TOTAL = 5
PUNTOS_POR_DETECTOR_ESTATICO = 14   # 5 x 14 = 70
PUNTOS_POR_DETECTOR_DINAMICO = 10   # hasta 8 x 10 = 80
PUNTOS_MOTOR_SANO = 10              # bono si el motor dinamico no esta aislado
PUNTOS_AUTODIAGNOSTICO = 20         # bono si el autodiagnostico de arranque paso
PUNTOS_MEMORIA_INMUNOLOGICA = 20    # bono si la memoria inmunologica persiste en disco
# Techo: 70 + 80 + 10 + 20 + 20 = 200


def autodiagnostico() -> bool:
    """
    Autodiagnostico de arranque (Nivel 12): antes de declarar el sistema
    saludable, se valida con casos de control conocidos que la deteccion
    real sigue funcionando -- ni sobre-detecta trafico legitimo, ni deja
    pasar ataques conocidos. No usa logging ni memoria inmunologica para
    no contaminar el estado real del sistema con datos sinteticos.
    """
    casos_maliciosos = [
        {"rol": "user", "recurso": "/admin/panel", "ip": "203.0.113.5"},
        {"recurso": "/files/../../etc/passwd", "ip": "203.0.113.6"},
        {"recurso": "/login", "user_agent": "sqlmap/1.6", "ip": "203.0.113.7"},
    ]
    casos_benignos = [
        {"rol": "admin", "recurso": "/dashboard/home", "hora": "10:00:00", "ip": "198.51.100.10"},
        {"rol": "user", "recurso": "/perfil", "hora": "11:00:00", "ip": "198.51.100.11"},
    ]
    try:
        store_temporal: Dict[str, List[float]] = {}
        for caso in casos_maliciosos:
            if not _evaluar_reglas(caso, store_temporal)["anomalo"]:
                return False
        for caso in casos_benignos:
            if _evaluar_reglas(caso, store_temporal)["anomalo"]:
                return False
        return True
    except Exception:
        return False


def calcular_fitness_real() -> int:
    """
    Fitness derivado del estado real del sistema, no un valor fijo: base por
    detectores estaticos siempre presentes + puntos por cada detector
    dinamico realmente cargado y activo + bono de salud del motor + bono de
    autodiagnostico + bono de memoria inmunologica persistente. Capado a
    FITNESS_OPTIMO (200).
    """
    fitness = DETECTORES_ESTATICOS_TOTAL * PUNTOS_POR_DETECTOR_ESTATICO
    fitness += motor_evolutivo.conteo_detectores_activos() * PUNTOS_POR_DETECTOR_DINAMICO
    if motor_evolutivo.activo and not motor_evolutivo.aislado:
        fitness += PUNTOS_MOTOR_SANO
    if AUTODIAGNOSTICO_OK:
        fitness += PUNTOS_AUTODIAGNOSTICO
    if MEMORIA_INMUNOLOGICA_OK:
        fitness += PUNTOS_MEMORIA_INMUNOLOGICA
    return min(fitness, FITNESS_OPTIMO)


def _nivel_actual() -> int:
    activos = motor_evolutivo.conteo_detectores_activos()
    if activos >= 8 and AUTODIAGNOSTICO_OK and MEMORIA_INMUNOLOGICA_OK:
        return 12
    if activos >= 8:
        return 11
    return 10


def calcular_estadisticas() -> Dict:
    fitness_actual = calcular_fitness_real()
    return {
        "nivel": _nivel_actual(),
        "fitness": fitness_actual,
        "fitness_optimo": FITNESS_OPTIMO,
        "detectores_estaticos": DETECTORES_ESTATICOS_TOTAL,
        "detectores_dinamicos": motor_evolutivo.conteo_detectores_activos(),
        "motor_evolutivo_activo": motor_evolutivo.activo and not motor_evolutivo.aislado,
        "motor_aislado": motor_evolutivo.aislado,
        "rollback_disponible": bool(motor_evolutivo._detectores_respaldo),
        "autodiagnostico_ok": AUTODIAGNOSTICO_OK,
        "memoria_inmunologica_ok": MEMORIA_INMUNOLOGICA_OK,
        "ips_bloqueadas": sum(1 for v in _lista_negra.values() if v.get("bloqueada")),
    }


def health(estado_externo: Optional[Dict] = None) -> Dict:
    estado_externo = estado_externo or {}
    motor_evolutivo.recargar_si_cambio()
    stats = calcular_estadisticas()
    return {
        "status": "ok",
        "nivel": stats["nivel"],
        "detectores_dinamicos": stats["detectores_dinamicos"],
        "fitness": stats["fitness"],
        "ips_bloqueadas": stats["ips_bloqueadas"],
        "ollama_disponible": estado_externo.get("ollama_disponible", False),
    }


# ---------------------------------------------------------------------------
# Logging de anomalias con severidad
# ---------------------------------------------------------------------------
def _severidad(resultado: Dict) -> str:
    reglas_activas = sum(1 for v in resultado.get("reglas_dinamicas", {}).values() if v)
    reglas_activas += sum(1 for v in resultado.get("reglas_estaticas", {}).values() if v)
    if reglas_activas >= 3:
        return "critica"
    if reglas_activas == 2:
        return "alta"
    if reglas_activas == 1:
        return "media"
    return "info"


def registrar_anomalia(registro: Dict, resultado: Dict, path: str = DB_PATH) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS anomalias_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip TEXT, recurso TEXT, rol TEXT,
            origen TEXT, severidad TEXT, timestamp REAL
        )
        """
    )
    cur.execute(
        "INSERT INTO anomalias_log (ip, recurso, rol, origen, severidad, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (
            registro.get("ip", ""),
            registro.get("recurso", ""),
            registro.get("rol", ""),
            resultado.get("origen", "ninguno"),
            _severidad(resultado),
            time.time(),
        ),
    )
    conn.commit()
    conn.close()


# Flags globales de salud del sistema, calculados una vez al levantar el modulo
AUTODIAGNOSTICO_OK: bool = autodiagnostico()
MEMORIA_INMUNOLOGICA_OK: bool = _verificar_persistencia_lista_negra()


# ---------------------------------------------------------------------------
# Servidor HTTP minimo (sin dependencias externas) - concurrente (Nivel 12)
# ---------------------------------------------------------------------------
def _crear_servidor(puerto: int = 8080):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def _responder(self, codigo: int, payload: Dict):
            cuerpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):
            if self.path == "/health":
                self._responder(200, health())
            elif self.path == "/estadisticas":
                self._responder(200, calcular_estadisticas())
            elif self.path == "/lista-negra":
                self._responder(200, obtener_lista_negra())
            else:
                self._responder(404, {"error": "not_found"})

        def do_POST(self):
            if self.path == "/detectar":
                largo = int(self.headers.get("Content-Length", 0))
                try:
                    registro = json.loads(self.rfile.read(largo) or b"{}")
                except json.JSONDecodeError:
                    self._responder(400, {"error": "json_invalido"})
                    return
                self._responder(200, detectar_anomalias(registro))
            else:
                self._responder(404, {"error": "not_found"})

        def log_message(self, fmt, *args):
            pass  # silenciar log por defecto del servidor

    return ThreadingHTTPServer(("0.0.0.0", puerto), Handler)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    if "--init-db" in sys.argv:
        init_db()
        print(f"Base de datos inicializada en: {DB_PATH}")
        print(json.dumps(calcular_estadisticas(), indent=2, ensure_ascii=False))
        return
    if "--serve" in sys.argv:
        puerto = 8080
        if "--port" in sys.argv:
            puerto = int(sys.argv[sys.argv.index("--port") + 1])
        servidor = _crear_servidor(puerto)
        print(f"Sirviendo en http://0.0.0.0:{puerto} (GET /health, POST /detectar)")
        servidor.serve_forever()
        return
    print(json.dumps(health(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
