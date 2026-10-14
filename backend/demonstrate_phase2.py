"""
Phase 2 Run Engine Demonstration Script.
Demonstrates:
- Creating a Project, Prompt Version, and Test Cases
- Triggering an async evaluation run
- Streaming real-time SSE events
- Processing tests with FakeGeminiClient
- Output caching, token and latency metrics
- Assertions verification
"""
import asyncio
import sys
import time
from app.database import SessionLocal
from app.models.user import User
from app.models.project import Project
from app.models.prompt import Prompt, PromptVersion
from app.models.test_case import TestCase
from app.models.run import Run, RunResult
from app.core.security import get_password_hash
from app.engine.client import FakeGeminiClient
from app.engine.runner import run_engine_executor
from app.engine.events import broadcaster

async def main():
    print("=" * 70)
    print("  PromptCheck Phase 2: Run Engine Live Demonstration")
    print("=" * 70)

    # 1. Setup sample data in database
    with SessionLocal() as db:
        from app.models.run import OutputCache
        db.query(OutputCache).delete()
        db.commit()
        email = f"demo_user_{int(time.time())}@promptcheck.io"
        user = User(
            email=email,
            hashed_password=get_password_hash("password123"),
            full_name="Demo Engineer",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        project = Project(
            name="Customer Support Assistant",
            description="Testing support prompt versions for tone and accuracy",
            user_id=user.id,
            encrypted_gemini_api_key="demo_encrypted_key",
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        prompt = Prompt(
            project_id=project.id,
            name="Support Response Generator",
            description="Generates courteous customer support replies",
        )
        db.add(prompt)
        db.commit()
        db.refresh(prompt)

        template = (
            "You are a friendly customer service agent. Respond politely to customer {{ customer_name }} "
            "regarding product {{ product }} with query: {{ issue }}."
        )
        ts = int(time.time())
        version = PromptVersion(
            prompt_id=prompt.id,
            version_number=1,
            content=template,
            content_hash=f"demo_hash_{ts}",
        )
        db.add(version)
        db.commit()
        db.refresh(version)

        # Create 5 test cases
        test_cases_data = [
            {
                "name": "Refund Inquiry",
                "inputs": {"customer_name": "Alice", "product": "Pro Headphones", "issue": "damaged delivery"},
                "assertions": [
                    {"type": "contains", "value": "Alice"},
                    {"type": "contains", "value": "refund"},
                ],
                "expected": "Hello Alice, I apologize for the damaged Pro Headphones. We will process your refund immediately.",
            },
            {
                "name": "Shipping Delay",
                "inputs": {"customer_name": "Bob", "product": "Smart Watch", "issue": "order delayed"},
                "assertions": [
                    {"type": "contains", "value": "Bob"},
                    {"type": "starts_with", "value": "Dear"},
                ],
                "expected": "Dear Bob, thank you for reaching out. We apologize for the delay with your Smart Watch.",
            },
            {
                "name": "Warranty Request",
                "inputs": {"customer_name": "Charlie", "product": "Keyboard", "issue": "key sticking"},
                "assertions": [
                    {"type": "contains", "value": "warranty"},
                    {"type": "not_contains", "value": "unavailable"},
                ],
                "expected": "Hello Charlie, we are happy to help replace your Keyboard under our warranty terms.",
            },
            {
                "name": "Billing Question",
                "inputs": {"customer_name": "Diana", "product": "Subscription", "issue": "double charge"},
                "assertions": [
                    {"type": "contains", "value": "Diana"},
                    {"type": "regex", "value": r"credited back|refunded"},
                ],
                "expected": "Hello Diana, we noticed the billing anomaly. The duplicate amount has been credited back.",
            },
            {
                "name": "Feature Request",
                "inputs": {"customer_name": "Evan", "product": "Mobile App", "issue": "dark mode request"},
                "assertions": [
                    {"type": "contains", "value": "dark mode"},
                    {"type": "max_length", "value": 150},
                ],
                "expected": "Hi Evan, thanks for recommending dark mode! It will be available in the upcoming release.",
            },
        ]

        test_ids = []
        for tcd in test_cases_data:
            tc = TestCase(
                project_id=project.id,
                name=tcd["name"],
                inputs=tcd["inputs"],
                assertions=tcd["assertions"],
                is_active=True,
            )
            db.add(tc)
            db.commit()
            db.refresh(tc)
            test_ids.append((tc.id, tcd["expected"]))

        # Create the Run
        run = Run(
            project_id=project.id,
            prompt_version_id=version.id,
            status="queued",
            total_tests=len(test_ids),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        project_name = project.name
        project_id = project.id
        version_hash = version.content_hash
        run_id = run.id
        run_status = run.status

    print(f"\n[+] Project Created: '{project_name}' (ID: {project_id})")
    print(f"[+] Prompt Version Created: v1 (Hash: {version_hash})")
    print(f"[+] Active Test Cases: {len(test_ids)}")
    print(f"[+] Run Enqueued: Run #{run_id} (Status: {run_status})\n")

    # 2. Configure FakeGeminiClient
    client = FakeGeminiClient(simulated_latency_ms=18.5)
    for tcd in test_cases_data:
        # Map customer name to test case expected response
        client.set_response_for_prompt(tcd["inputs"]["customer_name"], tcd["expected"])

    # 3. Setup SSE listener in background task
    queue = await broadcaster.subscribe(run_id)

    async def sse_listener():
        print("--- [SSE STREAM OPENED: /api/runs/{}/stream] ---".format(run_id))
        while True:
            msg = await queue.get()
            event = msg.get("event")
            data = msg.get("data", {})
            if event == "run_started":
                print(f"  [SSE event: run_started]  Run {data['run_id']} started (Total tests: {data['total_tests']})")
            elif event == "test_result":
                status_icon = "[PASSED]" if data.get("status") == "passed" else "[FAILED]"
                print(
                    f"  [SSE event: test_result]  Test '{data.get('test_case_name')}' -> {status_icon} | "
                    f"Latency: {data.get('latency_ms')}ms | Tokens: {data.get('total_tokens')}"
                )
            elif event == "run_progress":
                print(f"  [SSE event: run_progress] Completed: {data.get('completed')}/{data.get('total')} | Passed: {data.get('passed')} | Failed: {data.get('failed')}")
            elif event == "run_completed":
                print(f"  [SSE event: run_completed] Run {data['run_id']} finished successfully!")
                break
            elif event in ("run_failed", "run_cancelled"):
                print(f"  [SSE event: {event}] Run terminated with event {event}")
                break
        await broadcaster.unsubscribe(run_id, queue)
        print("--- [SSE STREAM CLOSED] ---\n")

    listener_task = asyncio.create_task(sse_listener())

    # 4. Execute the Run using the Run Engine
    await run_engine_executor(
        run_id=run_id,
        client=client,
        max_concurrency=4,
        requests_per_minute=60,
    )

    await listener_task

    # 5. Retrieve Final Summary Metrics from Database
    with SessionLocal() as db:
        from sqlalchemy.orm import joinedload

        final_run = db.query(Run).filter(Run.id == run_id).first()
        results = (
            db.query(RunResult)
            .options(joinedload(RunResult.test_case))
            .filter(RunResult.run_id == run_id)
            .all()
        )

        print("=" * 70)
        print("  EVALUATION RUN REPORT SUMMARY")
        print("=" * 70)
        print(f"  Run ID           : {final_run.id}")
        print(f"  Final Status     : {final_run.status.upper()}")
        print(f"  Total Tests      : {final_run.total_tests}")
        print(f"  Passed Tests     : {final_run.passed_tests}")
        print(f"  Failed Tests     : {final_run.failed_tests}")
        pass_rate = (final_run.passed_tests / final_run.total_tests) * 100
        print(f"  Pass Rate        : {pass_rate:.1f}%")
        print(f"  Started At       : {final_run.started_at}")
        print(f"  Completed At     : {final_run.completed_at}")
        print("-" * 70)
        print("  INDIVIDUAL TEST RESULTS & METRICS:")
        print("-" * 70)
        total_tokens = 0
        total_latency = 0.0
        for r in results:
            total_tokens += r.total_tokens
            total_latency += r.latency_ms
            tc_name = r.test_case.name if r.test_case else f"Test #{r.test_case_id}"
            print(f"  * {tc_name:<20} | Status: {r.status.upper():<6} | Tokens: {r.total_tokens:<3} (Prompt: {r.prompt_tokens}, Output: {r.completion_tokens}) | Latency: {r.latency_ms:.1f}ms")
            print(f"    Rendered: \"{r.rendered_prompt}\"")
            print(f"    Output  : \"{r.output}\"")
            print(f"    Pass Checks: {r.assertion_results}\n")

        avg_latency = total_latency / len(results) if results else 0
        print("-" * 70)
        print(f"  Total Prompt + Completion Tokens Consumed : {total_tokens}")
        print(f"  Average Execution Latency                 : {avg_latency:.2f}ms")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
