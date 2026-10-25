"""Small stateless service used to demonstrate verified image releases."""
import json
import os
from pathlib import Path

from flask import Flask, jsonify

BUILD_INFO = Path(__file__).with_name("build-info.json")


def create_app(build_info_path=BUILD_INFO):
    application = Flask(__name__)
    # Image identity comes from a file written during the build, never an env override.
    if Path(build_info_path).exists():
        version = json.loads(Path(build_info_path).read_text())["commit"]
        if not isinstance(version, str) or len(version) != 40 or any(
            char not in "0123456789abcdef" for char in version
        ):
            raise ValueError("Invalid embedded source commit")
    else:
        version = "development"

    @application.get("/")
    def index():
        return jsonify(
            status="success",
            message="Automated image pipeline: verified releases with recovery",
            version=version,
        )

    @application.get("/version")
    def release_version():
        return jsonify(version=version)

    @application.get("/health")
    def readiness():
        if os.getenv("FAIL_HEALTH", "false").lower() == "true":
            return jsonify(status="unhealthy", version=version), 503
        return jsonify(status="healthy", version=version)

    @application.get("/live")
    def liveness():
        # A deliberate readiness failure must not create a restart loop.
        return jsonify(status="alive"), 200

    return application


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080)
