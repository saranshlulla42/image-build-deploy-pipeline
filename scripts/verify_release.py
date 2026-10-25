"""Verify both readiness and the identity embedded in the served artifact."""
import argparse
import json
import time
import urllib.error
import urllib.request


def request_json(url, timeout=3):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError(f"Unexpected HTTP status: {response.status}")
        return json.load(response)


def verify(base_url, expected, timeout=30, interval=1):
    deadline = time.monotonic() + timeout
    last_error = "No verification attempted"
    while True:
        try:
            health = request_json(base_url.rstrip("/") + "/health")
            version = request_json(base_url.rstrip("/") + "/version")
            if not isinstance(health, dict) or not isinstance(version, dict):
                raise ValueError("Expected JSON objects from readiness and version endpoints")
            if health.get("status") != "healthy":
                raise ValueError("Readiness check is not healthy")
            if health.get("version") != expected or version.get("version") != expected:
                raise ValueError("Served version does not match the requested source commit")
            return {"status": "verified", "version": expected}
        except (OSError, ValueError, urllib.error.URLError) as error:
            last_error = str(error)
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Release verification failed: {last_error}")
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.url, args.expected_version, args.timeout)))
    except RuntimeError as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
