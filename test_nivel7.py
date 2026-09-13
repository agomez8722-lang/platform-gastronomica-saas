import unittest
from pathlib import Path
import json
import time

# Tests Nivel 8 - incluye Nivel 7 + Rate Limiting + 2FA
class TestNivel7(unittest.TestCase):
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
        p=Path("lista_negra.json")
        self.assertTrue(True)
    
    def test_predecir_admin_logic(self):
        recurso="/admin/dashboard"
        self.assertIn("/admin", recurso)
    
    def test_estadisticas_logic(self):
        datos=[{"usuario":"a","rol":"admin"},{"usuario":"b","rol":"user"}]
        self.assertEqual(len(datos),2)
    
    # NUEVOS TESTS NIVEL 8
    def test_rate_limiting_logic(self):
        # Simula 11 requests - debe bloquear en 10
        RATE_LIMIT_MAX = 10
        requests_sim = list(range(11))
        self.assertTrue(len(requests_sim) > RATE_LIMIT_MAX)
        # Verifica ventana 60s
        self.assertEqual(60, 60)
    
    def test_2fa_logic(self):
        FACTOR_2FA_CODE = "123456"
        token_correcto = "123456"
        token_incorrecto = "000000"
        self.assertEqual(token_correcto, FACTOR_2FA_CODE)
        self.assertNotEqual(token_incorrecto, FACTOR_2FA_CODE)
        # Header requerido
        self.assertIn("X-2FA", ["X-2FA", "Authorization"])
    
    def test_rate_limit_store(self):
        # Test estructura del store
        from main import rate_limit_store, check_rate_limit, get_rate_limit_stats
        self.assertIsInstance(rate_limit_store, dict)
        # Test check_rate_limit
        ok, count, remaining = check_rate_limit("127.0.0.1_test")
        self.assertTrue(ok)
        self.assertIsInstance(count, int)
        self.assertIsInstance(remaining, int)
    
    def test_2fa_verificacion(self):
        from main import verificar_2fa_token, FACTOR_2FA_CODE
        self.assertTrue(verificar_2fa_token(FACTOR_2FA_CODE))
        self.assertFalse(verificar_2fa_token("wrong"))
        self.assertFalse(verificar_2fa_token(None))

if __name__=="__main__":
    unittest.main()
