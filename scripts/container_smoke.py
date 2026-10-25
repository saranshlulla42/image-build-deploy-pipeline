"""Run the built image with restricted privileges and verify its embedded commit."""
import argparse
import subprocess
import sys

from verify_release import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--expected-version", required=True)
    args = parser.parse_args()
    identifier = subprocess.check_output([
        "docker", "run", "-d", "--read-only", "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "-p", "127.0.0.1::8080", args.image,
    ], text=True).strip()
    try:
        port = subprocess.check_output(["docker", "port", identifier, "8080/tcp"], text=True).strip().split(":")[-1]
        print(verify("http://127.0.0.1:" + port, args.expected_version, timeout=30))
        return 0
    finally:
        subprocess.run(["docker", "logs", identifier], check=False)
        subprocess.run(["docker", "rm", "-f", identifier], check=False)


if __name__ == "__main__":
    sys.exit(main())
