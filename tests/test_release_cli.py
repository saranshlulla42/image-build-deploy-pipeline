import subprocess
import sys

import pytest


@pytest.mark.parametrize("context,image,version,extra", [
    ("cloud-demo", "ghcr.io/example/app:mutable", "a" * 40, []),
    ("cloud-demo", "ghcr.io/example/app@sha256:" + "1" * 64, "a" * 40, ["--fault-readiness"]),
    ("kind-demo", "demo-app:local", "not-a-source-commit", ["--allow-local-image"]),
    ("cloud-demo", "demo-app:local", "a" * 40, ["--allow-local-image"]),
])
def test_unsafe_or_ambiguous_release_arguments_are_rejected_before_cluster_access(context, image, version, extra):
    result = subprocess.run([
        sys.executable, "scripts/release.py", "--context", context, "--image", image,
        "--expected-version", version, *extra,
    ], capture_output=True, text=True)
    assert result.returncode == 2
    assert "error:" in result.stderr
    assert "kubectl" not in result.stderr
