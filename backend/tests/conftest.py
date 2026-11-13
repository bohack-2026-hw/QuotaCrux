import os
import shutil
import subprocess
import tempfile

import pytest

# Isolate all state before routeevo.config is imported.
_TMP = tempfile.mkdtemp(prefix="routeevo-test-")
os.environ["ROUTEEVO_VAR_DIR"] = _TMP


def docker_available() -> bool:
    return shutil.which("docker") is not None and subprocess.run(["docker", "info"], capture_output=True).returncode == 0


requires_docker = pytest.mark.skipif(not docker_available(), reason="docker daemon not available")
