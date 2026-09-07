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

    def tearDown(self):
        self.tmp.cleanup()

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
