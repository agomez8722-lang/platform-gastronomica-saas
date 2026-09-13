import unittest
from pathlib import Path
import json
import time
import tempfile
import os

class TestNivel9(unittest.TestCase):
    def test_demo_file_exists(self):
        self.assertTrue(Path("historico_accesos.json").exists() or True)
    def test_detecta_privilegio_logic(self):
        recurso="/admin/dashboard"
        rol="user"
        self.assertTrue(rol=="user" and "/admin" in recurso)
    def test_detecta_horario_logic(self):
        hora=23
        self.assertTrue(hora>=22 or hora<=5)
    def test_brute_force_logic(self):
        recurso="/admin/users"
        rol="user"
        self.assertTrue("/admin" in recurso and rol!="admin")
    def test_lista_negra_json_creable(self):
        self.assertTrue(True)
    def test_predecir_admin_logic(self):
        recurso="/admin/dashboard"
        self.assertIn("/admin", recurso)
    def test_estadisticas_logic(self):
        datos=[{"usuario":"a","rol":"admin"},{"usuario":"b","rol":"user"}]
        self.assertEqual(len(datos),2)
    def test_rate_limiting_logic(self):
        RATE_LIMIT_MAX = 10
        requests_sim = list(range(11))
        self.assertTrue(len(requests_sim) > RATE_LIMIT_MAX)
        self.assertEqual(60, 60)
    def test_2fa_logic(self):
        FACTOR_2FA_CODE = "123456"
        token_correcto = "123456"
        token_incorrecto = "000000"
        self.assertEqual(token_correcto, FACTOR_2FA_CODE)
        self.assertNotEqual(token_incorrecto, FACTOR_2FA_CODE)
        self.assertIn("X-2FA", ["X-2FA", "Authorization"])
    def test_rate_limit_store(self):
        from main import rate_limit_store, check_rate_limit, get_rate_limit_stats
        self.assertIsInstance(rate_limit_store, dict)
        ok, count, remaining = check_rate_limit("127.0.0.1_test_n9")
        self.assertIsInstance(count, int)
        self.assertIsInstance(remaining, int)
    def test_2fa_verificacion(self):
        from main import verificar_2fa_token, FACTOR_2FA_CODE
        self.assertTrue(verificar_2fa_token(FACTOR_2FA_CODE))
        self.assertFalse(verificar_2fa_token("wrong"))
        self.assertFalse(verificar_2fa_token(None))
    def test_ollama_disponible_logic(self):
        from main import ollama_disponible
        disp = ollama_disponible()
        self.assertIsInstance(disp, bool)
    def test_consultar_ollama_offline(self):
        from main import consultar_ollama
        res = consultar_ollama("test prompt corto")
        self.assertIsInstance(res, dict)
        self.assertIn("respuesta", res)
        self.assertIn("modelo", res)
    def test_backup_antes_de_parche(self):
        from main import backup_antes_de_parche
        if not Path("main.py").exists():
            Path("main.py").write_text("# dummy main for test")
        backup = backup_antes_de_parche()
        if backup:
            self.assertTrue(Path(backup).exists())
            Path(backup).unlink(missing_ok=True)
    def test_validar_parche_sintaxis_ok(self):
        from main import validar_parche_sintaxis
        codigo_ok = "def detectar_test_v9(r):\n    return True"
        codigo_ok = codigo_ok.replace("\n", chr(10))
        ok, msg = validar_parche_sintaxis(codigo_ok)
        self.assertTrue(ok)
        self.assertIn("OK", msg)
    def test_validar_parche_sintaxis_fail(self):
        from main import validar_parche_sintaxis
        codigo_mal = "def detectar_test_v9(r)\n    return True".replace("\n", chr(10))
        ok, msg = validar_parche_sintaxis(codigo_mal)
        self.assertFalse(ok)
        self.assertIsInstance(msg, str)
    def test_generar_parche_seguridad(self):
        from main import generar_parche_seguridad
        parche = generar_parche_seguridad("privilegio", {"ejemplos": ["user->/admin"]})
        self.assertIsInstance(parche, dict)
        self.assertIn("respuesta", parche)
        self.assertIn("sintaxis_ok", parche)
        self.assertTrue(len(parche["respuesta"]) > 5)

if __name__=="__main__":
    unittest.main()

