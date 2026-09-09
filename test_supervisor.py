import tempfile
import unittest
from pathlib import Path

from supervisor import ProjectConfig, SupremeTDDAgent



class TestProjectConfig(unittest.TestCase):

    def test_configuracion_por_defecto(self):
        config = ProjectConfig()

        self.assertEqual(
            config.required_files,
            ["test_proyecto.py"],
        )

        self.assertIn(
            ".py",
            config.allowed_extensions,
        )

        self.assertIn(
            "venv",
            config.ignored_directories,
        )

        self.assertGreater(
            config.max_file_size,
            0,
        )




class TestSupremeTDDAgent(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

        self.target = (
            Path(self.tmp.name) / "proyecto"
        )

        self.orders = (
            Path(self.tmp.name) / "ordenes.txt"
        )

        config = ProjectConfig(
            target_project_path=str(self.target),
            orders_file=str(self.orders),
        )

        self.agent = SupremeTDDAgent(config)

    def test_consolidar_error_restaurar_backup(self):
        main = self.target / "main.py"

        main.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
            "archivo_invalido.txt": "contenido\n",
        }

        original = self.agent.ruta_segura

        def ruta_segura_fallida(relativa):
            if relativa == "archivo_invalido.txt":
                raise RuntimeError(
                    "Error simulado durante consolidación"
                )

            return original(relativa)

        self.agent.ruta_segura = ruta_segura_fallida

        with self.assertRaises(
            RuntimeError
        ):
            self.agent.consolidar(propuesta)

        self.assertEqual(
            main.read_text(encoding="utf-8"),
            "VERSION = 1\n",
        )

    def test_consolidar_error_rollback_archivo_nuevo(self):
        main = self.target / "main.py"
        main.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
            "nuevo.py": "NUEVO = True\n",
            "archivo_invalido.txt": "contenido\n",
        }

        original = self.agent.ruta_segura

        def ruta_segura_fallida(relativa):
            if relativa == "archivo_invalido.txt":
                raise RuntimeError(
                    "Error simulado durante consolidación"
                )

            return original(relativa)

        self.agent.ruta_segura = ruta_segura_fallida

        with self.assertRaises(RuntimeError):
            self.agent.consolidar(propuesta)

        self.assertEqual(
            main.read_text(encoding="utf-8"),
            "VERSION = 1\n",
        )

        self.assertFalse(
            (self.target / "nuevo.py").exists()
        )

    def test_consolidar_rollback_despues_de_replace_parcial(self):
        main = self.target / "main.py"
        main.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
            "nuevo.py": "NUEVO = True\n",
        }

        original_replace = __import__("os").replace
        llamadas = {"count": 0}

        def replace_fallido(origen, destino):
            llamadas["count"] += 1
            if llamadas["count"] == 2:
                raise RuntimeError(
                    "Error simulado después del primer replace"
                )
            return original_replace(origen, destino)

        import os
        original_os_replace = os.replace
        os.replace = replace_fallido

        try:
            with self.assertRaises(RuntimeError):
                self.agent.consolidar(propuesta)
        finally:
            os.replace = original_os_replace

        self.assertEqual(
            main.read_text(encoding="utf-8"),
            "VERSION = 1\n",
        )

        self.assertFalse(
            (self.target / "nuevo.py").exists()
        )

    def test_consolidar_rollback_despues_de_varios_replace(self):
        main = self.target / "main.py"
        config = self.target / "config.py"

        main.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        config.write_text(
            "DEBUG = False\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
            "config.py": "DEBUG = True\n",
            "nuevo.py": "NUEVO = True\n",
        }

        import os

        original_replace = os.replace
        llamadas = {"count": 0}

        def replace_fallido(origen, destino):
            llamadas["count"] += 1

            if llamadas["count"] == 3:
                raise RuntimeError(
                    "Error simulado después de varios replace"
                )

            return original_replace(
                origen,
                destino,
            )

        os.replace = replace_fallido

        try:
            with self.assertRaises(RuntimeError):
                self.agent.consolidar(propuesta)
        finally:
            os.replace = original_replace

        self.assertEqual(
            main.read_text(encoding="utf-8"),
            "VERSION = 1\n",
        )

        self.assertEqual(
            config.read_text(encoding="utf-8"),
            "DEBUG = False\n",
        )

        self.assertFalse(
            (self.target / "nuevo.py").exists()
        )

    def test_consolidar_rollback_elimina_archivos_nuevos_despues_de_replace(self):
        main = self.target / "main.py"
        nuevo = self.target / "nuevo.py"
        tercero = self.target / "tercero.py"

        main.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
            "nuevo.py": "NUEVO = True\n",
            "tercero.py": "TERCERO = True\n",
        }

        import os

        original_replace = os.replace
        llamadas = {"count": 0}

        def replace_fallido(origen, destino):
            llamadas["count"] += 1

            if llamadas["count"] == 3:
                raise RuntimeError(
                    "Error simulado después de crear archivo nuevo"
                )

            return original_replace(
                origen,
                destino,
            )

        os.replace = replace_fallido

        try:
            with self.assertRaises(RuntimeError):
                self.agent.consolidar(propuesta)
        finally:
            os.replace = original_replace

        self.assertEqual(
            main.read_text(encoding="utf-8"),
            "VERSION = 1\n",
        )

        self.assertFalse(
            nuevo.exists()
        )

        self.assertFalse(
            tercero.exists()
        )

    def test_consolidar_varios_archivos(self):
        main = self.target / "main.py"
        config = self.target / "config.py"

        main.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        config.write_text(
            "DEBUG = False\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
            "config.py": "DEBUG = True\n",
        }

        self.agent.consolidar(propuesta)

        self.assertEqual(
            main.read_text(encoding="utf-8"),
            "VERSION = 2\n",
        )

        self.assertEqual(
            config.read_text(encoding="utf-8"),
            "DEBUG = True\n",
        )

    def test_consolidar_error_restaurar_varios_archivos(self):
        main = self.target / "main.py"
        config = self.target / "config.py"

        main.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        config.write_text(
            "DEBUG = False\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
            "config.py": "DEBUG = True\n",
            "archivo_invalido.txt": "contenido\n",
        }

        original = self.agent.ruta_segura

        def ruta_segura_fallida(relativa):
            if relativa == "archivo_invalido.txt":
                raise RuntimeError(
                    "Error simulado durante consolidación"
                )

            return original(relativa)

        self.agent.ruta_segura = ruta_segura_fallida

        with self.assertRaises(
            RuntimeError
        ):
            self.agent.consolidar(propuesta)

        self.assertEqual(
            main.read_text(encoding="utf-8"),
            "VERSION = 1\n",
        )

        self.assertEqual(
            config.read_text(encoding="utf-8"),
            "DEBUG = False\n",
        )


    def test_consolidar_crea_directorios_anidados(self):
        propuesta = {
            "src/modulos/feature.py": (
                "def feature():\n"
                "    return True\n"
            ),
        }

        self.agent.consolidar(propuesta)

        archivo = (
            self.target
            / "src"
            / "modulos"
            / "feature.py"
        )

        self.assertTrue(archivo.exists())

        self.assertEqual(
            archivo.read_text(encoding="utf-8"),
            "def feature():\n"
            "    return True\n",
        )

    def test_consolidar_crea_archivo_nuevo(self):
        archivo = self.target / "nuevo.py"

        self.assertFalse(archivo.exists())

        propuesta = {
            "nuevo.py": "VALOR = 123\n",
        }

        self.agent.consolidar(propuesta)

        self.assertTrue(archivo.exists())

        self.assertEqual(
            archivo.read_text(encoding="utf-8"),
            "VALOR = 123\n",
        )

    def test_consolidar_no_elimina_archivos_no_propuestos(self):
        existente = self.target / "existente.py"

        existente.write_text(
            "NO_CAMBIAR = True\n",
            encoding="utf-8",
        )

        propuesta = {
            "nuevo.py": "NUEVO = True\n",
        }

        self.agent.consolidar(propuesta)

        self.assertTrue(existente.exists())

        self.assertEqual(
            existente.read_text(encoding="utf-8"),
            "NO_CAMBIAR = True\n",
        )

    def test_consolidar_reemplaza_archivo_existente(self):
        archivo = self.target / "main.py"

        archivo.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
        }

        self.agent.consolidar(propuesta)

        self.assertEqual(
            archivo.read_text(encoding="utf-8"),
            "VERSION = 2\n",
        )

    def test_consolidar_no_deja_archivos_temporales(self):
        propuesta = {
            "main.py": "VERSION = 2\n",
            "config.py": "DEBUG = True\n",
        }

        self.agent.consolidar(propuesta)

        temporales = list(
            self.target.rglob("*.supreme.tmp")
        )

        self.assertEqual(
            temporales,
            [],
        )


    def tearDown(self):
        self.tmp.cleanup()

    def test_ejecutar_sandbox_test_fallido_es_rechazado(self):
        archivos = {
            "main.py": (
                "def main():\n"
                "    pass\n\n"
                "if __name__ == '__main__':\n"
                "    main()\n"
            ),
            "test_proyecto.py": (
                "import unittest\n\n"
                "class TestFallo(unittest.TestCase):\n"
                "    def test_falla(self):\n"
                "        self.assertEqual(1, 2)\n"
            ),
        }

        aprobado, detalle = (
            self.agent.ejecutar_sandbox(archivos)
        )

        self.assertIn("FAILED", detalle)
        self.assertFalse(aprobado)
        self.assertIn("FAILED", detalle)


    def test_ejecutar_sandbox_timeout(self):
        archivos = {
            "main.py": (
                "def main():\n"
                "    pass\n\n"
                "if __name__ == '__main__':\n"
                "    main()\n"
            ),
            "test_proyecto.py": (
                "import time\n"
                "import unittest\n\n"
                "class TestTimeout(unittest.TestCase):\n"
                "    def test_timeout(self):\n"
                "        time.sleep(5)\n"
            ),
        }

        self.agent.config.sandbox_timeout = 1

        aprobado, detalle = (
            self.agent.ejecutar_sandbox(archivos)
        )

        self.assertFalse(aprobado)

        self.assertIn(
            "tiempo máximo",
            detalle,
        )


        main = self.target / "main.py"
    def test_consolidar_crea_backup_y_actualiza_archivo(self):
        main = self.target / "main.py"

        main.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
        }

        self.agent.consolidar(propuesta)

        self.assertEqual(
            main.read_text(encoding="utf-8"),
            "VERSION = 2\n",
        )

        backups = list(
            self.agent.backup_dir.iterdir()
        )

        self.assertEqual(
            len(backups),
            1,
        )

        backup_main = (
            backups[0] / "main.py"
        )

        self.assertTrue(
            backup_main.exists()
        )

        self.assertEqual(
            backup_main.read_text(
                encoding="utf-8"
            ),
            "VERSION = 1\n",
        )


    # ================================================================
    # CONFIGURACIÓN / ENTORNO
    # ================================================================

    def test_entorno_se_crea(self):
        self.assertTrue(
            self.target.exists()
        )

        self.assertTrue(
            self.agent.memory_dir.exists()
        )

        self.assertTrue(
            self.agent.backup_dir.exists()
        )

        self.assertTrue(
            self.orders.exists()
        )

    def test_copiar_soporte_excluye_archivos_generados(self):
        self.target.mkdir(parents=True, exist_ok=True)

        (self.target / "main.py").write_text(
            "print('main')",
            encoding="utf-8",
        )

        (self.target / "test_proyecto.py").write_text(
            "print('tests')",
            encoding="utf-8",
        )

        (self.target / "historico.json").write_text(
            '{"registros":[]}',
            encoding="utf-8",
        )

        (self.target / "soporte.txt").write_text(
            "archivo auxiliar",
            encoding="utf-8",
        )

        with tempfile.TemporaryDirectory() as sandbox_dir:
            sandbox = Path(sandbox_dir)

            self.agent.copiar_soporte(sandbox)

            self.assertFalse(
                (sandbox / "main.py").exists()
            )

            self.assertFalse(
                (sandbox / "test_proyecto.py").exists()
            )

            self.assertFalse(
                (sandbox / "historico.json").exists()
            )

            self.assertTrue(
                (sandbox / "soporte.txt").exists()
            )

    def test_python_es_el_interprete_actual(self):
        import sys

        self.assertEqual(
            self.agent._python(),
            sys.executable,
        )

    # ================================================================
    # VALIDACIÓN PYTHON
    # ================================================================

    def test_validar_python_correcto(self):
        codigo = """
def sumar(a, b):
    return a + b
"""

        tree = self.agent.validar_python(
            codigo,
            "ejemplo.py",
        )

        self.assertIsNotNone(tree)

    def test_validar_python_vacio(self):
        with self.assertRaises(ValueError):
            self.agent.validar_python(
                "",
                "vacio.py",
            )

    def test_validar_python_solo_espacios(self):
        with self.assertRaises(ValueError):
            self.agent.validar_python(
                "   \n\t  ",
                "vacio.py",
            )

    def test_validar_python_sintaxis_invalida(self):
        with self.assertRaises(ValueError) as contexto:
            self.agent.validar_python(
                "def funcion(:\n",
                "roto.py",
            )

        self.assertIn(
            "SyntaxError",
            str(contexto.exception),
        )

    # ================================================================
    # SEGURIDAD AST
    # ================================================================

    def test_exec_es_peligroso(self):
        tree = self.agent.validar_python(
            "exec('print(1)')",
            "peligroso.py",
        )

        peligro = (
            self.agent.detectar_codigo_peligroso(
                tree
            )
        )

        self.assertEqual(
            peligro,
            "exec",
        )

    def test_eval_es_peligroso(self):
        tree = self.agent.validar_python(
            "eval('1 + 1')",
            "peligroso.py",
        )

        peligro = (
            self.agent.detectar_codigo_peligroso(
                tree
            )
        )

        self.assertEqual(
            peligro,
            "eval",
        )

    def test_compile_es_peligroso(self):
        tree = self.agent.validar_python(
            "compile('x = 1', '', 'exec')",
            "peligroso.py",
        )

        peligro = (
            self.agent.detectar_codigo_peligroso(
                tree
            )
        )

        self.assertEqual(
            peligro,
            "compile",
        )

    def test_import_subprocess_es_peligroso(self):
        tree = self.agent.validar_python(
            "import subprocess",
            "peligroso.py",
        )

        peligro = (
            self.agent.detectar_codigo_peligroso(
                tree
            )
        )

        self.assertEqual(
            peligro,
            "subprocess",
        )

    def test_from_subprocess_es_peligroso(self):
        tree = self.agent.validar_python(
            "from subprocess import run",
            "peligroso.py",
        )

        peligro = (
            self.agent.detectar_codigo_peligroso(
                tree
            )
        )

        self.assertEqual(
            peligro,
            "subprocess",
        )

    def test_codigo_peligroso_con_import_os(self):
        tree = self.agent.validar_python(
            "import os\nos.system('echo peligroso')",
            "peligroso.py",
        )

        peligro = (
            self.agent.detectar_codigo_peligroso(
                tree
            )
        )

        self.assertEqual(
            peligro,
            "system",
        )


    def test_codigo_peligroso_con_import_subprocess_alias(self):
        tree = self.agent.validar_python(
            "import subprocess as sp\nsp.run(['echo', 'peligroso'])",
            "peligroso.py",
        )

        peligro = (
            self.agent.detectar_codigo_peligroso(
                tree
            )
        )

        self.assertEqual(
            peligro,
            "subprocess",
        )

    def test_codigo_peligroso_con_subprocess_run(self):
        tree = self.agent.validar_python(
            "import subprocess\nsubprocess.run(['echo', 'peligroso'])",
            "peligroso.py",
        )

        peligro = (
            self.agent.detectar_codigo_peligroso(
                tree
            )
        )

        self.assertEqual(
            peligro,
            "subprocess",
        )

    def test_codigo_peligroso_con_subprocess_run(self):
        tree = self.agent.validar_python(
            "import subprocess\nsubprocess.run(['echo', 'peligroso'])",
            "peligroso.py",
        )

        peligro = (
            self.agent.detectar_codigo_peligroso(
                tree
            )
        )

        self.assertEqual(
            peligro,
            "subprocess",
        )

    def test_codigo_peligroso_con_subprocess_popen(self):
        tree = self.agent.validar_python(
            "import subprocess\nsubprocess.Popen(['echo', 'peligroso'])",
            "peligroso.py",
        )

        peligro = (
            self.agent.detectar_codigo_peligroso(
                tree
            )
        )

        self.assertEqual(
            peligro,
            "subprocess",
        )

    def test_codigo_peligroso_con_os_popen(self):
        tree = self.agent.validar_python(
            "import os\nos.popen('echo peligroso')",
            "peligroso.py",
        )

        peligro = (
            self.agent.detectar_codigo_peligroso(
                tree
            )
        )

        self.assertEqual(
            peligro,
            "popen",
        )


    def test_os_system_es_peligroso(self):
        tree = self.agent.validar_python(
            "import os\nos.system('ls')",
            "peligroso.py",
        )

        peligro = (
            self.agent.detectar_codigo_peligroso(
                tree
            )
        )

        self.assertEqual(
            peligro,
            "system",
        )

    def test_codigo_normal_no_es_peligroso(self):
        tree = self.agent.validar_python(
            """
def sumar(a, b):
    return a + b

resultado = sumar(2, 3)
""",
            "normal.py",
        )

        peligro = (
            self.agent.detectar_codigo_peligroso(
                tree
            )
        )

        self.assertIsNone(
            peligro
        )

    # ================================================================
    # VALIDAR ARCHIVO PYTHON
    # ================================================================

    def test_validar_archivo_python_correcto(self):
        codigo = """

def main():
    return 42
"""

        resultado = (
            self.agent.validar_archivo_python(
                codigo,
                "main.py",
            )
        )

        self.assertIsNone(
            resultado
        )

    def test_validar_archivo_python_peligroso(self):
        codigo = """

def main():
    exec("print(1)")
"""

        with self.assertRaises(ValueError) as contexto:
            self.agent.validar_archivo_python(
                codigo,
                "main.py",
            )

        self.assertIn(
            "Código",
            str(contexto.exception),
        )

    # ================================================================
    # QA DETERMINÍSTICO
    # ================================================================

    def test_main_con_guard_es_aceptado(self):
        archivos = {
            "main.py": (
                "def main():\n"
                "    print('hola')\n\n"
                "if __name__ == '__main__':\n"
                "    main()\n"
            ),
            "test_proyecto.py": (
                "def test_ok():\n"
                "    assert True\n"
            ),
        }

        aprobado, issues = (
            self.agent._qa_deterministico(
                archivos,
                {},
            )
        )

        self.assertTrue(
            aprobado,
            issues,
        )

        self.assertEqual(
            issues,
            [],
        )

    def test_main_sin_guard_es_rechazado(self):
        archivos = {
            "main.py": (
                "def main():\n"
                "    print('hola')\n"
            ),
            "test_proyecto.py": (
                "def test_ok():\n"
                "    assert True\n"
            ),
        }

        aprobado, issues = (
            self.agent._qa_deterministico(
                archivos,
                {},
            )
        )

        self.assertFalse(
            aprobado
        )

        self.assertTrue(
            any(
                "le falta el guard" in issue
                for issue in issues
            )
        )

    def test_archivo_obligatorio_ausente(self):
        archivos = {
            "main.py": (
                "print('hola')\n"
            ),
        }

        aprobado, issues = (
            self.agent._qa_deterministico(
                archivos,
                {},
            )
        )

        self.assertFalse(
            aprobado
        )

        self.assertTrue(
            any(
                "test_proyecto.py" in issue
                for issue in issues
            )
        )

    def test_sintaxis_invalida(self):
        archivos = {
            "main.py": (
                "def main(\n"
            ),
            "test_proyecto.py": (
                "def test_ok():\n"
                "    assert True\n"
            ),
        }

        aprobado, issues = (
            self.agent._qa_deterministico(
                archivos,
                {},
            )
        )

        self.assertFalse(
            aprobado
        )

        self.assertTrue(
            any(
                "SyntaxError" in issue
                for issue in issues
            )
        )

    def test_codigo_peligroso(self):
        archivos = {
            "main.py": (
                "def main():\n"
                "    exec('print(1)')\n\n"
                "if __name__ == '__main__':\n"
                "    main()\n"
            ),
            "test_proyecto.py": (
                "def test_ok():\n"
                "    assert True\n"
            ),
        }

        aprobado, issues = (
            self.agent._qa_deterministico(
                archivos,
                {},
            )
        )

        self.assertFalse(
            aprobado
        )

        self.assertTrue(
            any(
                "Código peligroso" in issue
                for issue in issues
            )
        )

    def test_falso_guard_no_debe_ser_aceptado(self):
        archivos = {
            "main.py": (
                "def main():\n"
                "    print('hola')\n\n"
                "nombre = 'otra_cosa'\n"
                "if nombre == '__main__':\n"
                "    pass\n"
            ),
            "test_proyecto.py": (
                "def test_ok():\n"
                "    assert True\n"
            ),
        }

        aprobado, issues = (
            self.agent._qa_deterministico(
                archivos,
                {},
            )
        )

        self.assertFalse(
            aprobado
        )

        self.assertTrue(
            any(
                "le falta el guard" in issue
                for issue in issues
            )
        )

    # ================================================================
    # VALIDACIÓN DE PROPUESTA
    # ================================================================

    def test_propuesta_sin_tests_es_rechazada(self):
        archivos = {
            "main.py": (
                "print('hola')\n"
            ),
        }

        with self.assertRaises(ValueError) as contexto:
            self.agent.validar_propuesta(
                archivos
            )

        self.assertIn(
            "test_proyecto.py",
            str(contexto.exception),
        )

    def test_propuesta_valida(self):
        archivos = {
            "main.py": (
                "def main():\n"
                "    print('hola')\n"
            ),
            "test_proyecto.py": (
                "def test_ok():\n"
                "    assert True\n"
            ),
        }

        resultado = (
            self.agent.validar_propuesta(
                archivos
            )
        )

        self.assertIsNone(
            resultado
        )

    def test_propuesta_con_python_peligroso_es_rechazada(self):
        archivos = {
            "main.py": (
                "def main():\n"
                "    exec('print(1)')\n"
            ),
            "test_proyecto.py": (
                "def test_ok():\n"
                "    assert True\n"
            ),
        }

        with self.assertRaises(ValueError):
            self.agent.validar_propuesta(
                archivos
            )

    def test_ejecutar_sandbox_propuesta_valida(self):
        archivos = {
            "main.py": (
                "def main():\n"
                "    return 42\n"
            ),
            "test_proyecto.py": (
                "import unittest\n"
                "import main\n"
                "\n"
                "class TestMain(unittest.TestCase):\n"
                "    def test_main(self):\n"
                "        self.assertEqual(main.main(), 42)\n"
            ),
        }

        resultado, detalle = (
            self.agent.ejecutar_sandbox(
                archivos
            )
        )

        self.assertTrue(
            resultado,
            detalle,
        )

    # ================================================================
    # SELECCIÓN DE MODELOS
    # ================================================================

    def test_modelo_planificador(self):
        modelo, timeout = (
            self.agent._modelo_y_timeout(
                "planificador"
            )
        )

        self.assertEqual(
            modelo,
            self.agent.config.model_rapido,
        )

        self.assertEqual(
            timeout,
            self.agent.config.timeout_planificador,
        )

    def test_modelo_arquitecto(self):
        modelo, timeout = (
            self.agent._modelo_y_timeout(
                "arquitecto"
            )
        )

        self.assertEqual(
            modelo,
            self.agent.config.model_rapido,
        )

        self.assertEqual(
            timeout,
            self.agent.config.timeout_arquitecto,
        )

    def test_modelo_qa(self):
        modelo, timeout = (
            self.agent._modelo_y_timeout(
                "qa"
            )
        )

        self.assertEqual(
            modelo,
            self.agent.config.model_rapido,
        )

        self.assertEqual(
            timeout,
            self.agent.config.timeout_qa,
        )

    def test_modelo_revisor(self):
        modelo, timeout = (
            self.agent._modelo_y_timeout(
                "revisor"
            )
        )

        self.assertEqual(
            modelo,
            self.agent.config.model_rapido,
        )

        self.assertEqual(
            timeout,
            self.agent.config.timeout_revisor,
        )

    def test_modelo_implementador(self):
        modelo, timeout = (
            self.agent._modelo_y_timeout(
                "implementador"
            )
        )

        self.assertEqual(
            modelo,
            self.agent.config.model_implementador,
        )

        self.assertEqual(
            timeout,
            self.agent.config.timeout_implementador,
        )

    def test_modelo_generico(self):
        modelo, timeout = (
            self.agent._modelo_y_timeout(
                "generico"
            )
        )

        self.assertEqual(
            modelo,
            self.agent.config.model_name,
        )

        self.assertEqual(
            timeout,
            self.agent.config.ollama_timeout,
        )

    # ================================================================
    # ESCANEO
    # ================================================================

    def test_escanear_proyecto_encuentra_python(self):
        archivo = (
            self.target / "main.py"
        )

        archivo.write_text(
            "print('hola')\n",
            encoding="utf-8",
        )

        archivos = (
            self.agent.escanear_proyecto()
        )

        self.assertIn(
            "main.py",
            archivos,
        )

        self.assertEqual(
            archivos["main.py"],
            "print('hola')\n",
        )

    def test_escanear_proyecto_ignora_venv(self):
        venv_dir = (
            self.target / "venv"
        )

        venv_dir.mkdir()

        archivo = (
            venv_dir / "oculto.py"
        )

        archivo.write_text(
            "print('no')\n",
            encoding="utf-8",
        )

        archivos = (
            self.agent.escanear_proyecto()
        )

        self.assertNotIn(
            "venv/oculto.py",
            archivos,
        )

    # ================================================================
    # MEMORIA
    # ================================================================

    def test_guardar_memoria(self):
        self.agent.guardar_memoria(
            "test",
            {"valor": 123},
        )

        self.assertTrue(
            self.agent.history_file.exists()
        )

        contenido = (
            self.agent.history_file.read_text(
                encoding="utf-8"
            )
        )

        self.assertIn(
            '"tipo": "test"',
            contenido,
        )

        self.assertIn(
            '"valor": 123',
            contenido,
        )

if __name__ == "__main__":
    unittest.main()
