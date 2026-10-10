"""Exercise a running API + worker using synthetic data (no paid API calls)."""

import os
import time
from uuid import uuid4

import httpx


def main() -> None:
    with httpx.Client(
        base_url=os.getenv("BASE_URL", "http://localhost:8000"),
        headers={"Authorization": f"Bearer {os.getenv('API_TOKEN', 'local-development-only')}"},
        timeout=15,
    ) as client:
        client.get("/health/ready").raise_for_status()
        response = client.post("/api/v1/conversations", json={"title": "Smoke-test weekend"})
        response.raise_for_status()
        conversation_id = response.json()["id"]
        client.post(
            f"/api/v1/conversations/{conversation_id}/messages/batch",
            json={
                "messages": [
                    {
                        "external_id": "smoke-1",
                        "author_id": "demo-participant",
                        "sent_at": "2026-07-10T14:30:00Z",
                        "text": "Let's go hiking Saturday, but be back before dinner.",
                    }
                ]
            },
        ).raise_for_status()
        response = client.post(
            f"/api/v1/conversations/{conversation_id}/plan-generations",
            json={"timezone": "America/Los_Angeles"},
            headers={"Idempotency-Key": str(uuid4())},
        )
        response.raise_for_status()
        generation_id = response.json()["id"]
        for _ in range(60):
            response = client.get(f"/api/v1/plan-generations/{generation_id}")
            response.raise_for_status()
            result = response.json()
            if result["status"] == "succeeded":
                break
            if result["status"] == "failed":
                raise RuntimeError(result["error"])
            time.sleep(0.5)
        else:
            raise TimeoutError("Generation did not complete. Is the worker running?")
        plan_url = f"/api/v1/plans/{result['plan_id']}"
        response = client.get(plan_url)
        response.raise_for_status()
        plan = response.json()
        plan["content"]["title"] = "Edited smoke-test plan"
        patch = {"revision": plan["revision"], "content": plan["content"]}
        client.patch(plan_url, json=patch).raise_for_status()
        assert client.patch(plan_url, json=patch).status_code == 409
        print(f"Passed: transcript → queued generation → draft → edit → conflict. Plan: {plan_url}")


if __name__ == "__main__":
    main()
