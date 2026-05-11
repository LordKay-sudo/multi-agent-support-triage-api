from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import warnings
from pathlib import Path
from typing import Any
from urllib import request

warnings.filterwarnings(
    "ignore",
    message="The default value of `allowed_objects` will change in a future version.*",
)
warnings.simplefilter("ignore")

DEFAULT_PAYLOAD_PATH = Path("examples/support_ticket.json")
API_PREFIX = "/api/v1"


def load_payload(path: Path = DEFAULT_PAYLOAD_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_in_process_demo(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the API flow without starting uvicorn; ideal for local demos and CI."""

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    create_response = client.post(f"{API_PREFIX}/tickets", json=payload)
    create_response.raise_for_status()
    ticket_id = create_response.json()["id"]

    triage_response = client.post(f"{API_PREFIX}/tickets/{ticket_id}/triage")
    triage_response.raise_for_status()
    return summarize_triage_response(triage_response.json())


def run_remote_demo(base_url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Run the same flow against a live FastAPI instance."""

    normalized_base_url = base_url.rstrip("/")
    create_body = _post_json(f"{normalized_base_url}{API_PREFIX}/tickets", payload)
    ticket_id = create_body["id"]

    triage_body = _post_json(f"{normalized_base_url}{API_PREFIX}/tickets/{ticket_id}/triage", {})
    return summarize_triage_response(triage_body)


def summarize_triage_response(body: dict[str, Any]) -> dict[str, Any]:
    report = body["report"]
    return {
        "ticket_id": body["id"],
        "status": body["status"],
        "category": report["category"],
        "priority": report["priority"],
        "confidence": report["confidence"],
        "escalate": report["escalate"],
        "rationale": report["rationale"],
        "workflow_path": report["workflow_path"],
        "recommended_actions": report["recommended_actions"],
        "draft_response": report["draft_response"],
        "trace_id": report["trace_id"],
    }


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    http_request = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(http_request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a support ticket through the multi-agent triage API.",
    )
    parser.add_argument(
        "--payload",
        type=Path,
        default=DEFAULT_PAYLOAD_PATH,
        help="Path to a JSON support ticket payload.",
    )
    parser.add_argument(
        "--base-url",
        help="Optional live API base URL, for example http://localhost:8000.",
    )
    return parser.parse_args()


def main() -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    args = parse_args()
    payload = load_payload(args.payload)
    if args.base_url:
        result = run_remote_demo(args.base_url, payload)
    else:
        with contextlib.redirect_stderr(io.StringIO()):
            result = run_in_process_demo(payload)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
