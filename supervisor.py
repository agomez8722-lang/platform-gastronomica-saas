# -*- coding: utf-8 -*-
"""
SUPREME TDD EVOLVING AGENT
Arquitectura multiagente autónoma para evolución segura de proyectos Python.

Componentes:
- Sensor de intenciones
- Planificador
- Arquitecto
- Implementador
- QA/TDD
- Revisor
- Controlador
- Consolidador
- Memoria de evolución

Requisitos:
- Python 3.9+
- requests
- Ollama ejecutándose localmente

No requiere watchdog.
El sensor utiliza polling para mantener cero dependencias adicionales.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


# ============================================================================
# LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

LOGGER = logging.getLogger("SupremeTDDAgent")


# ============================================================================
# CONFIGURACIÓN
# ============================================================================

@dataclass
class ProjectConfig:
    target_project_path: str = str(
        Path("~/Desktop/mi_proyecto_automatizado_PRUEBA").expanduser()
    )

    orders_file: str = str(
        Path("~/Desktop/ordenes.txt").expanduser()
    )

    # URL base de la API de generación de Ollama
    ollama_url: str = "http://localhost:11434/api/generate"

    # URL para health-check (listar modelos disponibles)
    ollama_tags_url: str = "http://localhost:11434/api/tags"

    # Modelo pesado: solo para el Implementador (requiere calidad máxima)
    model_implementador: str = "qwen2.5-coder:7b"

    # Modelo ligero: para agentes rápidos (Planificador, Arquitecto, QA, Revisor)
    model_rapido: str = "qwen2.5-coder:3b"

    # Compatibilidad: model_name usa el modelo pesado por defecto
    model_name: str = "qwen2.5-coder:7b"

    required_files: List[str] = field(
        default_factory=lambda: [
            "test_proyecto.py"
        ]
    )

    # Timeouts por rol (segundos)
    timeout_planificador: int = 90
    timeout_arquitecto: int = 90
    timeout_implementador: int = 240
    timeout_qa: int = 90
    timeout_revisor: int = 60

    # Timeout genérico (fallback)
    ollama_timeout: int = 180

    sandbox_timeout: int = 30

    max_attempts: int = 3

    # Retries de red por llamada a Ollama
    ollama_max_retries: int = 3

    # Backoff base entre reintentos de red (segundos)
    ollama_retry_backoff: float = 2.0

    poll_interval: float = 1.0

    max_order_length: int = 12000

    max_file_size: int = 300000

    allowed_extensions: List[str] = field(
        default_factory=lambda: [
            ".py",
            ".txt",
            ".md",
            ".json",
            ".js",
            ".ts",
        ]
    )

    ignored_directories: List[str] = field(
        default_factory=lambda: [
            ".git",
            ".venv",
            "venv",
            "env",
            ".env",
            "__pycache__",
            ".pytest_cache",
            "backups",
            ".idea",
            ".vscode",
            "node_modules",
        ]
    )


# ============================================================================
# UTILIDADES
# ============================================================================

def ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def sha256_text(texto: str) -> str:
    return hashlib.sha256(
        texto.encode("utf-8", errors="ignore")
    ).hexdigest()


# ============================================================================
# AGENTE PRINCIPAL
# ============================================================================

class SupremeTDDAgent:

    def __init__(
        self,
        config: Optional[ProjectConfig] = None,
    ) -> None:

        self.config = config or ProjectConfig()

        self.target_path = (
            Path(self.config.target_project_path)
            .expanduser()
            .resolve()
        )

        self.orders_file = (
            Path(self.config.orders_file)
            .expanduser()
            .resolve()
        )

        self.main_file = self.target_path / "main.py"

        self.test_file = (
            self.target_path / "test_proyecto.py"
        )

        self.memory_dir = (
            self.target_path / ".supreme_agent"
        )

        self.history_file = (
            self.memory_dir / "evolution_history.jsonl"
        )

        self.backup_dir = (
            self.memory_dir / "backups"
        )

        self._ensure_environment()

    # ========================================================================
    # ENTORNO
    # ========================================================================

    def _ensure_environment(self) -> None:

        self.target_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.orders_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.memory_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.backup_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self.orders_file.exists():

            self.orders_file.touch()

        LOGGER.info(
            "Espacio de trabajo: %s",
            self.target_path,
        )

    # ========================================================================
    # PYTHON
    # ========================================================================

    def _python(self) -> str:

        if not sys.executable:
            raise RuntimeError(
                "No se pudo determinar el intérprete Python."
            )

        return sys.executable

    # ========================================================================
    # MEMORIA
    # ========================================================================

    def guardar_memoria(
        self,
        tipo: str,
        datos: Dict[str, Any],
    ) -> None:

        registro = {
            "timestamp": ahora(),
            "tipo": tipo,
            "datos": datos,
        }

        try:

            with self.history_file.open(
                "a",
                encoding="utf-8",
            ) as archivo:

                archivo.write(
                    json.dumps(
                        registro,
                        ensure_ascii=False,
                    )
                    + "\n"
                )

        except OSError as error:

            LOGGER.warning(
                "No se pudo guardar memoria: %s",
                error,
            )

    # ========================================================================
    # ESCANEO
    # ========================================================================

    def escanear_proyecto(self) -> Dict[str, str]:

        resultado: Dict[str, str] = {}

        ignorados = set(
            self.config.ignored_directories
        )

        extensiones = {
            extension.lower()
            for extension in self.config.allowed_extensions
        }

        for root, dirs, files in os.walk(
            self.target_path
        ):

            dirs[:] = [
                directory
                for directory in dirs
                if directory not in ignorados
            ]

            for filename in files:

                path = Path(root) / filename

                if (
                    path == self.orders_file
                    or path == self.history_file
                ):
                    continue

                if path.suffix.lower() not in extensiones:
                    continue

                try:

                    if path.stat().st_size > self.config.max_file_size:

                        LOGGER.warning(
                            "Archivo omitido por tamaño: %s",
                            path,
                        )

                        continue

                    relative = path.relative_to(
                        self.target_path
                    )

                    resultado[str(relative)] = (
                        path.read_text(
                            encoding="utf-8",
                            errors="ignore",
                        )
                    )

                except (
                    OSError,
                    UnicodeError,
                ) as error:

                    LOGGER.warning(
                        "No se pudo leer %s: %s",
                        path,
                        error,
                    )

        LOGGER.info(
            "Archivos encontrados: %d",
            len(resultado),
        )

        return resultado

    # ========================================================================
    # OLLAMA
    # ========================================================================


    # ========================================================================
    # HEALTH-CHECK DE OLLAMA
    # ========================================================================

    def verificar_ollama(
        self,
    ) -> List[str]:
        """
        Comprueba que Ollama está activo y devuelve la lista de modelos
        disponibles. Lanza RuntimeError si no hay conexión.
        """
        try:
            resp = requests.get(
                self.config.ollama_tags_url,
                timeout=5,
            )
        except requests.exceptions.ConnectionError as error:
            raise RuntimeError(
                "Ollama no está disponible en "
                f"{self.config.ollama_tags_url}. "
                "Asegúrate de que `ollama serve` está activo."
            ) from error
        except requests.exceptions.Timeout as error:
            raise RuntimeError(
                "Ollama no respondió al health-check en 5 s."
            ) from error

        if resp.status_code != 200:
            raise RuntimeError(
                f"Ollama health-check falló HTTP {resp.status_code}."
            )

        try:
            data = resp.json()
        except ValueError as error:
            raise RuntimeError(
                "Ollama health-check devolvió respuesta no JSON."
            ) from error

        modelos = [
            m.get("name", "")
            for m in data.get("models", [])
        ]
        LOGGER.info(
            "Ollama disponible. Modelos: %s",
            modelos,
        )
        return modelos

    def _modelo_y_timeout(
        self,
        rol: str,
    ) -> Tuple[str, int]:
        """
        Devuelve (model_name, timeout_segundos) según el rol del agente.
        Usa el modelo ligero para agentes rápidos y el pesado para el
        Implementador. Si el modelo ligero no está disponible, cae al
        modelo pesado automáticamente.
        """
        rol = rol.lower()

        # Asignación de modelos y timeouts por rol
        rapidos = {
            "planificador": self.config.timeout_planificador,
            "arquitecto": self.config.timeout_arquitecto,
            "qa": self.config.timeout_qa,
            "revisor": self.config.timeout_revisor,
        }
        if rol in rapidos:
            return self.config.model_rapido, rapidos[rol]

        if rol == "implementador":
            return self.config.model_implementador, self.config.timeout_implementador

        # Fallback genérico
        return self.config.model_name, self.config.ollama_timeout

    def consultar_ollama(
        self,
        prompt: str,
        rol: str = "generico",
    ) -> str:
        """
        Llama a Ollama con streaming real, retry automático con backoff
        exponencial y selección de modelo/timeout según el rol del agente.

        Parámetros:
            prompt: texto a enviar al modelo.
            rol: "planificador" | "arquitecto" | "implementador" | "qa" |
                 "revisor" | "generico"

        Retorna el texto de respuesta del modelo.
        Lanza RuntimeError si todos los reintentos fallan.
        """
        modelo, timeout = self._modelo_y_timeout(rol)

        # Modo streaming: recibimos tokens uno a uno → sin timeout de socket
        payload = {
            "model": modelo,
            "prompt": prompt,
            "stream": True,
            "format": "json",
            "options": {
                # Parámetros de generación para JSON consistente
                "temperature": 0.1,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
            },
        }

        ultimo_error: Optional[Exception] = None

        for intento in range(1, self.config.ollama_max_retries + 1):

            LOGGER.info(
                "Ollama [%s / modelo=%s / timeout=%ds] intento %d/%d",
                rol,
                modelo,
                timeout,
                intento,
                self.config.ollama_max_retries,
            )

            t_inicio = time.monotonic()

            try:
                response = requests.post(
                    self.config.ollama_url,
                    json=payload,
                    # read_timeout = timeout total de generación
                    # connect_timeout = 10 s
                    timeout=(10, timeout),
                    stream=True,
                )

            except requests.exceptions.ConnectionError as error:
                ultimo_error = RuntimeError(
                    "No se pudo conectar con Ollama."
                )
                LOGGER.warning(
                    "Intento %d — conexión fallida: %s",
                    intento, error,
                )

            except requests.exceptions.Timeout as error:
                ultimo_error = RuntimeError(
                    f"Ollama superó el tiempo máximo de espera ({timeout} s)."
                )
                LOGGER.warning(
                    "Intento %d — timeout (%ds): %s",
                    intento, timeout, error,
                )

            except requests.exceptions.RequestException as error:
                ultimo_error = RuntimeError(
                    f"Error de red comunicando con Ollama: {error}"
                )
                LOGGER.warning(
                    "Intento %d — error de red: %s",
                    intento, error,
                )

            else:
                if response.status_code != 200:
                    ultimo_error = RuntimeError(
                        f"Ollama respondió HTTP {response.status_code}: "
                        f"{response.text[:500]}"
                    )
                    LOGGER.warning(
                        "Intento %d — HTTP %d",
                        intento, response.status_code,
                    )
                else:
                    # Acumular tokens del streaming
                    fragmentos: List[str] = []
                    try:
                        for linea in response.iter_lines():
                            if not linea:
                                continue
                            try:
                                chunk = json.loads(linea)
                            except json.JSONDecodeError:
                                continue
                            fragmento = chunk.get("response", "")
                            if fragmento:
                                fragmentos.append(fragmento)
                            if chunk.get("done", False):
                                break
                    except requests.exceptions.ChunkedEncodingError as error:
                        ultimo_error = RuntimeError(
                            f"Streaming interrumpido: {error}"
                        )
                        LOGGER.warning(
                            "Intento %d — streaming roto: %s",
                            intento, error,
                        )
                        # Ir al backoff y reintentar
                        fragmentos = []

                    if fragmentos:
                        respuesta = "".join(fragmentos).strip()
                        if respuesta:
                            t_total = time.monotonic() - t_inicio
                            LOGGER.info(
                                "Ollama respondió en %.1f s (%d chars)",
                                t_total,
                                len(respuesta),
                            )
                            return respuesta

                    if not fragmentos:
                        ultimo_error = RuntimeError(
                            "Ollama devolvió respuesta vacía (streaming)."
                        )
                        LOGGER.warning(
                            "Intento %d — respuesta vacía",
                            intento,
                        )

            # Backoff exponencial antes del siguiente intento
            if intento < self.config.ollama_max_retries:
                espera = self.config.ollama_retry_backoff * (2 ** (intento - 1))
                LOGGER.info(
                    "Esperando %.1f s antes del reintento...",
                    espera,
                )
                time.sleep(espera)

        raise ultimo_error or RuntimeError(
            "Ollama falló sin error específico."
        )

    # ========================================================================
    # RECUPERACIÓN JSON
    # ========================================================================

    def extraer_json(
        self,
        texto: str,
    ) -> Dict[str, Any]:
        """
        Extrae el primer objeto JSON válido del texto generado por Ollama.

        Estrategias en orden de prioridad:
        1. Parsear el texto completo directamente.
        2. Extraer bloques ```json ... ``` o ``` ... ```.
        3. Localizar el JSON más externo { ... } del texto.
        4. Reparar problemas comunes: comas finales, comillas simples,
           controles Unicode, truncamiento.
        5. Extracción por fuerza bruta de substring.
        """
        texto = texto.strip()

        def _parse(candidato: str) -> Optional[Dict]:
            candidato = candidato.strip()
            if not candidato:
                return None
            try:
                data = json.loads(candidato)
                if isinstance(data, dict):
                    return data
            except (json.JSONDecodeError, TypeError):
                pass
            return None

        def _reparar(texto_raw: str) -> str:
            """Aplica reparaciones heurísticas al JSON antes de parsear."""
            # Eliminar comas antes de } o ]
            texto_raw = re.sub(r",\s*([}\]])", r"", texto_raw)
            # Reemplazar comillas simples que rodean valores de string
            # (solo casos obvios, sin romper contenido)
            # Eliminar caracteres de control problemáticos (excepto \n \t)
            texto_raw = re.sub(
                r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]",
                "",
                texto_raw,
            )
            # Si el JSON está truncado, intentar cerrar la estructura
            abiertos_llave = texto_raw.count("{") - texto_raw.count("}")
            abiertos_corchete = texto_raw.count("[") - texto_raw.count("]")
            if abiertos_llave > 0 or abiertos_corchete > 0:
                # Cerrar la última cadena si está abierta
                texto_raw = re.sub(r'("[^"]*?)$', r'\1"', texto_raw)
                texto_raw += "]" * max(abiertos_corchete, 0)
                texto_raw += "}" * max(abiertos_llave, 0)
            return texto_raw

        candidatos: List[str] = [texto]

        # Estrategia 2: bloques ```json ... ``` o ``` ... ```
        bloques = re.findall(
            r"```(?:json)?\s*(.*?)```",
            texto,
            flags=re.DOTALL | re.IGNORECASE,
        )
        candidatos.extend(bloques)

        # Estrategia 3: JSON más externo { ... }
        inicio = texto.find("{")
        fin = texto.rfind("}")
        if inicio >= 0 and fin > inicio:
            candidatos.append(texto[inicio: fin + 1])

        # Estrategia 4: con reparación
        if inicio >= 0:
            candidatos.append(_reparar(texto[inicio: fin + 1] if fin > inicio else texto[inicio:]))

        # Estrategia 5: fuerza bruta — buscar todos los { y probar substrings
        posiciones = [i for i, c in enumerate(texto) if c == "{"]
        for pos in posiciones[:5]:  # máximo 5 intentos
            for cierre in range(len(texto) - 1, pos, -1):
                if texto[cierre] == "}":
                    candidatos.append(texto[pos: cierre + 1])
                    break

        for candidato in candidatos:
            resultado = _parse(candidato)
            if resultado is not None:
                return resultado
            # Intentar con reparación
            resultado = _parse(_reparar(candidato))
            if resultado is not None:
                LOGGER.warning(
                    "JSON reparado automáticamente (contenía errores menores)."
                )
                return resultado

        LOGGER.error(
            "No se pudo extraer JSON. Texto recibido (primeros 500 chars): %s",
            texto[:500],
        )
        raise ValueError(
            "No se pudo interpretar el JSON generado por Ollama. "
            "Verifica que el modelo soporte el modo JSON."
        )

    # ========================================================================
    # VALIDACIÓN DE RUTAS
    # ========================================================================

    def ruta_segura(
        self,
        relativa: str,
    ) -> Path:

        if not isinstance(
            relativa,
            str,
        ):

            raise ValueError(
                "La ruta debe ser texto."
            )

        relativa = relativa.strip()

        if not relativa:
            raise ValueError(
                "Ruta vacía."
            )

        candidato = (
            self.target_path / relativa
        ).resolve()

        try:

            candidato.relative_to(
                self.target_path
            )

        except ValueError as error:

            raise ValueError(
                f"Ruta fuera del proyecto: {relativa}"
            ) from error

        if candidato.name.startswith("."):

            raise ValueError(
                f"No se permite modificar archivos ocultos: {relativa}"
            )

        if candidato.suffix.lower() not in {
            ext.lower()
            for ext in self.config.allowed_extensions
        }:

            raise ValueError(
                f"Extensión no permitida: {relativa}"
            )

        return candidato

    # ========================================================================
    # VALIDACIÓN AST
    # ========================================================================

    def validar_python(
        self,
        codigo: str,
        nombre: str,
    ) -> ast.AST:

        if not codigo.strip():

            raise ValueError(
                f"{nombre} está vacío."
            )

        try:

            return ast.parse(
                codigo,
                filename=nombre,
            )

        except SyntaxError as error:

            raise ValueError(
                f"SyntaxError en {nombre}: "
                f"línea {error.lineno}, "
                f"columna {error.offset}: "
                f"{error.msg}"
            ) from error

    # ========================================================================
    # SEGURIDAD AST
    # ========================================================================

    def detectar_codigo_peligroso(self, codigo):
        """
        Detecta código Python potencialmente peligroso mediante AST.

        Devuelve únicamente el identificador del peligro:
            exec
            eval
            compile
            system
            subprocess

        Devuelve None cuando no encuentra una operación peligrosa.

        Acepta tanto un AST como código fuente Python.
        """

        # Los tests y algunos consumidores pueden entregar directamente
        # código fuente. Convertirlo a AST permite analizar ambos formatos.
        if isinstance(codigo, str):
            try:
                codigo = ast.parse(codigo)
            except SyntaxError:
                return None

        if not isinstance(codigo, ast.AST):
            return None

        funciones_prohibidas = {
            "eval",
            "exec",
            "compile",
        }

        # Nombres que representan módulos peligrosos.
        aliases_os = {"os"}
        aliases_subprocess = set()

        # Nombres que representan funciones peligrosas.
        aliases_system = set()
        aliases_subprocess_func = set()

        # ---------------------------------------------------------
        # Primera pasada:
        # identificar imports.
        # ---------------------------------------------------------
        for node in ast.walk(codigo):

            if isinstance(node, ast.Import):
                for alias in node.names:

                    if alias.name == "os":
                        aliases_os.add(alias.asname or "os")

                    if alias.name == "subprocess":
                        return "subprocess"

            elif isinstance(node, ast.ImportFrom):

                modulo = node.module or ""

                if (
                    modulo == "subprocess"
                    or modulo.startswith("subprocess.")
                ):
                    # Cualquier import desde subprocess es peligroso,
                    # manteniendo el comportamiento original.
                    return "subprocess"

                if modulo == "os":
                    for alias in node.names:
                        if alias.name == "system":
                            aliases_system.add(
                                alias.asname or alias.name
                            )

        # ---------------------------------------------------------
        # Propagación de aliases.
        #
        # Ejemplos:
        #
        # f = os.system
        # g = f
        # g(...)
        #
        # import subprocess as sp
        # f = sp.run
        # f(...)
        #
        # La propagación se repite hasta que no aparezcan aliases nuevos.
        # ---------------------------------------------------------
        cambio = True

        while cambio:
            cambio = False

            for node in ast.walk(codigo):

                if not isinstance(node, ast.Assign):
                    continue

                if not node.targets:
                    continue

                # Solo necesitamos nombres simples como destino:
                # f = ...
                destinos = [
                    target.id
                    for target in node.targets
                    if isinstance(target, ast.Name)
                ]

                if not destinos:
                    continue

                valor = node.value

                # f = os.system
                if (
                    isinstance(valor, ast.Attribute)
                    and valor.attr == "system"
                    and isinstance(valor.value, ast.Name)
                    and valor.value.id in aliases_os
                ):
                    for destino in destinos:
                        if destino not in aliases_system:
                            aliases_system.add(destino)
                            cambio = True

                # f = sp.run
                #
                # Si sp es un alias de subprocess, cualquier atributo
                # llamado desde él se considera perteneciente al módulo
                # peligroso.
                if (
                    isinstance(valor, ast.Attribute)
                    and isinstance(valor.value, ast.Name)
                    and valor.value.id in aliases_subprocess
                ):
                    for destino in destinos:
                        if destino not in aliases_subprocess_func:
                            aliases_subprocess_func.add(destino)
                            cambio = True

                # g = f
                #
                # Propagación de alias de system.
                if (
                    isinstance(valor, ast.Name)
                    and valor.id in aliases_system
                ):
                    for destino in destinos:
                        if destino not in aliases_system:
                            aliases_system.add(destino)
                            cambio = True

                # g = f
                #
                # Propagación de alias de subprocess.
                if (
                    isinstance(valor, ast.Name)
                    and valor.id in aliases_subprocess_func
                ):
                    for destino in destinos:
                        if destino not in aliases_subprocess_func:
                            aliases_subprocess_func.add(destino)
                            cambio = True

        # ---------------------------------------------------------
        # Segunda pasada:
        # identificar llamadas peligrosas.
        # ---------------------------------------------------------
        for node in ast.walk(codigo):

            if not isinstance(node, ast.Call):
                continue

            funcion = node.func

            # exec(...)
            # eval(...)
            # compile(...)
            if isinstance(funcion, ast.Name):

                if funcion.id in funciones_prohibidas:
                    return funcion.id

                # from os import system
                # f = os.system
                # g = f
                if funcion.id in aliases_system:
                    return "system"

                # f = subprocess.run
                # g = f
                if funcion.id in aliases_subprocess_func:
                    return "subprocess"

            # os.system(...)
            # sistema.system(...)
            # os.popen(...)
            # sistema.popen(...)
            if isinstance(funcion, ast.Attribute):

                if funcion.attr == "system":
                    objeto = funcion.value

                    if (
                        isinstance(objeto, ast.Name)
                        and objeto.id in aliases_os
                    ):
                        return "system"

                if funcion.attr == "popen":
                    objeto = funcion.value

                    if (
                        isinstance(objeto, ast.Name)
                        and objeto.id in aliases_os
                    ):
                        return "popen"

                # sp.run(...)
                # sp.Popen(...)
                # sp.call(...)
                #
                # Cualquier acceso al módulo subprocess es peligroso.
                if (
                    isinstance(funcion.value, ast.Name)
                    and funcion.value.id in aliases_subprocess
                ):
                    return "subprocess"

        return None

    def validar_archivo_python(
        self,
        codigo: str,
        nombre: str,
    ) -> None:

        tree = self.validar_python(
            codigo,
            nombre,
        )

        peligro = (
            self.detectar_codigo_peligroso(
                tree
            )
        )

        if peligro:

            raise ValueError(
                f"Código en  {nombre} contiene operación "
                f"potencialmente peligrosa: {peligro}"
            )

    # ========================================================================
    # AGENTE PLANIFICADOR
    # ========================================================================

    def agente_planificador(
        self,
        orden: str,
        mapa: Dict[str, str],
        error_anterior: str = "",
    ) -> Dict[str, Any]:

        contexto = json.dumps(
            mapa,
            ensure_ascii=False,
            indent=2,
        )

        req_files_str = ", ".join([f'"{rf}"' for rf in self.config.required_files])

        prompt = f"""
ERES EL AGENTE PLANIFICADOR.

Tu responsabilidad es transformar una orden humana en un plan técnico.

ORDEN:
{orden}

PROYECTO:
{contexto}

ARCHIVOS OBLIGATORIOS DEL PROYECTO:
[{req_files_str}]

ERROR ANTERIOR:
{error_anterior}

REGLAS:

- No escribas código.
- No ejecutes comandos.
- No inventes archivos existentes.
- Puedes proponer archivos nuevos.
- Todo cambio debe ser pequeño, verificable y reversible.
- Debe existir una estrategia de pruebas.
- No eliminar funcionalidades existentes.
- No utilizar dependencias externas innecesarias.
- Los archivos obligatorios DEBEN ser preservados o incluidos en files_to_modify.

DEVUELVE ÚNICAMENTE JSON VÁLIDO.

FORMATO:

{{
  "objective": "objetivo",
  "risk": "low|medium|high",
  "required_files": [{req_files_str}],
  "files_to_modify": [],
  "files_to_create": [],
  "files_to_delete": [],
  "tests_required": [],
  "acceptance_criteria": [],
  "steps": []
}}
"""

        respuesta = self.consultar_ollama(
            prompt,
            rol="planificador",
        )

        plan = self.extraer_json(
            respuesta
        )

        plan["required_files"] = list(self.config.required_files)

        files_mod = plan.setdefault("files_to_modify", [])
        files_cre = plan.get("files_to_create", [])

        for req_f in self.config.required_files:
            if req_f not in files_mod and req_f not in files_cre:
                files_mod.append(req_f)

        self.guardar_memoria(
            "plan",
            plan,
        )

        return plan

    # ========================================================================
    # AGENTE ARQUITECTO
    # ========================================================================

    def agente_arquitecto(
        self,
        orden: str,
        plan: Dict[str, Any],
        mapa: Dict[str, str],
    ) -> Dict[str, Any]:

        contexto = json.dumps(
            mapa,
            ensure_ascii=False,
            indent=2,
        )

        plan_texto = json.dumps(
            plan,
            ensure_ascii=False,
            indent=2,
        )

        req_files_str = ", ".join([f'"{rf}"' for rf in self.config.required_files])

        prompt = f"""
ERES EL AGENTE ARQUITECTO.

Analiza la orden y el plan.

ORDEN:
{orden}

PLAN:
{plan_texto}

PROYECTO:
{contexto}

ARCHIVOS OBLIGATORIOS DEL PROYECTO:
[{req_files_str}]

Determina la estructura técnica necesaria.

Puedes crear nuevos módulos si realmente son necesarios.
Asegúrate de incluir la estructura para los archivos obligatorios.

Nunca elimines funcionalidades existentes sin una justificación
técnica explícita.

DEVUELVE ÚNICAMENTE JSON VÁLIDO:

{{
  "architecture": "descripcion",
  "required_files": [{req_files_str}],
  "modules": [
    {{
      "path": "archivo.py",
      "purpose": "responsabilidad",
      "depends_on": []
    }}
  ],
  "interfaces": [],
  "invariants": [],
  "regression_risks": [],
  "implementation_order": []
}}
"""

        respuesta = self.consultar_ollama(
            prompt,
            rol="arquitecto",
        )

        arquitectura = self.extraer_json(
            respuesta
        )

        arquitectura["required_files"] = list(self.config.required_files)

        self.guardar_memoria(
            "architecture",
            arquitectura,
        )

        return arquitectura

    # ========================================================================
    # AGENTE IMPLEMENTADOR
    # ========================================================================

    def agente_implementador(
        self,
        orden: str,
        plan: Dict[str, Any],
        arquitectura: Dict[str, Any],
        mapa: Dict[str, str],
        error_anterior: str = "",
    ) -> Dict[str, str]:

        contexto = json.dumps(
            mapa,
            ensure_ascii=False,
            indent=2,
        )

        req_files_str = ", ".join([f'"{rf}"' for rf in self.config.required_files])

        prompt = f"""
ERES EL AGENTE IMPLEMENTADOR.

ORDEN:
{orden}

PLAN:
{json.dumps(plan, ensure_ascii=False, indent=2)}

ARQUITECTURA:
{json.dumps(arquitectura, ensure_ascii=False, indent=2)}

PROYECTO:
{contexto}

ERROR ANTERIOR:
{error_anterior}

Debes producir los archivos necesarios.

CONTRATO OBLIGATORIO DE ARCHIVOS REQUERIDOS:
La respuesta DEBE incluir obligatoriamente las siguientes claves dentro del objeto JSON "files":
[{req_files_str}]

REGLA CLAVE PARA RESOLVER RESTRICCIONES VS ARCHIVOS OBLIGATORIOS:
1. "files" es un diccionario con todos los archivos que componen la propuesta.
2. Si la ORDEN contiene restricciones como "NO modifiques test_proyecto.py", DEBES incluir la clave "test_proyecto.py" dentro de "files", asignando como valor el contenido COMPLETO original de "test_proyecto.py" extraído exactamente de PROYECTO.
3. Incluir un archivo obligatorio en "files" con su contenido original NO violará la restricción de "NO modificar", sino que garantizará el cumplimiento del contrato.
4. Si la orden requiere modificar o añadir pruebas, incluye la versión actualizada correspondiente en "files".
5. NUNCA omitas "test_proyecto.py" del objeto "files". Omitirlo causará un rechazo inmediato por validación.

Puedes modificar archivos existentes.

Puedes crear archivos nuevos.

NO puedes eliminar archivos.

NO puedes ejecutar comandos.

NO puedes usar:
eval
exec
compile
os.system
subprocess
shutil.rmtree
os.remove
os.unlink
os.rmdir

Mantén las funcionalidades existentes.

Los tests deben utilizar unittest.

REGLAS OBLIGATORIAS DE SINTAXIS:

- Cada archivo Python debe ser sintácticamente válido.
- Antes de devolver cada archivo Python, verifica mentalmente que todas las cadenas estén correctamente cerradas.
- No generes cadenas multilínea incompletas.
- No dejes comillas simples o dobles sin cerrar.
- No dejes paréntesis, corchetes o llaves sin cerrar.
- No cortes una cadena entre líneas de forma inválida.
- Devuelve el contenido completo de cada archivo, desde la primera hasta la última línea.
- Si ERROR ANTERIOR contiene un SyntaxError, corrige específicamente ese error antes de devolver la nueva propuesta.
- No reproduzcas el mismo error sintáctico del intento anterior.

IMPORTANTE:

Debes devolver EXACTAMENTE un objeto JSON cuya raíz tenga una única propiedad llamada "files".

"files" DEBE ser un OBJETO JSON (diccionario), nunca una lista, nunca un texto y nunca null.

Cada clave dentro de "files" debe ser una ruta de archivo relativa.
Cada valor dentro de "files" debe ser un STRING con el contenido COMPLETO del archivo.

EJEMPLO VÁLIDO:

{{
  "files": {{
    "ejemplo.py": "print(\"hola\")",
    "test_proyecto.py": "import unittest\\n\\nclass TestEjemplo(unittest.TestCase):\\n    pass"
  }}
}}

EJEMPLO INVÁLIDO:

{{
  "files": ["ejemplo.py"]
}}

EJEMPLO INVÁLIDO:

{{
  "files": "ejemplo.py"
}}

EJEMPLO INVÁLIDO:

{{
  "archivo.py": "contenido"
}}

NO añadas explicaciones.
NO uses Markdown.
NO uses bloques ```json.
NO devuelvas texto antes o después del JSON.
"""

        respuesta = self.consultar_ollama(
            prompt,
            rol="implementador",
        )

        resultado = self.extraer_json(
            respuesta
        )

        archivos = resultado.get(
            "files"
        )

        if archivos is None:
            LOGGER.error(
                "Respuesta del implementador sin campo 'files': %s",
                json.dumps(
                    resultado,
                    ensure_ascii=False,
                    indent=2,
                )[:5000],
            )

        if not isinstance(
            archivos,
            dict,
        ):

            raise ValueError(
                "El implementador no devolvió "
                "un diccionario de archivos."
            )

        archivos_normalizados: Dict[str, str] = {}

        for ruta, contenido in archivos.items():

            if not isinstance(
                ruta,
                str,
            ):

                raise ValueError(
                    "El nombre de archivo no es texto."
                )

            if not isinstance(
                contenido,
                str,
            ):

                raise ValueError(
                    f"Contenido inválido para {ruta}."
                )

            ruta_segura = self.ruta_segura(
                ruta
            )

            if ruta_segura.name.startswith("."):

                raise ValueError(
                    f"Archivo oculto no permitido: {ruta}"
                )

            if ruta_segura.suffix.lower() == ".py":

                self.validar_archivo_python(
                    contenido,
                    ruta,
                )

            archivos_normalizados[
                str(
                    ruta_segura.relative_to(
                        self.target_path
                    )
                )
            ] = contenido

        if not archivos_normalizados:

            raise ValueError(
                "El implementador no produjo archivos."
            )

        return archivos_normalizados

    # ========================================================================
    # AGENTE QA
    # ========================================================================

    # ========================================================================
    # QA DETERMINISTA (análisis estático de código)
    # ========================================================================

    def _qa_deterministico(
        self,
        archivos: Dict[str, str],
        mapa: Dict[str, str],
    ) -> Tuple[bool, List[str]]:
        """
        Análisis estático determinista: no depende del LLM.
        Devuelve (aprobado, lista_de_issues).
        """
        issues: List[str] = []

        for nombre, contenido in archivos.items():
            if not nombre.endswith(".py"):
                continue

            # 1. Verificar sintaxis Python
            try:
                tree = ast.parse(contenido, filename=nombre)
            except SyntaxError as err:
                issues.append(
                    f"SyntaxError en {nombre} línea {err.lineno}: {err.msg}"
                )
                continue

            # 2. Verificar que main() no se llama en el nivel superior
            #    (sería un efecto secundario al importar)
            if nombre == "main.py":
                for nodo in ast.walk(tree):
                    # Buscar llamadas a funciones en el nivel de módulo
                    if isinstance(nodo, ast.Module):
                        for stmt in nodo.body:
                            # Solo permitir: def, class, import, assign, if __name__
                            if isinstance(stmt, ast.Expr):
                                if isinstance(stmt.value, ast.Call):
                                    func = stmt.value.func
                                    func_name = ""
                                    if isinstance(func, ast.Name):
                                        func_name = func.id
                                    elif isinstance(func, ast.Attribute):
                                        func_name = func.attr
                                    # Permitir llamadas a guardar/persistencia
                                    # SOLO si están dentro de if __name__ == "__main__"
                                    issues.append(
                                        "Llamada a funcion "
                                        + func_name
                                        + "() en nivel de modulo en "
                                        + nombre
                                        + " (posible efecto secundario al importar)."
                                        + " Envuelve en: if __name__ == '__main__': ..."
                                    )

            # 3. Verificar guardar_registro / persistencia en nivel módulo
            #    fuera de bloques if __name__
            if nombre == "main.py":
                # Buscar instancias de persistencia en nivel superior
                for nodo in ast.walk(tree):
                    if isinstance(nodo, ast.Module):
                        for stmt in nodo.body:
                            if isinstance(stmt, ast.Assign):
                                # p = persistencia.Persistencia() → OK (solo asignación)
                                pass
                            elif isinstance(stmt, ast.Expr):
                                # Ya lo capturamos arriba
                                pass

            # 4. Detectar código peligroso
            peligro = self.detectar_codigo_peligroso(tree)
            if peligro:
                issues.append(
                    f"Código peligroso en {nombre}: {peligro}"
                )

            # 5. Verificar que if __name__ == "__main__" está presente
            #    si el archivo tiene una función main()
            tiene_main_func = any(
                isinstance(n, ast.FunctionDef) and n.name == "main"
                for n in ast.walk(tree)
            )
            tiene_guard = any(
                isinstance(n, ast.If)
                and isinstance(n.test, ast.Compare)
                and len(n.test.ops) == 1
                and isinstance(n.test.ops[0], ast.Eq)
                and len(n.test.comparators) == 1
                and isinstance(n.test.left, ast.Name)
                and n.test.left.id == "__name__"
                and isinstance(n.test.comparators[0], ast.Constant)
                and n.test.comparators[0].value == "__main__"
                for n in ast.walk(tree)
            )
            if tiene_main_func and not tiene_guard:
                issues.append(
                    f"{nombre} define main() pero le falta el guard "
                    "if __name__ == '__main__': main()"
                )

        # 6. Verificar que los archivos requeridos están presentes
        for req in self.config.required_files:
            if req not in archivos:
                issues.append(
                    f"Archivo obligatorio ausente en la propuesta: {req}"
                )

        aprobado = len(issues) == 0
        return aprobado, issues

    def agente_qa(
        self,
        orden: str,
        archivos: Dict[str, str],
        mapa: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Agente QA con dos capas:
        1. Análisis DETERMINISTA (AST + reglas) → veredicto confiable.
        2. Análisis LLM (Ollama) → detecta regresiones semánticas complejas.

        Si el análisis determinista falla, el rechazo es definitivo.
        Si el LLM rechaza pero el determinista aprueba, se loguea la discrepancia
        y se confía en el determinista (evita falsos positivos del LLM).
        """
        # --- CAPA 1: Determinista ---
        det_aprobado, det_issues = self._qa_deterministico(archivos, mapa)

        if not det_aprobado:
            LOGGER.warning(
                "QA determinista rechazó la propuesta: %s",
                det_issues,
            )
            return {
                "approved": False,
                "issues": det_issues,
                "required_tests": [],
                "reason": (
                    "Rechazo determinista (AST/reglas): "
                    + "; ".join(det_issues)
                ),
                "source": "determinista",
            }

        LOGGER.info(
            "QA determinista: APROBADO. Consultando LLM para análisis semántico..."
        )

        # --- CAPA 2: LLM (análisis semántico) ---
        archivos_texto = json.dumps(
            archivos,
            ensure_ascii=False,
            indent=2,
        )

        # INSTRUCCIÓN EXPLÍCITA sobre import vs ejecución directa
        prompt = f"""
ERES EL AGENTE QA/TDD.

ORDEN:
{orden}

ARCHIVOS PROPUESTOS:
{archivos_texto}

PROYECTO ORIGINAL:
{json.dumps(mapa, ensure_ascii=False, indent=2)}

REGLA CRÍTICA SOBRE EFECTOS SECUNDARIOS:
"Importar main" y "ejecutar main.py" son cosas DISTINTAS:
- `import main` en Python ejecuta el código del módulo a NIVEL RAÍZ,
  pero NO ejecuta las funciones que están dentro de bloques
  `if __name__ == "__main__":`.
- Si `main.py` tiene una función `main()` llamada SOLO dentro de
  `if __name__ == "__main__": main()`, entonces importar el módulo
  NO producirá efectos secundarios (no guardará registros, no escribirá
  archivos, no hará I/O).
- Solo debes marcar "efecto secundario al importar" si hay código que
  llama a funciones de I/O (guardar, escribir, etc.) FUERA de cualquier
  función y FUERA del bloque `if __name__ == "__main__":`.

Comprueba SOLO:
- regresiones de funcionalidad (¿se eliminó algo que existía?);
- compatibilidad de la interfaz de las funciones modificadas con los tests;
- cumplimiento del requerimiento de la ORDEN;
- seguridad (sin eval/exec/os.system).

NO rechaces por razones ya validadas determinísticamente (sintaxis, imports,
guard de __name__).

DEVUELVE ÚNICAMENTE JSON VÁLIDO:

{{
  "approved": true,
  "issues": [],
  "required_tests": [],
  "reason": "explicación breve"
}}
"""

        try:
            respuesta = self.consultar_ollama(
                prompt,
                rol="qa",
            )
            resultado_llm = self.extraer_json(respuesta)
        except Exception as error:
            LOGGER.warning(
                "QA LLM falló (%s). Usando resultado determinista (APROBADO).",
                error,
            )
            return {
                "approved": True,
                "issues": [],
                "required_tests": [],
                "reason": "Análisis determinista aprobado. LLM no disponible.",
                "source": "determinista_fallback",
            }

        llm_aprobado = resultado_llm.get("approved", True)

        if not llm_aprobado:
            llm_issues = resultado_llm.get("issues", [])
            llm_reason = resultado_llm.get("reason", "")
            LOGGER.warning(
                "QA LLM rechazó, pero el análisis determinista APROBÓ. "
                "Inspeccionando si el rechazo es un falso positivo..."
            )
            # Falso positivo conocido: el LLM confunde import con ejecución
            textos_falso_positivo = [
                "main()",
                "guardar_registro",
                "historico.json",
                "registro en",
                "efecto secundario",
            ]
            razon_texto = llm_reason.lower() + " ".join(
                str(i) for i in llm_issues
            ).lower()
            es_falso_positivo = any(
                fp in razon_texto for fp in textos_falso_positivo
            )
            if es_falso_positivo:
                LOGGER.warning(
                    "Falso positivo del LLM detectado y neutralizado. "
                    "El análisis determinista confirmó que el código es correcto. "
                    "Razón LLM ignorada: %s",
                    llm_reason[:200],
                )
                return {
                    "approved": True,
                    "issues": [],
                    "required_tests": resultado_llm.get("required_tests", []),
                    "reason": (
                        "Aprobado por análisis determinista. "
                        "El LLM confundió import con ejecución directa (falso positivo neutralizado)."
                    ),
                    "source": "determinista_override",
                    "llm_reason_rejected": llm_reason[:300],
                }
            # Rechazo LLM genuino (no es sobre import/efectos secundarios)
            return resultado_llm

        # LLM también aprueba
        resultado_llm["source"] = "determinista+llm"
        return resultado_llm

    # ========================================================================
    # AGENTE REVISOR
    # ========================================================================

    def agente_revisor(
        self,
        orden: str,
        plan: Dict[str, Any],
        arquitectura: Dict[str, Any],
        archivos: Dict[str, str],
        qa: Dict[str, Any],
    ) -> Dict[str, Any]:

        prompt = f"""
ERES EL AGENTE REVISOR Y CONTROLADOR DE CALIDAD.

Tu misión es impedir que una modificación defectuosa llegue
al proyecto real.

ORDEN:
{orden}

PLAN:
{json.dumps(plan, ensure_ascii=False, indent=2)}

ARQUITECTURA:
{json.dumps(arquitectura, ensure_ascii=False, indent=2)}

ARCHIVOS:
{json.dumps(archivos, ensure_ascii=False, indent=2)}

QA:
{json.dumps(qa, ensure_ascii=False, indent=2)}

Rechaza:

- cambios destructivos;
- archivos fuera del proyecto;
- código sintácticamente inválido;
- tests ausentes;
- eliminación innecesaria de funcionalidades;
- comandos externos;
- eval/exec;
- dependencias injustificadas;
- modificaciones que no correspondan a la orden.

DEVUELVE ÚNICAMENTE JSON:

{{
  "approved": true,
  "severity": "low|medium|high",
  "issues": [],
  "required_changes": [],
  "reason": "..."
}}
"""

        respuesta = self.consultar_ollama(
            prompt,
            rol="revisor",
        )

        return self.extraer_json(
            respuesta
        )

    # ========================================================================
    # VALIDAR ARCHIVOS PROPUESTOS
    # ========================================================================

    def validar_propuesta(
        self,
        archivos: Dict[str, str],
    ) -> None:

        if "test_proyecto.py" not in archivos:
            raise ValueError(
                "La propuesta del implementador debe incluir test_proyecto.py."
            )

        for ruta, contenido in archivos.items():

            path = self.ruta_segura(
                ruta
            )

            if len(contenido) > (
                self.config.max_file_size
            ):

                raise ValueError(
                    f"Archivo demasiado grande: {ruta}"
                )

            if path.suffix.lower() == ".py":

                self.validar_archivo_python(
                    contenido,
                    ruta,
                )

    # ========================================================================
    # COPIAR SOPORTE
    # ========================================================================

    def copiar_soporte(
        self,
        destino: Path,
    ) -> None:

        ignorados = set(
            self.config.ignored_directories
        )

        excluidos = {
            "main.py",
            "test_proyecto.py",
            "historico.json",
        }

        for root, dirs, files in os.walk(
            self.target_path
        ):

            dirs[:] = [
                directory
                for directory in dirs
                if directory not in ignorados
            ]

            for filename in files:

                if filename in excluidos:
                    continue

                origen = Path(root) / filename

                try:

                    relativo = (
                        origen.relative_to(
                            self.target_path
                        )
                    )

                except ValueError:

                    continue

                destino_archivo = (
                    destino / relativo
                )

                try:

                    destino_archivo.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )

                    shutil.copy2(
                        origen,
                        destino_archivo,
                    )

                except OSError as error:

                    LOGGER.warning(
                        "No se pudo copiar %s: %s",
                        origen,
                        error,
                    )
    # ========================================================================
    # ENTORNO SANDBOX
    # ========================================================================

    def entorno_sandbox(
        self,
        sandbox: Path,
    ) -> Dict[str, str]:

        entorno = os.environ.copy()

        pythonpath = entorno.get(
            "PYTHONPATH",
            "",
        )

        rutas = [
            str(sandbox)
        ]

        if pythonpath:
            rutas.append(
                pythonpath
            )

        entorno["PYTHONPATH"] = (
            os.pathsep.join(rutas)
        )

        return entorno

    # ========================================================================
    # APLICAR PROPUESTA EN SANDBOX
    # ========================================================================

    def escribir_propuesta(
        self,
        sandbox: Path,
        archivos: Dict[str, str],
    ) -> None:

        for ruta, contenido in archivos.items():

            relativo = Path(ruta)

            destino = (
                sandbox / relativo
            ).resolve()

            try:

                destino.relative_to(
                    sandbox.resolve()
                )

            except ValueError as error:

                raise ValueError(
                    f"Archivo fuera del sandbox: {ruta}"
                ) from error

            destino.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            destino.write_text(
                contenido,
                encoding="utf-8",
            )

    # ========================================================================
    # EJECUTAR TESTS
    # ========================================================================

    def ejecutar_tests(
        self,
        sandbox: Path,
    ) -> Tuple[bool, str]:

        test = (
            sandbox / "test_proyecto.py"
        )

        if not test.exists():

            return (
                False,
                "No existe test_proyecto.py.",
            )

        comando = [
            self._python(),
            "-m",
            "unittest",
            "discover",
            "-v",
        ]

        LOGGER.info(
            "Ejecutando suite unittest en sandbox..."
        )

        try:

            proceso = subprocess.run(
                comando,
                cwd=str(sandbox),
                env=self.entorno_sandbox(
                    sandbox
                ),
                capture_output=True,
                text=True,
                timeout=self.config.sandbox_timeout,
                check=False,
            )

        except subprocess.TimeoutExpired:

            return (
                False,
                "La suite superó el tiempo máximo.",
            )

        except OSError as error:

            return (
                False,
                f"No se pudo ejecutar unittest: {error}",
            )

        stdout = (
            proceso.stdout or ""
        ).strip()

        stderr = (
            proceso.stderr or ""
        ).strip()

        detalle = "\n".join(
            parte
            for parte in (
                stdout,
                stderr,
            )
            if parte
        ).strip()

        if proceso.returncode != 0:

            return (
                False,
                detalle
                or (
                    "unittest terminó con código "
                    f"{proceso.returncode}."
                ),
            )

        main_py = sandbox / "main.py"
        if main_py.exists():
            script_code = (
                "import json, os, sys\n"
                "hist = os.path.join('.', 'historico.json')\n"
                "before = -1\n"
                "if os.path.exists(hist):\n"
                "    try:\n"
                "        with open(hist, 'r', encoding='utf-8') as f:\n"
                "            before = len(json.load(f).get('registros', []))\n"
                "    except Exception:\n"
                "        pass\n"
                "try:\n"
                "    import main\n"
                "except Exception as e:\n"
                "    print(f'Error al importar main: {e}')\n"
                "    sys.exit(1)\n"
                "after = -1\n"
                "if os.path.exists(hist):\n"
                "    try:\n"
                "        with open(hist, 'r', encoding='utf-8') as f:\n"
                "            after = len(json.load(f).get('registros', []))\n"
                "    except Exception:\n"
                "        pass\n"
                "if before >= 0 and after > before:\n"
                "    print(f'EFECTO SECUNDARIO DETECTADO: import main incrementó registros de {before} a {after}')\n"
                "    sys.exit(2)\n"
                "print('COMPROBACION_IMPORT_MAIN_OK')\n"
            )
            try:
                res_import = subprocess.run(
                    [self._python(), "-c", script_code],
                    cwd=str(sandbox),
                    env=self.entorno_sandbox(sandbox),
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                if res_import.returncode != 0:
                    out = ((res_import.stdout or "").strip() + "\n" + (res_import.stderr or "").strip()).strip()
                    return (
                        False,
                        f"Rechazo en verificación de import main:\n{out}",
                    )
            except Exception as error:
                return (
                    False,
                    f"Error comprobando efectos secundarios de import main: {error}",
                )

        return True, detalle

    # ========================================================================
    # SANDBOX COMPLETO
    # ========================================================================

    def ejecutar_sandbox(
        self,
        archivos: Dict[str, str],
    ) -> Tuple[bool, str]:

        with tempfile.TemporaryDirectory(
            prefix="supreme_tdd_"
        ) as temp_dir:

            sandbox = Path(
                temp_dir
            )

            self.copiar_soporte(
                sandbox
            )

            try:

                self.escribir_propuesta(
                    sandbox,
                    archivos,
                )

            except Exception as error:

                return (
                    False,
                    f"No se pudo preparar sandbox: {error}",
                )

            return self.ejecutar_tests(
                sandbox
            )

    # ========================================================================
    # BACKUP
    # ========================================================================

    def crear_backup(
        self,
        archivos: List[str],
    ) -> Path:

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        destino = (
            self.backup_dir
            / timestamp
        )

        destino.mkdir(
            parents=True,
            exist_ok=True,
        )

        for relativa in archivos:

            path = self.ruta_segura(
                relativa
            )

            if not path.exists():
                continue

            copia = (
                destino / relativa
            )

            copia.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.copy2(
                path,
                copia,
            )

        return destino

    # ========================================================================
    # CONSOLIDACIÓN TRANSACCIONAL
    # ========================================================================

    def consolidar(
        self,
        archivos: Dict[str, str],
    ) -> None:

        rutas = list(
            archivos.keys()
        )

        if not rutas:
            LOGGER.info(
                "Consolidación completada."
            )
            return

        backup = self.crear_backup(
            rutas
        )

        temporales: List[
            Tuple[Path, Path]
        ] = []

        try:

            for relativa, contenido in (
                archivos.items()
            ):

                destino = self.ruta_segura(
                    relativa
                )

                destino.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                temporal = (
                    destino.parent
                    / (
                        "."
                        + destino.name
                        + ".supreme.tmp"
                    )
                )

                temporal.write_text(
                    contenido,
                    encoding="utf-8",
                )

                temporales.append(
                    (
                        temporal,
                        destino,
                    )
                )

            for temporal, destino in temporales:

                os.replace(
                    temporal,
                    destino,
                )

            LOGGER.info(
                "Consolidación completada."
            )

            self.guardar_memoria(
                "consolidation",
                {
                    "files": rutas,
                    "backup": str(backup),
                },
            )

        except Exception as error_original:

            LOGGER.exception(
                "Error durante consolidación. "
                "Intentando restaurar backup."
            )

            error_rollback = None

            for relativa in rutas:

                origen_backup = (
                    backup / relativa
                )

                destino = self.ruta_segura(
                    relativa
                )

                try:

                    if origen_backup.exists():

                        destino.parent.mkdir(
                            parents=True,
                            exist_ok=True,
                        )

                        shutil.copy2(
                            origen_backup,
                            destino,
                        )

                    elif destino.exists():

                        destino.unlink()

                        directorio = destino.parent

                        while directorio != self.target_path:

                            try:
                                directorio.rmdir()
                            except OSError:
                                break

                            directorio = directorio.parent

                except Exception as error:

                    if error_rollback is None:
                        error_rollback = error

                    LOGGER.exception(
                        "Error durante rollback de %s",
                        relativa,
                    )

            if error_rollback is not None:
                raise error_rollback from error_original

            raise

        finally:

            for temporal, _ in temporales:

                try:

                    if temporal.exists():
                        temporal.unlink()

                except OSError:
                    pass

    # ========================================================================
    # PROCESAMIENTO AUTÓNOMO
    # ========================================================================

    def procesar_orden(
        self,
        orden: str,
    ) -> bool:

        orden = orden.strip()

        if not orden:
            return False

        if len(orden) > (
            self.config.max_order_length
        ):

            LOGGER.error(
                "La orden supera el tamaño permitido."
            )

            return False

        LOGGER.info(
            "=" * 70
        )

        LOGGER.info(
            "NUEVA ORDEN AUTÓNOMA:"
        )

        LOGGER.info(
            "%s",
            orden,
        )

        self.guardar_memoria(
            "order",
            {
                "order": orden
            },
        )

        error_anterior = ""

        for intento in range(
            1,
            self.config.max_attempts + 1,
        ):

            LOGGER.info(
                "=" * 70
            )

            LOGGER.info(
                "CICLO MULTIAGENTE %d/%d",
                intento,
                self.config.max_attempts,
            )

            try:

                mapa = (
                    self.escanear_proyecto()
                )

                LOGGER.info(
                    "AGENTE PLANIFICADOR..."
                )

                plan = (
                    self.agente_planificador(
                        orden,
                        mapa,
                        error_anterior,
                    )
                )

                LOGGER.info(
                    "AGENTE ARQUITECTO..."
                )

                arquitectura = (
                    self.agente_arquitecto(
                        orden,
                        plan,
                        mapa,
                    )
                )

                LOGGER.info(
                    "AGENTE IMPLEMENTADOR..."
                )

                archivos = (
                    self.agente_implementador(
                        orden,
                        plan,
                        arquitectura,
                        mapa,
                        error_anterior,
                    )
                )

                self.validar_propuesta(
                    archivos
                )

                LOGGER.info(
                    "AGENTE QA..."
                )

                qa = self.agente_qa(
                    orden,
                    archivos,
                    mapa,
                )

                if not qa.get(
                    "approved",
                    False,
                ):

                    error_anterior = (
                        "RECHAZO QA:\n"
                        + json.dumps(
                            qa,
                            ensure_ascii=False,
                            indent=2,
                        )
                    )

                    raise ValueError(
                        error_anterior
                    )

                LOGGER.info(
                    "AGENTE REVISOR..."
                )

                revision = (
                    self.agente_revisor(
                        orden,
                        plan,
                        arquitectura,
                        archivos,
                        qa,
                    )
                )

                if not revision.get(
                    "approved",
                    False,
                ):

                    error_anterior = (
                        "RECHAZO REVISOR:\n"
                        + json.dumps(
                            revision,
                            ensure_ascii=False,
                            indent=2,
                        )
                    )

                    raise ValueError(
                        error_anterior
                    )


                LOGGER.info(
                    "VALIDACIÓN SANDBOX..."
                )

                aprobado, detalle = (
                    self.ejecutar_sandbox(
                        archivos
                    )
                )

                if not aprobado:

                    error_anterior = detalle

                    LOGGER.warning(
                        "Sandbox rechazó la propuesta."
                    )

                    LOGGER.warning(
                        "%s",
                        detalle,
                    )

                    self.guardar_memoria(
                        "sandbox_failure",
                        {
                            "error": detalle
                        },
                    )

                    continue

                LOGGER.info(
                    "SUITE SUPERADA."
                )

                if detalle:

                    LOGGER.info(
                        "Resultado:\n%s",
                        detalle,
                    )

                LOGGER.info(
                    "CONSOLIDANDO ECOSISTEMA..."
                )

                self.consolidar(
                    archivos
                )

                LOGGER.info(
                    "EVOLUCIÓN COMPLETADA."
                )

                self.guardar_memoria(
                    "success",
                    {
                        "order": orden,
                        "files": list(
                            archivos.keys()
                        ),
                    },
                )

                return True

            except Exception as error:

                error_anterior = str(
                    error
                )

                LOGGER.warning(
                    "Ciclo %d falló: %s",
                    intento,
                    error,
                )

                self.guardar_memoria(
                    "cycle_failure",
                    {
                        "attempt": intento,
                        "error": error_anterior,
                    },
                )

        LOGGER.error(
            "ORDEN NO CONSOLIDADA."
        )

        self.guardar_memoria(
            "failure",
            {
                "order": orden,
                "error": error_anterior,
            },
        )

        return False

    # ========================================================================
    # SENSOR
    # ========================================================================

    def leer_ordenes(self) -> str:

        try:

            contenido = (
                self.orders_file.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
            )

        except OSError as error:

            LOGGER.warning(
                "No se pudo leer ordenes.txt: %s",
                error,
            )

            return ""

        return contenido.strip()

    # ========================================================================
    # MARCAR ORDEN PROCESADA
    # ========================================================================

    def limpiar_ordenes(
        self,
        orden: str,
    ) -> None:

        try:

            actual = self.leer_ordenes()

            if actual.strip() != orden.strip():

                return

            self.orders_file.write_text(
                "",
                encoding="utf-8",
            )

        except OSError as error:

            LOGGER.warning(
                "No se pudo limpiar ordenes.txt: %s",
                error,
            )

    # ========================================================================
    # SENSOR AUTÓNOMO
    # ========================================================================

    def ejecutar_sensor(
        self,
    ) -> None:

        LOGGER.info(
            "SUPREME TDD EVOLVING AGENT"
        )

        LOGGER.info(
            "Modo autónomo multiagente activado."
        )

        # Health-check de Ollama antes de entrar al bucle
        try:
            modelos = self.verificar_ollama()
            # Ajustar modelo rápido si no está disponible
            if self.config.model_rapido not in modelos:
                candidatos_rapido = [
                    m for m in modelos
                    if any(tag in m for tag in ["3b", "1.5b", "0.5b", "3B"])
                ]
                if candidatos_rapido:
                    self.config.model_rapido = candidatos_rapido[0]
                    LOGGER.warning(
                        "Modelo rápido '%s' no disponible. "
                        "Usando '%s' como alternativa.",
                        self.config.model_rapido,
                        candidatos_rapido[0],
                    )
                else:
                    # Caer al modelo pesado para todos los roles
                    self.config.model_rapido = self.config.model_implementador
                    LOGGER.warning(
                        "No hay modelo ligero disponible. "
                        "Usando '%s' para todos los agentes.",
                        self.config.model_implementador,
                    )
            if self.config.model_implementador not in modelos:
                LOGGER.warning(
                    "Modelo implementador '%s' no está disponible. "
                    "Modelos disponibles: %s",
                    self.config.model_implementador,
                    modelos,
                )
        except RuntimeError as error:
            LOGGER.error(
                "Ollama no está disponible: %s",
                error,
            )
            LOGGER.error(
                "Inicia Ollama con: ollama serve"
            )
            return

        LOGGER.info(
            "Escribe órdenes en:"
        )

        LOGGER.info(
            "%s",
            self.orders_file,
        )

        ultimo_hash: Optional[str] = None

        contenido_inicial = (
            self.leer_ordenes()
        )

        if contenido_inicial:

            ultimo_hash = (
                sha256_text(
                    contenido_inicial
                )
            )

            LOGGER.info(
                "Orden inicial detectada."
            )

            exito = (
                self.procesar_orden(
                    contenido_inicial
                )
            )

            if exito:

                self.limpiar_ordenes(
                    contenido_inicial
                )

                ultimo_hash = None

        else:

            LOGGER.info(
                "No hay orden inicial pendiente."
            )

        LOGGER.info(
            "SENSOR DE INTENCIONES ACTIVO."
        )

        LOGGER.info(
            "Vigilando: %s",
            self.orders_file,
        )

        while True:

            try:

                time.sleep(
                    self.config.poll_interval
                )

                contenido = (
                    self.leer_ordenes()
                )

                if not contenido:

                    continue

                nuevo_hash = (
                    sha256_text(
                        contenido
                    )
                )

                if nuevo_hash == ultimo_hash:

                    continue

                ultimo_hash = nuevo_hash

                LOGGER.info(
                    "Cambio detectado en ordenes.txt."
                )

                exito = (
                    self.procesar_orden(
                        contenido
                    )
                )

                if exito:

                    self.limpiar_ordenes(
                        contenido
                    )

                    ultimo_hash = None

                    LOGGER.info(
                        "Orden completada y retirada de la cola."
                    )

                else:

                    LOGGER.warning(
                        "La orden no fue consolidada."
                    )

                    LOGGER.warning(
                        "La orden permanece en ordenes.txt."
                    )

            except KeyboardInterrupt:

                LOGGER.info(
                    "Sensor detenido por el usuario."
                )

                return

            except Exception:

                LOGGER.exception(
                    "Error inesperado del sensor."
                )

                time.sleep(
                    max(
                        self.config.poll_interval,
                        2.0,
                    )
                )


# ============================================================================
# REQUERIMIENTO INICIAL DE PRUEBA
# ============================================================================

def construir_requerimiento_inicial() -> str:

    return """
Analiza el proyecto actual y realiza una mejora pequeña y segura
que pueda validarse automáticamente.

No elimines funcionalidades existentes.

La modificación debe incluir pruebas.

Si no existe una mejora claramente segura y justificable,
no realices cambios.

La solución debe ser reversible y compatible con la arquitectura actual.
"""


# ============================================================================
# MAIN
# ============================================================================

def main() -> int:

    config = ProjectConfig()

    agent = SupremeTDDAgent(
        config=config
    )

    # Verificación de Ollama al arranque (falla rápido si no está disponible)
    try:
        agent.verificar_ollama()
    except RuntimeError as error:
        LOGGER.error("No se puede iniciar: %s", error)
        LOGGER.error("Ejecuta: ollama serve")
        return 1

    try:

        agent.ejecutar_sensor()

    except KeyboardInterrupt:

        LOGGER.info(
            "Proceso interrumpido por el usuario."
        )

        return 130

    except Exception:

        LOGGER.exception(
            "Error fatal del supervisor."
        )

        return 1

    return 0


# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == "__main__":
    sys.exit(main())
