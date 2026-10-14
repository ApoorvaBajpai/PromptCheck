"""
Phase 2 Real Gemini API Run Demonstration Script.
Demonstrates:
- Storing encrypted Gemini API key at rest
- Executing an evaluation run against the live Google Gemini API
- Real-time SSE streaming of live LLM generation events
- Real token counts and round-trip API latencies
- Sandboxed prompt rendering and assertion evaluations
"""

import asyncio
import os
import sys
import time

from app.core.security import encrypt_api_key, get_password_hash
from app.database import SessionLocal
from app.engine.client import GeminiClient
from app.engine.events import broadcaster
from app.engine.runner import run_engine_executor
from app.models.project import Project
from app.models.prompt import Prompt, PromptVersion
from app.models.run import OutputCache, Run, RunResult
from app.models.test_case import TestCase
from app.models.user import User


async def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[!] ERROR: GEMINI_API_KEY environment variable is not set.")
        sys.exit(1)

    print("=" * 70)
    print("  PromptCheck Phase 2: Live Gemini API Evaluation Demonstration")
    print("=" * 70)

    with SessionLocal() as db:
        # Clear previous demo cache to ensure live network API calls
        db.query(OutputCache).delete()
        db.commit()

        email = f"real_gemini_user_{int(time.time())}@promptcheck.io"
        user = User(
            email=email,
            hashed_password=get_password_hash("password123"),
            full_name="AI Evaluation Engineer",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Invariant 5: Encrypt Gemini API key at rest
        encrypted_key = encrypt_api_key(api_key)

        project = Project(
            name="Polyglot Translation Prompt",
            description="Testing multilingual translation prompt versions with Google Gemini",
            user_id=user.id,
            encrypted_gemini_api_key=encrypted_key,
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        prompt = Prompt(
            project_id=project.id,
            name="Translator Prompt",
            description="Prompt to produce clean translations without filler words",
        )
        db.add(prompt)
        db.commit()
        db.refresh(prompt)

        template = (
            "Translate the following phrase into {{ target_language }}. "
            "Output ONLY the translated text in plain text, with no extra commentary: {{ text }}"
        )
        ts = int(time.time())
        version = PromptVersion(
            prompt_id=prompt.id,
            version_number=1,
            content=template,
            content_hash=f"gemini_real_hash_{ts}",
        )
        db.add(version)
        db.commit()
        db.refresh(version)

        # 3 Real test cases
        test_cases_defs = [
            {
                "name": "Spanish Translation",
                "inputs": {"target_language": "Spanish", "text": "Thank you very much"},
                "assertions": [
                    {"type": "contains", "value": "gracias"},
                    {"type": "not_contains", "value": "translation:"},
                ],
            },
            {
                "name": "German Translation",
                "inputs": {"target_language": "German", "text": "Good morning"},
                "assertions": [
                    {"type": "contains", "value": "Guten Morgen"},
                    {"type": "max_length", "value": 50},
                ],
            },
            {
                "name": "French Translation",
                "inputs": {"target_language": "French", "text": "Hello, how are you?"},
                "assertions": [
                    {
                        "type": "regex",
                        "value": r"[Bb]onjour|[Cc]omment allez-vous|[Cc]omment vas-tu|[Cc]a va",
                    },
                ],
            },
        ]

        test_ids = []
        for tc_def in test_cases_defs:
            tc = TestCase(
                project_id=project.id,
                name=tc_def["name"],
                inputs=tc_def["inputs"],
                assertions=tc_def["assertions"],
                is_active=True,
            )
            db.add(tc)
            db.commit()
            db.refresh(tc)
            test_ids.append(tc.id)

        # Create evaluation run
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

    # Mask key for display to maintain zero plaintext key exposure
    masked_key = api_key[:4] + "..." + api_key[-4:]
    print(f"\n[+] Project Created: '{project_name}' (ID: {project_id})")
    print(f"[+] Encrypted Gemini API Key Stored at Rest: {encrypted_key[:24]}...")
    print(f"[+] Active Live Gemini Key: {masked_key}")
    print(f"[+] Prompt Version Created: v1 (Hash: {version_hash})")
    print(f"[+] Active Test Cases: {len(test_ids)}")
    print(f"[+] Run Enqueued: Run #{run_id} (Status: {run_status})\n")

    # Instantiate real Gemini client
    client = GeminiClient(api_key=api_key)

    # SSE Event Streaming Listener
    queue = await broadcaster.subscribe(run_id)

    async def sse_listener():
        print(f"--- [REAL-TIME SSE STREAM OPENED: /api/runs/{run_id}/stream] ---")
        while True:
            msg = await queue.get()
            event = msg.get("event")
            data = msg.get("data", {})
            if event == "run_started":
                r_id = data["run_id"]
                n_tests = data["total_tests"]
                print(f"  [SSE event: run_started]  Run {r_id} started (Total: {n_tests})")
            elif event == "test_result":
                status_icon = "[PASSED]" if data.get("status") == "passed" else "[FAILED]"
                tc_n = data.get("test_case_name")
                lat = data.get("latency_ms")
                tok = data.get("total_tokens")
                print(f"  [SSE event: test_result]  Test '{tc_n}' -> {status_icon} | {lat}ms | {tok}tok")
            elif event == "run_progress":
                c = data.get("completed")
                tot = data.get("total")
                p = data.get("passed")
                f = data.get("failed")
                print(f"  [SSE event: run_progress] Completed: {c}/{tot} | Passed: {p} | Failed: {f}")
            elif event == "run_completed":
                print(f"  [SSE event: run_completed] Run {data['run_id']} finished successfully!")
                break
            elif event in ("run_failed", "run_cancelled"):
                print(f"  [SSE event: {event}] Run terminated with event {event}")
                break
        await broadcaster.unsubscribe(run_id, queue)
        print("--- [REAL-TIME SSE STREAM CLOSED] ---\n")

    listener_task = asyncio.create_task(sse_listener())

    # Execute evaluation run against live Gemini API
    await run_engine_executor(
        run_id=run_id,
        client=client,
        max_concurrency=3,
        requests_per_minute=60,
    )

    await listener_task

    # Summary Report
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
        print("  LIVE GEMINI RUN REPORT SUMMARY")
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
        print("  LIVE GEMINI API TEST OUTPUTS & ASSERTIONS:")
        print("-" * 70)
        total_tokens = 0
        total_latency = 0.0
        for r in results:
            total_tokens += r.total_tokens
            total_latency += r.latency_ms
            tc_name = r.test_case.name if r.test_case else f"Test #{r.test_case_id}"
            clean_output = (r.output or "").encode("ascii", "replace").decode("ascii").strip()
            tok_info = f"Tokens: {r.total_tokens} (P: {r.prompt_tokens}, C: {r.completion_tokens})"
            print(
                f"  * {tc_name:<22} | Status: {r.status.upper():<6} | "
                f"{tok_info} | Latency: {r.latency_ms:.1f}ms"
            )
            print(f'    Live Output : "{clean_output}"')
            print(f"    Assertions  : {r.assertion_results}\n")

        avg_latency = total_latency / len(results) if results else 0
        print("-" * 70)
        print(f"  Total Prompt + Completion Tokens Consumed : {total_tokens}")
        print(f"  Average Live API Latency                  : {avg_latency:.2f}ms")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
