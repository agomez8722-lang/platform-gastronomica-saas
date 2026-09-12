import importlib
import os, json, unittest
import main
from auth import validar_rol, filtrar_por_rol
from db import AccessRepository

class TestFase1(unittest.TestCase):
    def setUp(self):
        self.datos = [
            {"usuario":"ana","rol":"admin","fecha":"2024-01-02","hora":"09:30:00","recurso":"/a"},
            {"usuario":"luis","rol":"admin","fecha":"2024-01-01","hora":"08:00:00","recurso":"/b"},
            {"usuario":"maria","rol":"user","fecha":"2024-01-03","hora":"10:00:00","recurso":"/c"},
        ]

    def test_01_admins_ordenados(self):
        res = main.filtrar_y_ordenar_accesos(self.datos, "admin")
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["usuario"], "luis") # 01-01 antes que 02

    def test_02_excluye_otros(self):
        res = main.filtrar_y_ordenar_accesos(self.datos, "admin")
        self.assertTrue(all(r["rol"]=="admin" for r in res))

    def test_03_none_input(self):
        self.assertEqual(main.filtrar_y_ordenar_accesos(None), [])
        self.assertEqual(main.filtrar_y_ordenar_accesos([], "admin"), [])

    def test_04_no_existe_historico(self):
        if os.path.exists("historico_accesos.json"):
            os.remove("historico_accesos.json")
        datos = main.cargar_historico("historico_accesos.json")
        self.assertTrue(os.path.exists("historico_accesos.json"))
        self.assertEqual(len(datos), 5)

    def test_05_csv_existe(self):
        d = main.cargar_historico()
        f = main.filtrar_y_ordenar_accesos(d, "admin")
        main.guardar_csv(f, "accesos_filtrados.csv")
        self.assertTrue(os.path.exists("accesos_filtrados.csv"))

    def test_06_json_existe(self):
        d = main.cargar_historico()
        f = main.filtrar_y_ordenar_accesos(d, "admin")
        main.guardar_json(f, "accesos_filtrados.json")
        self.assertTrue(os.path.exists("accesos_filtrados.json"))

    def test_07_stats_keys(self):
        stats = main.calcular_estadisticas(self.datos)
        self.assertIn("total", stats)
        self.assertIn("por_rol", stats)
        self.assertIn("usuarios_unicos", stats)

    def test_08_validar_true(self):
        self.assertTrue(validar_rol({"rol":"admin"}, "admin"))
        self.assertTrue(validar_rol({"rol":"admin"}, "user")) # jerarquico 100 >=10

    def test_09_validar_false(self):
        self.assertFalse(validar_rol({"rol":"user"}, "admin"))
        self.assertFalse(validar_rol({}, "admin"))
        self.assertFalse(validar_rol({"rol":"admin"}, "inexistente"))

    def test_10_filtrar_por_rol(self):
        res = filtrar_por_rol(self.datos, "user")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["usuario"], "maria")

    def test_11_db_migracion(self):
        repo = AccessRepository("accesos.db")
        # migrar desde historico*.json
        repo.migrar_desde_json()
        lista = repo.listar()
        self.assertTrue(len(lista) >= 2)
        self.assertTrue(os.path.exists("accesos.db"))

    def test_12_import_main(self):
        importlib
        m = importlib.import_module("main")
        self.assertTrue(hasattr(m, "filtrar_y_ordenar_accesos"))
        self.assertTrue(hasattr(m, "cargar_historico"))

if __name__ == "__main__":
    unittest.main()
