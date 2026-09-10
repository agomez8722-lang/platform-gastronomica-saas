import subprocess
import unittest
from pathlib import Path

from project_state import inspect_git


PROJECT_ROOT = Path(__file__).resolve().parent


class TestGitState(unittest.TestCase):

    def test_detecta_branch_actual(self):
        state = inspect_git(PROJECT_ROOT)

        expected = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        self.assertEqual(state.branch, expected)

    def test_detecta_commit_actual(self):
        state = inspect_git(PROJECT_ROOT)

        expected = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        self.assertEqual(state.commit, expected)

    def test_detecta_baseline(self):
        state = inspect_git(PROJECT_ROOT)

        self.assertEqual(
            state.baseline,
            "fase-a-baseline-119tests",
        )

    def test_detecta_estado_del_arbol(self):
        state = inspect_git(PROJECT_ROOT)

        expected_status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        self.assertEqual(
            state.clean,
            not bool(expected_status),
        )

    def test_obtiene_commits_recientes(self):
        state = inspect_git(PROJECT_ROOT)

        self.assertGreaterEqual(
            len(state.recent_commits),
            1,
        )

        expected_head = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        self.assertEqual(
            state.recent_commits[0],
            expected_head,
        )

    def test_obtiene_tags(self):
        state = inspect_git(PROJECT_ROOT)

        self.assertIn(
            "fase-a-baseline-119tests",
            state.tags,
        )


if __name__ == "__main__":
    unittest.main()


class TestTestState(unittest.TestCase):

    def test_ejecuta_suite_real(self):
        from project_state import inspect_tests

        state = inspect_tests(PROJECT_ROOT)

        self.assertEqual(state.total, 122)
        self.assertEqual(state.failed, 0)
        self.assertEqual(state.passed, state.total)
        self.assertTrue(state.success)

    def test_registra_duracion(self):
        from project_state import inspect_tests

        state = inspect_tests(PROJECT_ROOT)

        self.assertGreaterEqual(state.duration, 0.0)

    def test_estado_exitoso_coherente(self):
        from project_state import inspect_tests

        state = inspect_tests(PROJECT_ROOT)

        self.assertEqual(
            state.success,
            state.failed == 0,
        )
