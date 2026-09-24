import time
import unittest

import main
import evolutivo_real as ev


class TestDetectoresEstaticos(unittest.TestCase):

    def test_01_privilegio_user_admin_path(self):
        r = {"rol": "user", "recurso": "/admin/panel"}
        self.assertTrue(main.detectar_privilegio(r))

    def test_02_privilegio_admin_no_dispara(self):
        r = {"rol": "admin", "recurso": "/admin/panel"}
        self.assertFalse(main.detectar_privilegio(r))

    def test_03_horario_admin_fuera_de_horario(self):
        r = {"rol": "admin", "recurso": "/admin/config", "hora": "23:30:00"}
        self.assertTrue(main.detectar_horario(r))

    def test_04_horario_admin_dentro_de_horario(self):
        r = {"rol": "admin", "recurso": "/admin/config", "hora": "10:00:00"}
        self.assertFalse(main.detectar_horario(r))

    def test_05_brute_force_user(self):
        r = {"rol": "user", "recurso": "/admin/login"}
        self.assertTrue(main.detectar_brute_force(r))

    def test_06_brute_force_admin_no_dispara(self):
        r = {"rol": "admin", "recurso": "/admin/login"}
        self.assertFalse(main.detectar_brute_force(r))

    def test_07_rate_limit_excede_umbral(self):
        store = {}
        ahora = time.time()
        store["1.2.3.4"] = [ahora] * 8
        self.assertTrue(main.detectar_rate_limit("1.2.3.4", store))

    def test_08_rate_limit_bajo_umbral(self):
        store = {"1.2.3.4": [time.time()] * 3}
        self.assertFalse(main.detectar_rate_limit("1.2.3.4", store))

    def test_09_2fa_bypass_ip_sospechosa(self):
        r = {"recurso": "/admin/secure", "ip": "10.0.0.4"}
        self.assertTrue(main.detectar_2fa_bypass(r))

    def test_10_2fa_bypass_ip_normal(self):
        r = {"recurso": "/admin/secure", "ip": "192.168.1.1"}
        self.assertFalse(main.detectar_2fa_bypass(r))


class TestDetectoresDinamicosV10(unittest.TestCase):

    def test_11_privilegio_v10(self):
        r = {"rol": "user", "recurso": "/dashboard"}
        self.assertTrue(ev.detectar_privilegio_v10(r))

    def test_12_horario_v10(self):
        r = {"rol": "admin", "recurso": "/admin", "hora": "02:00:00"}
        self.assertTrue(ev.detectar_horario_v10(r))

    def test_13_brute_force_v10(self):
        r = {"rol": "guest", "recurso": "/admin/login"}
        self.assertTrue(ev.detectar_brute_force_v10(r))

    def test_14_rate_limit_v10(self):
        store = {"9.9.9.9": [time.time()] * 8}
        self.assertTrue(ev.detectar_rate_limit_v10("9.9.9.9", store))

    def test_15_2fa_bypass_v10(self):
        r = {"recurso": "/api/admin", "ip": "10.0.0.99"}
        self.assertTrue(ev.detectar_2fa_bypass_v10(r))


class TestMotorEvolutivoNivel10(unittest.TestCase):

    def test_16_motor_carga_detectores_dinamicos(self):
        motor = main.MotorEvolutivoNivel10()
        self.assertTrue(motor.activo)
        self.assertFalse(motor.aislado)
        self.assertGreaterEqual(motor.conteo_detectores_activos(), 5)

    def test_17_detectar_anomalias_integrado(self):
        store = {}
        r = {"rol": "user", "recurso": "/admin/panel", "ip": "1.1.1.1", "hora": "10:00:00"}
        resultado = main.detectar_anomalias(r, store)
        self.assertTrue(resultado["anomalo"])
        self.assertIn(resultado["origen"], ["dinamico", "estatico"])


class TestNivel11Evolucion(unittest.TestCase):

    def test_18_sqli_v11(self):
        r = {"recurso": "/search?q=' OR '1'='1"}
        self.assertTrue(ev.detectar_sqli_v11(r))

    def test_19_path_traversal_v11(self):
        r = {"recurso": "/files/../../etc/passwd"}
        self.assertTrue(ev.detectar_path_traversal_v11(r))

    def test_20_user_agent_v11(self):
        r = {"user_agent": "sqlmap/1.6"}
        self.assertTrue(ev.detectar_user_agent_v11(r))

    def test_21_motor_carga_ocho_detectores(self):
        motor = main.MotorEvolutivoNivel10()
        self.assertEqual(motor.conteo_detectores_activos(), 8)

    def test_22_fitness_real_maximo_con_todo_activo(self):
        main.motor_evolutivo = main.MotorEvolutivoNivel10()
        self.assertEqual(main.calcular_fitness_real(), 200)

    def test_23_nivel_asciende_a_12_con_todo_sano(self):
        main.motor_evolutivo = main.MotorEvolutivoNivel10()
        stats = main.calcular_estadisticas()
        self.assertEqual(stats["nivel"], 12)
        self.assertEqual(stats["detectores_dinamicos"], 8)
        self.assertTrue(stats["autodiagnostico_ok"])
        self.assertTrue(stats["memoria_inmunologica_ok"])

    def test_24_rollback_en_recarga_con_sintaxis_invalida(self):
        motor = main.MotorEvolutivoNivel10()
        activos_antes = motor.conteo_detectores_activos()
        ruta_temp = motor.path
        with open(ruta_temp, encoding="utf-8") as f:
            contenido_original = f.read()
        try:
            with open(ruta_temp, "a", encoding="utf-8") as f:
                f.write("\ndef roto(:\n    pass\n")  # sintaxis invalida a proposito
            cambio = motor.recargar_si_cambio()
            self.assertFalse(cambio)
            self.assertFalse(motor.aislado)
            self.assertEqual(motor.conteo_detectores_activos(), activos_antes)
        finally:
            with open(ruta_temp, "w", encoding="utf-8") as f:
                f.write(contenido_original)

    def test_25_registrar_anomalia_persiste_severidad(self):
        import sqlite3
        r = {"rol": "user", "recurso": "/admin/panel", "ip": "1.1.1.1", "hora": "10:00:00"}
        resultado = main.detectar_anomalias(r, {})
        conn = sqlite3.connect(main.DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT severidad FROM anomalias_log ORDER BY id DESC LIMIT 1")
        fila = cur.fetchone()
        conn.close()
        self.assertIsNotNone(fila)
        self.assertIn(fila[0], ["info", "media", "alta", "critica"])


class TestNivel12MemoriaInmunologica(unittest.TestCase):

    def setUp(self):
        # Aislar cada test: limpiar entradas de prueba de la lista negra real
        for ip in ["77.77.77.1", "77.77.77.2"]:
            main._lista_negra.pop(ip, None)
        main._guardar_lista_negra()

    def tearDown(self):
        for ip in ["77.77.77.1", "77.77.77.2"]:
            main._lista_negra.pop(ip, None)
        main._guardar_lista_negra()

    def test_26_autodiagnostico_pasa_con_sistema_sano(self):
        self.assertTrue(main.autodiagnostico())

    def test_27_ip_no_bloqueada_por_defecto(self):
        self.assertFalse(main.ip_bloqueada("77.77.77.1"))

    def test_28_ip_se_bloquea_tras_superar_umbral(self):
        ip = "77.77.77.1"
        for _ in range(main.UMBRAL_BLOQUEO):
            main.registrar_memoria_inmunologica(ip, True)
        self.assertTrue(main.ip_bloqueada(ip))

    def test_29_ip_bloqueada_persiste_en_disco(self):
        ip = "77.77.77.2"
        for _ in range(main.UMBRAL_BLOQUEO):
            main.registrar_memoria_inmunologica(ip, True)
        recargada = main._cargar_lista_negra()
        self.assertTrue(recargada.get(ip, {}).get("bloqueada"))

    def test_30_deteccion_prioriza_memoria_inmunologica(self):
        ip = "77.77.77.1"
        for _ in range(main.UMBRAL_BLOQUEO):
            main.registrar_memoria_inmunologica(ip, True)
        registro = {"rol": "admin", "recurso": "/perfil", "ip": ip, "hora": "10:00:00"}
        resultado = main.detectar_anomalias(registro, {})
        self.assertTrue(resultado["anomalo"])
        self.assertEqual(resultado["origen"], "memoria_inmunologica")
        self.assertEqual(resultado["severidad"], "critica")

    def test_31_servidor_threading_disponible(self):
        servidor = main._crear_servidor(puerto=0)
        try:
            from http.server import ThreadingHTTPServer
            self.assertIsInstance(servidor, ThreadingHTTPServer)
        finally:
            servidor.server_close()


if __name__ == "__main__":
    unittest.main()
