"""Regression guard: the default test suite must not depend on the local, gitignored
data/ directory (see conftest.py's synthetic fixtures). This runs the real suite as a
subprocess with data/ temporarily moved out of the way, proving nothing under
testpaths silently requires data/full/*.jsonl or data/public/*.jsonl to exist -- the
same check CI implicitly relies on, since data/ is gitignored and never present there.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"
THIS_FILE = Path(__file__)


def test_default_suite_passes_without_data_directory():
    backup_dir = None
    if DATA_DIR.exists():
        backup_dir = Path(tempfile.mkdtemp(prefix="paperscope-data-backup-")) / "data"
        shutil.move(str(DATA_DIR), str(backup_dir))

    try:
        assert not DATA_DIR.exists()
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-m", "not integration", "--ignore", str(THIS_FILE)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        if backup_dir is not None:
            shutil.move(str(backup_dir), str(DATA_DIR))
            shutil.rmtree(backup_dir.parent, ignore_errors=True)

    assert result.returncode == 0, (
        f"default suite failed with no data/ directory present\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
