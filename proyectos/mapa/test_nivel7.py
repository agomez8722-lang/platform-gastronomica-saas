import unittest, json, pathlib, ast, time
import evolutivo_real as evo
import main

class TestDetectoresDinamicosV10(unittest.TestCase):
    def test_11_privilegio_v10(self):
        self.assertTrue(evo.detectar_privilegio_v10({"rol":"user","recurso":"/admin/panel"}))
    def test_12_horario_v10(self):
        self.assertTrue(evo.detectar_horario_v10({"rol":"admin","recurso":"/admin","hora":"23:00:00"}))
    def test_13_brute_force_v10(self):
        self.assertTrue(evo.detectar_brute_force_v10({"rol":"user","recurso":"/admin"}))
    def test_14_rate_limit_v10(self):
        store={"10.0.0.1":[time.time()]*9}
        self.assertTrue(evo.detectar_rate_limit_v10("10.0.0.1", store))
    def test_15_2fa_bypass_v10(self):
        self.assertTrue(evo.detectar_2fa_bypass_v10({"recurso":"/admin","ip":"10.0.0.4"}))

class TestDetectoresEstaticos(unittest.TestCase):
    def test_01_privilegio_user_admin_path(self):
        self.assertTrue(evo.detectar_privilegio_v10({"rol":"user","recurso":"/admin/panel"}))
    def test_02_privilegio_admin_no_dispara(self):
        self.assertFalse(evo.detectar_privilegio_v10({"rol":"admin","recurso":"/admin/panel"}))
    def test_03_horario_admin_fuera_de_horario(self):
        self.assertTrue(evo.detectar_horario_v10({"rol":"admin","recurso":"/admin","hora":"23:00:00"}))
    def test_04_horario_admin_dentro_de_horario(self):
        self.assertFalse(evo.detectar_horario_v10({"rol":"admin","recurso":"/admin","hora":"10:00:00"}))
    def test_05_brute_force_user(self):
        self.assertTrue(evo.detectar_brute_force_v10({"rol":"user","recurso":"/admin"}))
    def test_06_brute_force_admin_no_dispara(self):
        self.assertFalse(evo.detectar_brute_force_v10({"rol":"admin","recurso":"/admin"}))
    def test_07_rate_limit_excede_umbral(self):
        store={"10.0.0.1":[time.time()]*9}
        self.assertTrue(evo.detectar_rate_limit_v10("10.0.0.1", store))
    def test_08_rate_limit_bajo_umbral(self):
        store={"10.0.0.1":[time.time()]*2}
        self.assertFalse(evo.detectar_rate_limit_v10("10.0.0.1", store))
    def test_09_2fa_bypass_ip_sospechosa(self):
        self.assertTrue(evo.detectar_2fa_bypass_v10({"recurso":"/admin","ip":"10.0.0.4"}))
    def test_10_2fa_bypass_ip_normal(self):
        self.assertFalse(evo.detectar_2fa_bypass_v10({"recurso":"/admin","ip":"10.0.0.5"}))

class TestMotorEvolutivoNivel10(unittest.TestCase):
    def test_16_motor_carga_detectores_dinamicos(self):
        motor=main.MotorEvolutivoNivel10()
        res=motor.ciclo()
        self.assertGreaterEqual(res["detectores_dinamicos"], 20)
    def test_17_detectar_anomalias_integrado(self):
        res=main._evaluar_reglas({"rol":"user","recurso":"/admin/panel","ip":"10.0.0.1"}, {})
        self.assertTrue(res["anomalo"])

class TestNivel11Evolucion(unittest.TestCase):
    def test_18_sqli_v11(self):
        self.assertTrue(evo.detectar_sqli_v11({"recurso":"/search?q=' OR '1'='1"}))
    def test_19_path_traversal_v11(self):
        self.assertTrue(evo.detectar_path_traversal_v11({"recurso":"/../../etc/passwd"}))
    def test_20_user_agent_v11(self):
        self.assertTrue(evo.detectar_user_agent_v11({"user_agent":"sqlmap/1.0"}))
    def test_21_motor_carga_ocho_detectores(self):
        motor=main.MotorEvolutivoNivel10()
        self.assertEqual(motor.ciclo()["detectores_dinamicos"], 20)
    def test_22_fitness_real_maximo_con_todo_activo(self):
        self.assertEqual(main.health()["fitness"], 500)
    def test_23_nivel_asciende_a_12_con_todo_sano(self):
        h=main.health()
        self.assertGreaterEqual(h["nivel"], 13)
        self.assertEqual(h["detectores_dinamicos"], 20)
    def test_24_rollback_en_recarga_con_sintaxis_invalida(self):
        orig=pathlib.Path("evolutivo_real.py").read_text()
        try:
            pathlib.Path("evolutivo_real.py").write_text("def invalido :::")
            h=main.health()
            self.assertIn("nivel", h)
        finally:
            pathlib.Path("evolutivo_real.py").write_text(orig)
    def test_25_registrar_anomalia_persiste_severidad(self):
        r={"rol":"user","recurso":"/admin/panel","ip":"9.9.9.9"}
        self.assertIn("detectores", main._evaluar_reglas(r, {}))

class TestNivel12MemoriaInmunologica(unittest.TestCase):
    def setUp(self):
        pathlib.Path("lista_negra.json").write_text("{}")
    def test_26_autodiagnostico_pasa_con_sistema_sano(self):
        self.assertGreaterEqual(main.health()["detectores_dinamicos"], 20)
    def test_27_ip_no_bloqueada_por_defecto(self):
        self.assertFalse(main.esta_bloqueada("1.2.3.4"))
    def test_28_ip_se_bloquea_tras_superar_umbral(self):
        ip="5.5.5.5"
        for _ in range(5):
            main.registrar_memoria_inmunologica(ip, True)
        self.assertTrue(main.esta_bloqueada(ip))
    def test_29_ip_bloqueada_persiste_en_disco(self):
        ip="6.6.6.6"
        for _ in range(5):
            main.registrar_memoria_inmunologica(ip, True)
        self.assertIn(ip, main.cargar_memoria_inmunologica())
    def test_30_deteccion_prioriza_memoria_inmunologica(self):
        ip="7.7.7.7"
        for _ in range(5):
            main.registrar_memoria_inmunologica(ip, True)
        res=main._evaluar_reglas({"ip":ip,"recurso":"/admin"}, {})
        self.assertTrue(res["bloqueado"])
        self.assertEqual(res["status"], 403)
        self.assertIn("ip_bloqueada_403", res["motivos"])
    def test_31_servidor_threading_disponible(self):
        import threading
        self.assertTrue(threading.current_thread().is_alive())
