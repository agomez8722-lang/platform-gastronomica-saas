from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
import stat
import subprocess
from typing import Iterator, Set, Tuple

@dataclass(frozen=True)
class GitState:
    branch: str
    commit: str
    clean: bool
    recent_commits: tuple[str,...]
    tags: tuple[str,...]
    baseline: str | None

def _git(project_path: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=project_path, capture_output=True, text=True, check=True)
    return result.stdout.strip()

def inspect_git(project_path: Path) -> GitState:
    project_path = Path(project_path).resolve()
    branch = _git(project_path, "branch", "--show-current")
    commit = _git(project_path, "rev-parse", "HEAD")
    status = _git(project_path, "status", "--porcelain")
    clean = not bool(status)
    log_output = _git(project_path, "log", "--oneline", "-5")
    recent_commits = tuple(line for line in log_output.splitlines() if line.strip())
    tags_output = _git(project_path, "tag", "--list")
    tags = tuple(line for line in tags_output.splitlines() if line.strip())
    baseline_candidates = [tag for tag in tags if "baseline" in tag.lower()]
    baseline = baseline_candidates[-1] if baseline_candidates else None
    return GitState(branch=branch, commit=commit, clean=clean, recent_commits=recent_commits, tags=tags, baseline=baseline)

@dataclass(frozen=True)
class TestState:
    total: int
    passed: int
    failed: int
    duration: float
    success: bool

def inspect_tests(project_path: Path) -> TestState:
    project_path = Path(project_path).resolve()
    if os.environ.get("PROJECT_STATE_RUNNING_TESTS") == "1":
        return TestState(total=0, passed=0, failed=0, duration=0.0, success=False)
    env = os.environ.copy()
    env["PROJECT_STATE_RUNNING_TESTS"] = "1"
    try:
        result = subprocess.run(["python","-m","pytest","-q","--ignore=test_project_state.py"], cwd=project_path, capture_output=True, text=True, timeout=60, env=env)
    except subprocess.TimeoutExpired:
        return TestState(total=0, passed=0, failed=1, duration=60.0, success=False)
    output = result.stdout + "\n" + result.stderr
    total=passed=failed=0
    duration=0.0
    for line in output.splitlines():
        stripped=line.strip()
        if "passed" in stripped or "failed" in stripped:
            parts=stripped.replace(",","").split()
            for index, part in enumerate(parts):
                if part.isdigit() and index+1 < len(parts):
                    value=int(part); label=parts[index+1]
                    if label.startswith("passed"): passed=value
                    elif label.startswith("failed"): failed=value
        if " in " in stripped and "s" in stripped:
            try:
                before=stripped.split(" in ",1)[1]
                duration_text=before.split("s",1)[0].strip()
                duration=float(duration_text)
            except (ValueError, IndexError): pass
    total=passed+failed
    return TestState(total=total, passed=passed, failed=failed, duration=duration, success=result.returncode==0 and failed==0)

# ===== FASE2: BACKUP SEGURO - detectar symlinks, no seguir fuera de raiz, evitar bucle =====
def _is_symlink(p: Path) -> bool:
    try:
        return stat.S_ISLNK(os.lstat(p).st_mode)
    except FileNotFoundError:
        return False

def safe_resolve(path: Path, root: Path) -> Path:
    root = root.resolve()
    visited: Set[Tuple[int,int]] = set()
    cur = path
    for _ in range(40):
        try:
            st = os.lstat(cur)
        except FileNotFoundError:
            break
        if not stat.S_ISLNK(st.st_mode):
            break
        key = (st.st_dev, st.st_ino)
        if key in visited:
            raise ValueError(f"Bucle de enlace simbólico detectado: {path}")
        visited.add(key)
        try:
            link_target = os.readlink(cur)
        except OSError:
            break
        if not os.path.isabs(link_target):
            cur = (cur.parent / link_target)
        else:
            cur = Path(link_target)
        try:
            cur_resolved = cur.resolve()
            cur_resolved.relative_to(root)
        except ValueError:
            raise ValueError(f"Ruta fuera del proyecto: {path}")
        except RuntimeError:
            raise ValueError(f"Bucle de enlace simbólico detectado: {path}")
    try:
        final = cur.resolve()
    except RuntimeError:
        raise ValueError(f"Bucle de enlace simbólico detectado: {path}")
    return final

def ruta_segura_standalone(root: Path, relativa: str) -> Path:
    if not isinstance(relativa, str):
        raise ValueError("La ruta debe ser texto.")
    relativa=relativa.strip()
    if not relativa:
        raise ValueError("Ruta vacía.")
    root_res=root.resolve()
    actual=root_res
    visited: Set[Tuple[int,int]] = set()
    for part in Path(relativa).parts:
        if part in ("/",""): continue
        if part==".":
            continue
        if part=="..":
            actual=actual.parent
            try:
                actual.relative_to(root_res)
            except ValueError:
                raise ValueError(f"Ruta fuera del proyecto: {relativa}")
            continue
        actual=actual/part
        try:
            st=os.lstat(actual)
            if stat.S_ISLNK(st.st_mode):
                key=(st.st_dev, st.st_ino)
                if key in visited:
                    raise ValueError(f"Bucle de enlace simbólico detectado: {relativa}")
                visited.add(key)
                try:
                    real=actual.resolve()
                except RuntimeError:
                    raise ValueError(f"Bucle de enlace simbólico detectado: {relativa}")
                try:
                    real.relative_to(root_res)
                except ValueError:
                    raise ValueError(f"Ruta fuera del proyecto: {relativa}")
                raise ValueError(f"No se permiten enlaces simbólicos: {relativa}")
        except FileNotFoundError:
            continue
    candidato=(root_res/relativa).resolve()
    try:
        candidato.relative_to(root_res)
    except ValueError:
        raise ValueError(f"Ruta fuera del proyecto: {relativa}")
    except RuntimeError:
        raise ValueError(f"Bucle de enlace simbólico detectado: {relativa}")
    return candidato

def walk_safe(root: Path) -> Iterator[Path]:
    root=root.resolve()
    visited_dirs: Set[Tuple[int,int]] = set()
    stack=[root]
    while stack:
        cur=stack.pop()
        try:
            st=os.lstat(cur)
            key=(st.st_dev, st.st_ino)
            if key in visited_dirs:
                continue
            visited_dirs.add(key)
        except FileNotFoundError:
            continue
        try:
            with os.scandir(cur) as it:
                for entry in it:
                    try:
                        entry.stat(follow_symlinks=False)
                    except FileNotFoundError:
                        continue
                    full=Path(entry.path)
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(full)
                    else:
                        try:
                            full.resolve().relative_to(root)
                            yield full
                        except ValueError:
                            continue
                        except RuntimeError:
                            continue
        except PermissionError:
            continue
