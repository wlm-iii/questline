"""Exercise running API + worker with fixture endpoints and synthetic data."""

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
        response = client.post(
            "/api/v1/trips",
            json={
                "name": "Smoke-test weekend",
                "origin": "San Jose, CA",
                "destination": "Big Sur, CA",
                "start_date": "2026-10-17",
                "end_date": "2026-10-18",
                "timezone": "America/Los_Angeles",
                "organizer_name": "Demo participant",
            },
        )
        response.raise_for_status()
        trip_id = response.json()["trip"]["id"]
        client.post(
            f"/api/v1/trips/{trip_id}/messages/batch",
            json={
                "messages": [
                    {
                        "external_id": "smoke-1",
                        "author_id": "demo-participant",
                        "sent_at": "2026-10-10T14:30:00Z",
                        "text": "Let's go hiking Saturday.",
                    }
                ]
            },
        ).raise_for_status()
        response = client.post(
            f"/api/v1/trips/{trip_id}/plan-generations",
            json={"budget_preset": "comfortable"},
            headers={"Idempotency-Key": str(uuid4())},
        )
        response.raise_for_status()
        generation_id = response.json()["generation"]["id"]
        for _ in range(60):
            response = client.get(f"/api/v1/plan-generations/{generation_id}")
            response.raise_for_status()
            result = response.json()["generation"]
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
        plan = response.json()["plan"]
        plan["content"]["title"] = "Edited smoke-test plan"
        patch = {"revision": plan["revision"], "content": plan["content"]}
        client.patch(plan_url, json=patch).raise_for_status()
        assert client.patch(plan_url, json=patch).status_code == 409
        print(f"Passed: trip → messages → queued generation → draft → edit → conflict. {plan_url}")


if __name__ == "__main__":
    main()
