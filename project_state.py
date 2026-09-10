from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess


@dataclass(frozen=True)
class GitState:
    branch: str
    commit: str
    clean: bool
    recent_commits: tuple[str, ...]
    tags: tuple[str, ...]
    baseline: str | None


def _git(project_path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def inspect_git(project_path: Path) -> GitState:
    project_path = Path(project_path).resolve()

    branch = _git(project_path, "branch", "--show-current")
    commit = _git(project_path, "rev-parse", "HEAD")

    status = _git(project_path, "status", "--porcelain")
    clean = not bool(status)

    log_output = _git(
        project_path,
        "log",
        "--oneline",
        "-5",
    )

    recent_commits = tuple(
        line for line in log_output.splitlines()
        if line.strip()
    )

    tags_output = _git(
        project_path,
        "tag",
        "--list",
    )

    tags = tuple(
        line for line in tags_output.splitlines()
        if line.strip()
    )

    baseline_candidates = [
        tag
        for tag in tags
        if "baseline" in tag.lower()
    ]

    baseline = baseline_candidates[-1] if baseline_candidates else None

    return GitState(
        branch=branch,
        commit=commit,
        clean=clean,
        recent_commits=recent_commits,
        tags=tags,
        baseline=baseline,
    )


@dataclass(frozen=True)
class TestState:
    total: int
    passed: int
    failed: int
    duration: float
    success: bool


def inspect_tests(project_path: Path) -> TestState:
    project_path = Path(project_path).resolve()

    # Evita recursión cuando ProjectState es probado por la propia
    # suite que inspect_tests() ejecuta.
    if os.environ.get("PROJECT_STATE_RUNNING_TESTS") == "1":
        return TestState(
            total=0,
            passed=0,
            failed=0,
            duration=0.0,
            success=False,
        )

    env = os.environ.copy()
    env["PROJECT_STATE_RUNNING_TESTS"] = "1"

    try:
        result = subprocess.run(
            [
                "python",
                "-m",
                "pytest",
                "-q",
                "--ignore=test_project_state.py",
            ],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return TestState(
            total=0,
            passed=0,
            failed=1,
            duration=60.0,
            success=False,
        )

    output = result.stdout + "\n" + result.stderr

    total = 0
    passed = 0
    failed = 0
    duration = 0.0

    for line in output.splitlines():
        stripped = line.strip()

        if "passed" in stripped or "failed" in stripped:
            parts = stripped.replace(",", "").split()

            for index, part in enumerate(parts):
                if part.isdigit() and index + 1 < len(parts):
                    value = int(part)
                    label = parts[index + 1]

                    if label.startswith("passed"):
                        passed = value
                    elif label.startswith("failed"):
                        failed = value

        if " in " in stripped and "s" in stripped:
            try:
                before = stripped.split(" in ", 1)[1]
                duration_text = before.split("s", 1)[0].strip()
                duration = float(duration_text)
            except (ValueError, IndexError):
                pass

    total = passed + failed

    return TestState(
        total=total,
        passed=passed,
        failed=failed,
        duration=duration,
        success=result.returncode == 0 and failed == 0,
    )
