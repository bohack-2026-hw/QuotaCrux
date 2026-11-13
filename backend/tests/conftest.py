import os
import shutil
import subprocess
import tempfile

import pytest

# Isolate all state before routeevo.config is imported.
_TMP = tempfile.mkdtemp(prefix="routeevo-test-")
os.environ["ROUTEEVO_VAR_DIR"] = _TMP
# Tests must never reach a real model: ignore backend/.env and point both providers at a closed port.
os.environ["ROUTEEVO_NO_DOTENV"] = "1"
os.environ["OPENAI_API_KEY"] = "test-no-network"
os.environ["OPENAI_BASE_URL"] = "http://127.0.0.1:9/v1"
os.environ["QWEN_BASE_URL"] = "http://127.0.0.1:9/v1"


def docker_available() -> bool:
    return shutil.which("docker") is not None and subprocess.run(["docker", "info"], capture_output=True).returncode == 0


requires_docker = pytest.mark.skipif(not docker_available(), reason="docker daemon not available")
