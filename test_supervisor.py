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

    def test_ruta_segura_rechaza_traversal_fuera_del_proyecto(self):
        with self.assertRaises(ValueError) as contexto:
            self.agent.ruta_segura("../fuera.py")

        self.assertIn(
            "Ruta fuera del proyecto",
            str(contexto.exception),
        )


    def test_ruta_segura_rechaza_ruta_absoluta_fuera_del_proyecto(self):
        fuera = (
            Path(self.tmp.name)
            / "fuera.py"
        )

        with self.assertRaises(ValueError) as contexto:
            self.agent.ruta_segura(str(fuera))

        self.assertIn(
            "Ruta fuera del proyecto",
            str(contexto.exception),
        )


    def test_ruta_segura_rechaza_archivo_oculto(self):
        with self.assertRaises(ValueError) as contexto:
            self.agent.ruta_segura(".secreto.py")

        self.assertIn(
            "No se permite modificar archivos ocultos",
            str(contexto.exception),
        )


    def test_ruta_segura_acepta_ruta_normal(self):
        resultado = self.agent.ruta_segura("src/main.py")

        self.assertEqual(
            resultado,
            (self.target / "src" / "main.py").resolve(),
        )


    def test_ruta_segura_acepta_ruta_normalizada_interna(self):
        resultado = self.agent.ruta_segura(
            "src/../main.py"
        )

        self.assertEqual(
            resultado,
            (self.target / "main.py").resolve(),
        )


    def test_ruta_segura_rechaza_prefijo_parecido_al_proyecto(self):
        fuera = (
            self.target.parent
            / (self.target.name + "_otro")
            / "archivo.py"
        )

        with self.assertRaises(ValueError) as contexto:
            self.agent.ruta_segura(str(fuera))

        self.assertIn(
            "Ruta fuera del proyecto",
            str(contexto.exception),
        )



    def test_ruta_segura_rechaza_ruta_vacia(self):
        with self.assertRaises(ValueError) as contexto:
            self.agent.ruta_segura("   ")

        self.assertIn(
            "Ruta vacía",
            str(contexto.exception),
        )


    def test_ruta_segura_rechaza_tipo_invalido(self):
        with self.assertRaises(ValueError) as contexto:
            self.agent.ruta_segura(None)

        self.assertIn(
            "La ruta debe ser texto",
            str(contexto.exception),
        )



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

        config = self.target / "config.py"

        config.write_text(
            "DEBUG = False\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
            "config.py": "DEBUG = True\n",
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

    def test_consolidar_falla_si_rollback_no_puede_restaurar(self):
        main = self.target / "main.py"

        main.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
            "nuevo.py": "NUEVO = True\n",
        }

        import os
        import shutil

        original_replace = os.replace
        original_copy2 = shutil.copy2

        llamadas_replace = {"count": 0}
        llamadas_copy2 = {"count": 0}

        def replace_fallido(origen, destino):
            llamadas_replace["count"] += 1

            if llamadas_replace["count"] == 2:
                raise RuntimeError(
                    "Error simulado durante consolidación"
                )

            return original_replace(
                origen,
                destino,
            )

        def copy2_fallido(origen, destino):
            llamadas_copy2["count"] += 1

            raise OSError(
                "Error simulado durante rollback"
            )

        os.replace = replace_fallido
        shutil.copy2 = copy2_fallido

        try:
            with self.assertRaises(OSError):
                self.agent.consolidar(propuesta)
        finally:
            os.replace = original_replace
            shutil.copy2 = original_copy2

    def test_consolidar_rollback_limpia_temporales_si_falla_primer_replace(self):
        main = self.target / "main.py"
        nuevo = self.target / "nuevo.py"

        main.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
            "nuevo.py": "NUEVO = True\n",
        }

        import os

        original_replace = os.replace

        def replace_fallido(origen, destino):
            raise RuntimeError(
                "Error simulado en primer replace"
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
            (
                self.target / ".main.py.supreme.tmp"
            ).exists()
        )

        self.assertFalse(
            (
                self.target / ".nuevo.py.supreme.tmp"
            ).exists()
        )


    def test_consolidar_rollback_elimina_archivo_nuevo_anidado(self):
        main = self.target / "main.py"
        nuevo = self.target / "subdir" / "nuevo.py"
        tercero = self.target / "subdir" / "tercero.py"

        main.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
            "subdir/nuevo.py": "NUEVO = True\n",
            "subdir/tercero.py": "TERCERO = True\n",
        }

        import os

        original_replace = os.replace
        llamadas = {"count": 0}

        def replace_fallido(origen, destino):
            llamadas["count"] += 1

            if llamadas["count"] == 3:
                raise RuntimeError(
                    "Error simulado con archivo anidado"
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


    def test_consolidar_rollback_elimina_directorio_vacio_creado(self):
        main = self.target / "main.py"
        subdir = self.target / "subdir"
        nuevo = subdir / "nuevo.py"

        main.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
            "subdir/nuevo.py": "NUEVO = True\n",
            "fallo.py": "FALLO = True\n",
        }

        import os

        original_replace = os.replace
        llamadas = {"count": 0}

        def replace_fallido(origen, destino):
            llamadas["count"] += 1

            if llamadas["count"] == 3:
                raise RuntimeError(
                    "Error simulado después de crear directorio"
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
            subdir.exists()
        )


    def test_consolidar_rollback_restaurar_archivo_anidado_existente(self):
        main = self.target / "main.py"
        config = self.target / "config" / "settings.py"

        main.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        config.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        config.write_text(
            "DEBUG = False\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
            "config/settings.py": "DEBUG = True\n",
            "nuevo.py": "NUEVO = True\n",
        }

        import os

        original_replace = os.replace
        llamadas = {"count": 0}

        def replace_fallido(origen, destino):
            llamadas["count"] += 1

            if llamadas["count"] == 3:
                raise RuntimeError(
                    "Error simulado restaurando archivo anidado"
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


    def test_crear_backup_falla_sin_dejar_backup_parcial(self):
        import shutil

        main = self.target / "main.py"
        config = self.target / "config.py"

        main.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        config.write_text(
            "DEBUG = True\n",
            encoding="utf-8",
        )

        original_copy2 = shutil.copy2
        llamadas = {"count": 0}

        def copy2_fallido(origen, destino):
            llamadas["count"] += 1

            if llamadas["count"] == 2:
                raise OSError(
                    "Error simulado durante segundo backup"
                )

            return original_copy2(
                origen,
                destino,
            )

        shutil.copy2 = copy2_fallido

        try:
            with self.assertRaises(OSError):
                self.agent.crear_backup(
                    [
                        "main.py",
                        "config.py",
                    ]
                )
        finally:
            shutil.copy2 = original_copy2

        backups = list(
            self.agent.backup_dir.iterdir()
        )

        self.assertEqual(
            backups,
            [],
        )



    def test_consolidar_falla_antes_de_modificar_si_backup_falla(self):
        main = self.target / "main.py"

        main.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
        }

        import shutil

        original_copy2 = shutil.copy2

        def copy2_fallido(origen, destino):
            raise OSError(
                "Error simulado creando backup"
            )

        shutil.copy2 = copy2_fallido

        try:
            with self.assertRaises(OSError):
                self.agent.consolidar(propuesta)
        finally:
            shutil.copy2 = original_copy2

        self.assertEqual(
            main.read_text(encoding="utf-8"),
            "VERSION = 1\n",
        )


    def test_consolidar_falla_si_no_puede_crear_temporal(self):
        main = self.target / "main.py"

        main.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
        }

        from unittest.mock import patch

        path_type = type(self.target / "dummy")
        original_write_text = path_type.write_text

        def write_text_fallido(self_path, contenido, *args, **kwargs):
            if self_path.name == ".main.py.supreme.tmp":
                raise OSError(
                    "Error simulado creando temporal"
                )

            return original_write_text(
                self_path,
                contenido,
                *args,
                **kwargs,
            )

        with patch.object(
            path_type,
            "write_text",
            new=write_text_fallido,
        ):
            with self.assertRaises(OSError):
                self.agent.consolidar(propuesta)

        self.assertEqual(
            main.read_text(encoding="utf-8"),
            "VERSION = 1\n",
        )


    def test_consolidar_exito_elimina_todos_los_temporales(self):
        main = self.target / "main.py"
        config = self.target / "config.py"
        nuevo = self.target / "nuevo.py"

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

        self.agent.consolidar(propuesta)

        self.assertEqual(
            main.read_text(encoding="utf-8"),
            "VERSION = 2\n",
        )

        self.assertEqual(
            config.read_text(encoding="utf-8"),
            "DEBUG = True\n",
        )

        self.assertEqual(
            nuevo.read_text(encoding="utf-8"),
            "NUEVO = True\n",
        )

        self.assertFalse(
            (self.target / ".main.py.supreme.tmp").exists()
        )

        self.assertFalse(
            (self.target / ".config.py.supreme.tmp").exists()
        )

        self.assertFalse(
            (self.target / ".nuevo.py.supreme.tmp").exists()
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

    def test_consolidar_propuesta_vacia_no_crea_backup(self):
        backups_antes = list(
            self.agent.backup_dir.iterdir()
        )

        self.agent.consolidar({})

        backups_despues = list(
            self.agent.backup_dir.iterdir()
        )

        self.assertEqual(
            backups_despues,
            backups_antes,
        )


    def test_consolidar_propuesta_vacia_no_modifica_proyecto(self):
        self.agent.consolidar({})

        archivos = list(
            self.target.rglob("*")
        )

        archivos = [
            path
            for path in archivos
            if path.is_file()
            and ".supreme_agent" not in path.parts
        ]

        self.assertEqual(
            archivos,
            [],
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


    def test_consolidar_continua_si_limpieza_temporal_falla(self):
        propuesta = {
            "main.py": "VERSION = 2\\n",
        }

        original_unlink = Path.unlink

        def unlink_fallido(self_path, *args, **kwargs):
            if self_path.name == ".main.py.supreme.tmp":
                raise OSError(
                    "Error simulado limpiando temporal"
                )

            return original_unlink(
                self_path,
                *args,
                **kwargs,
            )

        Path.unlink = unlink_fallido

        try:
            self.agent.consolidar(propuesta)
        finally:
            Path.unlink = original_unlink

        archivo = self.target / "main.py"

        self.assertTrue(
            archivo.exists()
        )

        self.assertEqual(
            archivo.read_text(
                encoding="utf-8"
            ),
            "VERSION = 2\\n",
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

    def test_consolidar_rollback_elimina_todos_los_directorios_anidados_vacios(self):
        main = self.target / "main.py"
        nuevo = (
            self.target
            / "nivel1"
            / "nivel2"
            / "nivel3"
            / "nuevo.py"
        )

        main.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
            "nivel1/nivel2/nivel3/nuevo.py": "NUEVO = True\n",
            "fallo.py": "FALLO = True\n",
        }

        import os

        original_replace = os.replace
        llamadas = {"count": 0}

        def replace_fallido(origen, destino):
            llamadas["count"] += 1

            # 1 -> main.py
            # 2 -> nuevo.py anidado
            # 3 -> fallo.py: provoca rollback
            if llamadas["count"] == 3:
                raise RuntimeError(
                    "Error simulado después de crear archivo profundamente anidado"
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
            (
                self.target
                / "nivel1"
                / "nivel2"
                / "nivel3"
            ).exists()
        )

        self.assertFalse(
            (
                self.target
                / "nivel1"
                / "nivel2"
            ).exists()
        )

        self.assertFalse(
            (
                self.target
                / "nivel1"
            ).exists()
        )

        self.assertTrue(
            self.target.exists()
        )



    # ================================================================
    # MEMORIA
    # ================================================================

    def test_consolidar_continua_si_guardar_memoria_falla(self):
        archivo = self.target / "main.py"

        archivo.write_text(
            "VERSION = 1\\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\\n",
        }

        memoria_original = self.agent.guardar_memoria

        def guardar_memoria_fallida(tipo, datos):
            raise OSError(
                "Error simulado guardando memoria"
            )

        self.agent.guardar_memoria = guardar_memoria_fallida

        try:
            self.agent.consolidar(propuesta)
        finally:
            self.agent.guardar_memoria = memoria_original

        self.assertEqual(
            archivo.read_text(encoding="utf-8"),
            "VERSION = 2\\n",
        )

        temporales = list(
            self.target.rglob("*.supreme.tmp")
        )

        self.assertEqual(
            temporales,
            [],
        )

    def test_consolidar_registra_memoria_con_datos_correctos(self):
        archivo = self.target / "main.py"

        archivo.write_text(
            "VERSION = 1\\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\\n",
        }

        registros = []

        memoria_original = self.agent.guardar_memoria

        def guardar_memoria_registro(tipo, datos):
            registros.append(
                (
                    tipo,
                    datos,
                )
            )

        self.agent.guardar_memoria = guardar_memoria_registro

        try:
            self.agent.consolidar(propuesta)
        finally:
            self.agent.guardar_memoria = memoria_original

        self.assertEqual(
            archivo.read_text(encoding="utf-8"),
            "VERSION = 2\\n",
        )

        self.assertEqual(
            len(registros),
            1,
        )

        tipo, datos = registros[0]

        self.assertEqual(
            tipo,
            "consolidation",
        )

        self.assertEqual(
            datos["files"],
            ["main.py"],
        )

        self.assertTrue(
            datos["backup"],
        )

        self.assertTrue(
            Path(datos["backup"]).exists()
        )

    def test_guardar_memoria_ignora_fallo_de_escritura(self):
        historia_original = self.agent.history_file

        class ArchivoHistoriaFallido:
            def open(self, *args, **kwargs):
                raise OSError(
                    "Error simulado escribiendo historial"
                )

        self.agent.history_file = ArchivoHistoriaFallido()

        try:
            self.agent.guardar_memoria(
                "test",
                {
                    "valor": 1,
                },
            )
        finally:
            self.agent.history_file = historia_original

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


    def test_consolidar_rollback_continua_si_limpieza_temporal_falla(self):
        archivo = self.target / "main.py"

        archivo.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
            "nuevo.py": "NUEVO = True\n",
        }

        import os

        original_replace = os.replace
        original_unlink = Path.unlink

        llamadas_replace = {"count": 0}

        def replace_fallido(origen, destino):
            llamadas_replace["count"] += 1

            if llamadas_replace["count"] == 2:
                raise OSError(
                    "Error simulado durante replace"
                )

            return original_replace(
                origen,
                destino,
            )

        def unlink_fallido(self_path, *args, **kwargs):
            if self_path.name == ".nuevo.py.supreme.tmp":
                raise OSError(
                    "Error simulado limpiando temporal durante rollback"
                )

            return original_unlink(
                self_path,
                *args,
                **kwargs
            )

        os.replace = replace_fallido
        Path.unlink = unlink_fallido

        try:
            with self.assertRaises(OSError):
                self.agent.consolidar(propuesta)
        finally:
            os.replace = original_replace
            Path.unlink = original_unlink

        self.assertEqual(
            archivo.read_text(
                encoding="utf-8"
            ),
            "VERSION = 1\n",
        )

        nuevo = self.target / "nuevo.py"

        self.assertFalse(
            nuevo.exists()
        )

    def test_consolidar_rollback_falla_al_eliminar_archivo_nuevo(self):
        main = self.target / "main.py"
        config = self.target / "config.py"
        nuevo = self.target / "nuevo.py"

        main.write_text(
            "VERSION = 1\\n",
            encoding="utf-8",
        )

        config.write_text(
            "DEBUG = False\\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\\n",
            "config.py": "DEBUG = True\\n",
            "nuevo.py": "NUEVO = True\\n",
            "fallo.py": "FALLO = True\\n",
        }

        import os
        from pathlib import Path
        from unittest.mock import patch

        original_replace = os.replace

        llamadas_replace = {"count": 0}

        def replace_fallido(origen, destino):
            llamadas_replace["count"] += 1

            # 1 -> main.py
            # 2 -> config.py
            # 3 -> nuevo.py
            # 4 -> fallo.py: provoca el fallo después
            #      de que nuevo.py ya existe.
            if llamadas_replace["count"] == 4:
                raise RuntimeError(
                    "Error simulado durante consolidación"
                )

            return original_replace(
                origen,
                destino,
            )

        def unlink_fallido(self_path, *args, **kwargs):
            if Path(self_path).resolve() == nuevo.resolve():
                raise OSError(
                    "Error simulado eliminando archivo nuevo"
                )

            return original_unlink(
                self_path,
                *args,
                **kwargs,
            )

        original_unlink = Path.unlink

        os.replace = replace_fallido

        try:
            with patch.object(
                Path,
                "unlink",
                new=unlink_fallido,
            ):
                with self.assertRaises(OSError):
                    self.agent.consolidar(propuesta)
        finally:
            os.replace = original_replace
    def test_consolidar_rollback_falla_despues_de_modificar_varios_archivos(self):
        main = self.target / "main.py"
        config = self.target / "config.py"
        nuevo = self.target / "nuevo.py"

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
        import shutil

        original_replace = os.replace
        original_copy2 = shutil.copy2

        llamadas_replace = {"count": 0}
        llamadas_copy2 = {"count": 0}

        def replace_fallido(origen, destino):
            llamadas_replace["count"] += 1

            if llamadas_replace["count"] == 3:
                raise RuntimeError(
                    "Error simulado durante consolidación"
                )

            return original_replace(
                origen,
                destino,
            )

        def copy2_fallido(origen, destino):
            llamadas_copy2["count"] += 1

            if llamadas_copy2["count"] == 1:
                raise OSError(
                    "Error simulado en primera restauración"
                )

            return original_copy2(
                origen,
                destino,
            )

        os.replace = replace_fallido
        shutil.copy2 = copy2_fallido

        try:
            with self.assertRaises(OSError):
                self.agent.consolidar(propuesta)
        finally:
            os.replace = original_replace
            shutil.copy2 = original_copy2

    def test_consolidar_rollback_falla_si_no_puede_eliminar_nuevo_anidado(self):
        main = self.target / "main.py"
        nuevo = self.target / "subdir" / "nuevo.py"

        main.write_text(
            "VERSION = 1\n",
            encoding="utf-8",
        )

        propuesta = {
            "main.py": "VERSION = 2\n",
            "subdir/nuevo.py": "NUEVO = True\n",
            "fallo.py": "FALLO = True\n",
        }

        import os
        from pathlib import Path
        from unittest.mock import patch

        original_replace = os.replace
        original_unlink = Path.unlink
        llamadas_replace = {"count": 0}

        def replace_fallido(origen, destino):
            llamadas_replace["count"] += 1

            # El primer replace modifica main.py.
            # El segundo replace crea subdir/nuevo.py.
            # El tercero falla y fuerza el rollback.
            if llamadas_replace["count"] == 3:
                raise RuntimeError(
                    "Error simulado durante consolidación"
                )

            return original_replace(
                origen,
                destino,
            )

        def unlink_fallido(self_path, *args, **kwargs):
            if Path(self_path).resolve() == nuevo.resolve():
                raise OSError(
                    "Error simulado eliminando nuevo anidado"
                )

            return original_unlink(
                self_path,
                *args,
                **kwargs,
            )

        os.replace = replace_fallido

        try:
            with patch.object(
                Path,
                "unlink",
                new=unlink_fallido,
            ):
                with self.assertRaises(OSError):
                    self.agent.consolidar(propuesta)
        finally:
            os.replace = original_replace


    # ================================================================
    # OLLAMA LOCAL - HEALTH CHECK Y STREAMING
    # ================================================================

    def test_ollama_health_check_exitoso(self):
        from unittest.mock import patch

        class RespuestaMock:
            status_code = 200

            def json(self):
                return {
                    "models": [
                        {"name": "qwen2.5-coder:3b"},
                        {"name": "qwen2.5-coder:7b"},
                    ]
                }

        with patch(
            "supervisor.requests.get",
            return_value=RespuestaMock(),
        ) as mock_get:

            modelos = self.agent.verificar_ollama()

        self.assertEqual(
            modelos,
            [
                "qwen2.5-coder:3b",
                "qwen2.5-coder:7b",
            ],
        )

        mock_get.assert_called_once_with(
            self.agent.config.ollama_tags_url,
            timeout=5,
        )


    def test_ollama_health_check_rechaza_conexion(self):
        from unittest.mock import patch
        import requests

        with patch(
            "supervisor.requests.get",
            side_effect=requests.exceptions.ConnectionError(
                "conexión rechazada"
            ),
        ):

            with self.assertRaises(RuntimeError) as contexto:
                self.agent.verificar_ollama()

        self.assertIn(
            "Ollama no está disponible",
            str(contexto.exception),
        )


    def test_ollama_health_check_rechaza_timeout(self):
        from unittest.mock import patch
        import requests

        with patch(
            "supervisor.requests.get",
            side_effect=requests.exceptions.Timeout(
                "timeout simulado"
            ),
        ):

            with self.assertRaises(RuntimeError) as contexto:
                self.agent.verificar_ollama()

        self.assertIn(
            "Ollama no respondió al health-check",
            str(contexto.exception),
        )


    def test_ollama_health_check_rechaza_http_no_exitoso(self):
        from unittest.mock import patch

        class RespuestaMock:
            status_code = 500
            text = "error interno"

        with patch(
            "supervisor.requests.get",
            return_value=RespuestaMock(),
        ):

            with self.assertRaises(RuntimeError) as contexto:
                self.agent.verificar_ollama()

        self.assertIn(
            "HTTP 500",
            str(contexto.exception),
        )


    def test_ollama_health_check_rechaza_json_invalido(self):
        from unittest.mock import patch

        class RespuestaMock:
            status_code = 200

            def json(self):
                raise ValueError(
                    "JSON inválido simulado"
                )

        with patch(
            "supervisor.requests.get",
            return_value=RespuestaMock(),
        ):

            with self.assertRaises(RuntimeError) as contexto:
                self.agent.verificar_ollama()

        self.assertIn(
            "respuesta no JSON",
            str(contexto.exception),
        )


    def test_ollama_consulta_streaming_exitoso(self):
        from unittest.mock import patch

        class RespuestaMock:
            status_code = 200
            text = ""

            def iter_lines(self):
                return [
                    b'{"response":"Hola","done":false}',
                    b'{"response":" desde","done":false}',
                    b'{"response":" Ollama","done":false}',
                    b'{"response":" local","done":true}',
                ]

        prompt = "Responde con un saludo."

        with patch(
            "supervisor.requests.post",
            return_value=RespuestaMock(),
        ) as mock_post:

            resultado = self.agent.consultar_ollama(
                prompt,
                rol="qa",
            )

        self.assertEqual(
            resultado,
            "Hola desde Ollama local",
        )

        mock_post.assert_called_once()

        args, kwargs = mock_post.call_args

        self.assertEqual(
            args[0],
            self.agent.config.ollama_url,
        )

        self.assertEqual(
            kwargs["json"]["model"],
            self.agent.config.model_rapido,
        )

        self.assertEqual(
            kwargs["json"]["prompt"],
            prompt,
        )

        self.assertTrue(
            kwargs["json"]["stream"],
        )

        self.assertEqual(
            kwargs["json"]["format"],
            "json",
        )

        self.assertEqual(
            kwargs["json"]["options"]["temperature"],
            0.1,
        )

        self.assertEqual(
            kwargs["json"]["options"]["top_p"],
            0.9,
        )

        self.assertEqual(
            kwargs["json"]["options"]["repeat_penalty"],
            1.1,
        )

        self.assertEqual(
            kwargs["timeout"],
            (
                10,
                self.agent.config.timeout_qa,
            ),
        )

        self.assertTrue(
            kwargs["stream"],
        )

    def test_ollama_connection_error_reintenta_y_recupera(self):
        from unittest.mock import patch
        import requests

        class RespuestaMock:
            status_code = 200

            def iter_lines(self):
                return [
                    b'{"response":"recuperado","done":true}',
                ]

        efectos = [
            requests.exceptions.ConnectionError(
                "conexion fallida"
            ),
            RespuestaMock(),
        ]

        with patch(
            "supervisor.requests.post",
            side_effect=efectos,
        ) as mock_post, patch(
            "supervisor.time.sleep"
        ) as mock_sleep:

            resultado = self.agent.consultar_ollama(
                "prueba conexion",
                rol="qa",
            )

        self.assertEqual(
            resultado,
            "recuperado",
        )

        self.assertEqual(
            mock_post.call_count,
            2,
        )

        mock_sleep.assert_called_once_with(
            self.agent.config.ollama_retry_backoff,
        )


    def test_ollama_timeout_reintenta_y_recupera(self):
        from unittest.mock import patch
        import requests

        class RespuestaMock:
            status_code = 200

            def iter_lines(self):
                return [
                    b'{"response":"recuperado","done":true}',
                ]

        efectos = [
            requests.exceptions.Timeout(
                "timeout simulado"
            ),
            RespuestaMock(),
        ]

        with patch(
            "supervisor.requests.post",
            side_effect=efectos,
        ) as mock_post, patch(
            "supervisor.time.sleep"
        ) as mock_sleep:

            resultado = self.agent.consultar_ollama(
                "prueba timeout",
                rol="qa",
            )

        self.assertEqual(
            resultado,
            "recuperado",
        )

        self.assertEqual(
            mock_post.call_count,
            2,
        )

        mock_sleep.assert_called_once_with(
            self.agent.config.ollama_retry_backoff,
        )


    def test_ollama_http_error_reintenta_y_recupera(self):
        from unittest.mock import patch

        class RespuestaError:
            status_code = 500
            text = "error interno"

        class RespuestaOK:
            status_code = 200

            def iter_lines(self):
                return [
                    b'{"response":"recuperado","done":true}',
                ]

        efectos = [
            RespuestaError(),
            RespuestaOK(),
        ]

        with patch(
            "supervisor.requests.post",
            side_effect=efectos,
        ) as mock_post, patch(
            "supervisor.time.sleep"
        ) as mock_sleep:

            resultado = self.agent.consultar_ollama(
                "prueba http",
                rol="qa",
            )

        self.assertEqual(
            resultado,
            "recuperado",
        )

        self.assertEqual(
            mock_post.call_count,
            2,
        )

        mock_sleep.assert_called_once_with(
            self.agent.config.ollama_retry_backoff,
        )


    def test_ollama_streaming_interrumpido_reintenta_y_recupera(self):
        from unittest.mock import patch
        import requests

        class RespuestaInterrumpida:
            status_code = 200

            def iter_lines(self):
                yield b'{"response":"parcial","done":false}'
                raise requests.exceptions.ChunkedEncodingError(
                    "stream roto"
                )

        class RespuestaOK:
            status_code = 200

            def iter_lines(self):
                return [
                    b'{"response":"recuperado","done":true}',
                ]

        efectos = [
            RespuestaInterrumpida(),
            RespuestaOK(),
        ]

        with patch(
            "supervisor.requests.post",
            side_effect=efectos,
        ) as mock_post, patch(
            "supervisor.time.sleep"
        ) as mock_sleep:

            resultado = self.agent.consultar_ollama(
                "prueba streaming",
                rol="qa",
            )

        self.assertEqual(
            resultado,
            "recuperado",
        )

        self.assertEqual(
            mock_post.call_count,
            2,
        )

        mock_sleep.assert_called_once_with(
            self.agent.config.ollama_retry_backoff,
        )


    def test_ollama_respuesta_vacia_reintenta_y_recupera(self):
        from unittest.mock import patch

        class RespuestaVacia:
            status_code = 200

            def iter_lines(self):
                return [
                    b'{"response":"","done":true}',
                ]

        class RespuestaOK:
            status_code = 200

            def iter_lines(self):
                return [
                    b'{"response":"recuperado","done":true}',
                ]

        efectos = [
            RespuestaVacia(),
            RespuestaOK(),
        ]

        with patch(
            "supervisor.requests.post",
            side_effect=efectos,
        ) as mock_post, patch(
            "supervisor.time.sleep"
        ) as mock_sleep:

            resultado = self.agent.consultar_ollama(
                "prueba respuesta vacia",
                rol="qa",
            )

        self.assertEqual(
            resultado,
            "recuperado",
        )

        self.assertEqual(
            mock_post.call_count,
            2,
        )

        mock_sleep.assert_called_once_with(
            self.agent.config.ollama_retry_backoff,
        )


    def test_ollama_agotados_todos_los_reintentos_lanza_error(self):
        from unittest.mock import patch
        import requests

        error = requests.exceptions.ConnectionError(
            "Ollama no disponible"
        )

        with patch(
            "supervisor.requests.post",
            side_effect=error,
        ) as mock_post, patch(
            "supervisor.time.sleep"
        ) as mock_sleep:

            with self.assertRaises(RuntimeError) as contexto:
                self.agent.consultar_ollama(
                    "prueba agotamiento",
                    rol="qa",
                )

        self.assertIn(
            "No se pudo conectar con Ollama",
            str(contexto.exception),
        )

        self.assertEqual(
            mock_post.call_count,
            self.agent.config.ollama_max_retries,
        )

        self.assertEqual(
            mock_sleep.call_count,
            self.agent.config.ollama_max_retries - 1,
        )

        esperas = [
            llamada.args[0]
            for llamada in mock_sleep.call_args_list
        ]

        self.assertEqual(
            esperas,
            [
                self.agent.config.ollama_retry_backoff,
                self.agent.config.ollama_retry_backoff * 2,
            ],
        )

    def test_ollama_request_exception_reintenta_y_recupera(self):
        from unittest.mock import patch
        import requests

        class RespuestaOK:
            status_code = 200

            def iter_lines(self):
                return [
                    b'{"response":"recuperado","done":true}',
                ]

        efectos = [
            requests.exceptions.RequestException(
                "error de red generico"
            ),
            RespuestaOK(),
        ]

        with patch(
            "supervisor.requests.post",
            side_effect=efectos,
        ) as mock_post, patch(
            "supervisor.time.sleep"
        ) as mock_sleep:

            resultado = self.agent.consultar_ollama(
                "prueba request exception",
                rol="qa",
            )

        self.assertEqual(
            resultado,
            "recuperado",
        )

        self.assertEqual(
            mock_post.call_count,
            2,
        )

        mock_sleep.assert_called_once_with(
            self.agent.config.ollama_retry_backoff,
        )


    def test_ollama_backoff_exponencial_usa_2_y_4_segundos(self):
        from unittest.mock import patch
        import requests

        error = requests.exceptions.ConnectionError(
            "conexion fallida"
        )

        with patch(
            "supervisor.requests.post",
            side_effect=error,
        ) as mock_post, patch(
            "supervisor.time.sleep"
        ) as mock_sleep:

            with self.assertRaises(RuntimeError):
                self.agent.consultar_ollama(
                    "prueba backoff",
                    rol="qa",
                )

        self.assertEqual(
            mock_post.call_count,
            self.agent.config.ollama_max_retries,
        )

        esperas = [
            llamada.args[0]
            for llamada in mock_sleep.call_args_list
        ]

        self.assertEqual(
            esperas,
            [
                self.agent.config.ollama_retry_backoff,
                self.agent.config.ollama_retry_backoff * 2,
            ],
        )


    def test_ollama_no_hace_sleep_despues_del_ultimo_intento(self):
        from unittest.mock import patch
        import requests

        error = requests.exceptions.ConnectionError(
            "conexion fallida"
        )

        with patch(
            "supervisor.requests.post",
            side_effect=error,
        ) as mock_post, patch(
            "supervisor.time.sleep"
        ) as mock_sleep:

            with self.assertRaises(RuntimeError):
                self.agent.consultar_ollama(
                    "prueba ultimo intento",
                    rol="qa",
                )

        self.assertEqual(
            mock_post.call_count,
            self.agent.config.ollama_max_retries,
        )

        self.assertEqual(
            mock_sleep.call_count,
            self.agent.config.ollama_max_retries - 1,
        )


    def test_ollama_reintentos_configurables(self):
        from unittest.mock import patch
        import requests

        self.agent.config.ollama_max_retries = 1

        error = requests.exceptions.ConnectionError(
            "conexion fallida"
        )

        with patch(
            "supervisor.requests.post",
            side_effect=error,
        ) as mock_post, patch(
            "supervisor.time.sleep"
        ) as mock_sleep:

            with self.assertRaises(RuntimeError):
                self.agent.consultar_ollama(
                    "prueba un solo intento",
                    rol="qa",
                )

        self.assertEqual(
            mock_post.call_count,
            1,
        )

        mock_sleep.assert_not_called()


    def test_ollama_backoff_respeta_valor_configurado(self):
        from unittest.mock import patch
        import requests

        self.agent.config.ollama_retry_backoff = 0.25

        error = requests.exceptions.ConnectionError(
            "conexion fallida"
        )

        with patch(
            "supervisor.requests.post",
            side_effect=error,
        ), patch(
            "supervisor.time.sleep"
        ) as mock_sleep:

            with self.assertRaises(RuntimeError):
                self.agent.consultar_ollama(
                    "prueba backoff configurado",
                    rol="qa",
                )

        esperas = [
            llamada.args[0]
            for llamada in mock_sleep.call_args_list
        ]

        self.assertEqual(
            esperas,
            [
                0.25,
                0.5,
            ],
        )


    def test_ollama_request_exception_agotada_conserva_error_generico(self):
        from unittest.mock import patch
        import requests

        error = requests.exceptions.RequestException(
            "servidor no responde"
        )

        with patch(
            "supervisor.requests.post",
            side_effect=error,
        ) as mock_post, patch(
            "supervisor.time.sleep"
        ):

            with self.assertRaises(RuntimeError) as contexto:
                self.agent.consultar_ollama(
                    "prueba request exception agotada",
                    rol="qa",
                )

        self.assertIn(
            "Error de red comunicando con Ollama",
            str(contexto.exception),
        )

        self.assertEqual(
            mock_post.call_count,
            self.agent.config.ollama_max_retries,
        )
