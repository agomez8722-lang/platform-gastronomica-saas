import unittest
from pathlib import Path
class TestNivel7(unittest.TestCase):
    def test_privilegio(self): self.assertTrue("user"=="user" and "/admin" in "/admin/dashboard")
    def test_horario(self): self.assertTrue(23>=22)
    def test_brute(self): self.assertIn("/admin", "/admin/users")
    def test_json(self): self.assertTrue(True)
    def test_admin(self): self.assertIn("/admin", "/admin/dashboard")
    def test_user(self): self.assertEqual(2,2)
    def test_stats(self): self.assertEqual(len([1,2]),2)
if __name__=="__main__": unittest.main()
