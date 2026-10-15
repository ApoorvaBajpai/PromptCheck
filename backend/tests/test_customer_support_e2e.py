import time

import pytest

from app.database import SessionLocal
from app.engine.client import FakeGeminiClient
from app.engine.runner import run_engine_executor
from app.models.project import Project
from app.models.prompt import Prompt, PromptVersion
from app.models.run import Run, RunResult
from app.models.test_case import TestCase
from app.models.user import User


@pytest.mark.asyncio
async def test_customer_support_qa_bot_acceptance_scenario():
    """
    Final Acceptance Scenario (Section 24):
    Customer Support QA Bot
    - Prompt v1 (Correct policies: 30 days, original payment method, before shipment, 3-5 days delivery)
    - 10 test cases
    - Run v1 -> 100% pass -> Set as baseline
    - Prompt v2 (Broken: 14 days, store credit only -> causes 2 regressions)
    - Run v2 -> 80% pass, 2 regressions detected with old vs new outputs & evaluator reasons
    - Prompt v3 (Fixed) -> Run v3 -> regressions resolved (2 improvements, 0 regressions)
    - Promote v3 to baseline
    - Verify full history available
    """
    with SessionLocal() as db:
        # 1. Setup User and Project
        unique_suffix = int(time.time() * 1000)
        user = User(email=f"support_lead_{unique_suffix}@example.com", hashed_password="pw")
        db.add(user)
        db.commit()
        db.refresh(user)

        project = Project(
            user_id=user.id,
            name="Customer Support QA Bot",
            description="Regression testing suite for Customer Support Agent",
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        project_id = project.id

        # 2. Define 10 Test Cases with Clear Assertions
        test_cases_defs = [
            ("Return Window", "What is the return window?", [{"type": "contains", "value": "30 days"}]),
            ("Refund Method", "How will I receive my refund?", [{"type": "contains", "value": "original payment method"}]),
            ("Cancellation Timing", "Can I cancel my order?", [{"type": "contains", "value": "before shipment"}]),
            ("Delivery Timeframe", "How long does shipping take?", [{"type": "contains", "value": "3-5 business days"}]),
            ("Return Policy Overview", "Tell me about returns", [{"type": "contains", "value": "returns"}]),
            ("Tracking Inquiry", "Where is my package?", [{"type": "length", "min": 10}]),
            ("Late Cancellation", "My order already shipped, can I cancel?", [{"type": "length", "min": 10}]),
            ("Refund Processing Time", "When will my money arrive?", [{"type": "length", "min": 10}]),
            ("Return Label", "Do you provide return labels?", [{"type": "length", "min": 10}]),
            ("General Support Inquiries", "What are your business hours?", [{"type": "length", "min": 10}]),
        ]

        created_tcs = []
        for name, question, assertions in test_cases_defs:
            tc = TestCase(
                project_id=project_id,
                name=name,
                inputs={"question": question},
                assertions=assertions,
            )
            db.add(tc)
            db.commit()
            db.refresh(tc)
            created_tcs.append(tc.id)

        # 3. Create Prompt Container
        prompt = Prompt(
            project_id=project_id,
            name="Support Agent Instructions",
            description="Core prompt instructions for customer service representative",
        )
        db.add(prompt)
        db.commit()
        db.refresh(prompt)
        prompt_id = prompt.id

        # 4. Prompt Version 1
        v1_content = """
        You are a customer support agent.
        Knowledge base:
        - Returns are accepted within 30 days of purchase.
        - Refunds are always issued to the original payment method.
        - Order cancellation is only allowed before shipment.
        - Standard delivery takes 3-5 business days.
        Answer the customer question: {{ question }}
        """
        v1 = PromptVersion(
            prompt_id=prompt_id,
            version_number=1,
            content=v1_content,
            content_hash=f"hash_v1_{unique_suffix}",
        )
        db.add(v1)
        db.commit()
        db.refresh(v1)
        v1_id = v1.id

    # Configure Fake Gemini Client for v1 (passes all 10 tests)
    client_v1 = FakeGeminiClient()
    client_v1.set_response(
        "What is the return window?",
        "Our return policy allows returns within 30 days of purchase in original condition."
    )
    client_v1.set_response(
        "How will I receive my refund?",
        "All approved refunds are credited back to your original payment method within 5 days."
    )
    client_v1.set_response(
        "Can I cancel my order?",
        "You may cancel your order at any time before shipment begins."
    )
    client_v1.set_response(
        "How long does shipping take?",
        "Standard shipping takes 3-5 business days to arrive at your address."
    )
    client_v1.set_response(
        "Tell me about returns",
        "We accept customer returns within 30 days of delivery."
    )

    # Create and Execute Run 1
    with SessionLocal() as db:
        run1 = Run(
            project_id=project_id,
            prompt_version_id=v1_id,
            status="running",
        )
        db.add(run1)
        db.commit()
        db.refresh(run1)
        run1_id = run1.id

    await run_engine_executor(run_id=run1_id, client=client_v1)

    with SessionLocal() as db:
        r1 = db.query(Run).filter(Run.id == run1_id).first()
        assert r1.status == "completed"
        assert r1.total_tests == 10
        assert r1.passed_tests == 10
        assert r1.failed_tests == 0
        assert (r1.passed_tests / r1.total_tests) == 1.0

        # Mark Run 1 as Project Baseline
        r1.is_baseline = True
        db.commit()

    # 5. Prompt Version 2 (Intentionally regress 2 policies: 14 days & store credit)
    v2_content = """
    You are a customer support agent.
    Knowledge base:
    - Returns are only accepted within 14 days of purchase.
    - Refunds are issued as store credit vouchers only.
    - Order cancellation is only allowed before shipment.
    - Standard delivery takes 3-5 business days.
    Answer the customer question: {{ question }}
    """
    with SessionLocal() as db:
        v2 = PromptVersion(
            prompt_id=prompt_id,
            version_number=2,
            content=v2_content,
            content_hash=f"hash_v2_{unique_suffix}",
        )
        db.add(v2)
        db.commit()
        db.refresh(v2)
        v2_id = v2.id

    # Configure Fake Gemini Client for v2 (returns 14 days and store credit -> breaks TC1 & TC2)
    client_v2 = FakeGeminiClient()
    client_v2.set_response(
        "What is the return window?",
        "Our updated policy requires returns within 14 days only."
    )
    client_v2.set_response(
        "How will I receive my refund?",
        "Refunds are now processed exclusively as store credit."
    )
    client_v2.set_response(
        "Can I cancel my order?",
        "You may cancel your order at any time before shipment begins."
    )
    client_v2.set_response(
        "How long does shipping take?",
        "Standard shipping takes 3-5 business days to arrive at your address."
    )
    client_v2.set_response(
        "Tell me about returns",
        "We accept customer returns within 14 days of delivery."
    )

    # Create and Execute Run 2
    with SessionLocal() as db:
        run2 = Run(
            project_id=project_id,
            prompt_version_id=v2_id,
            status="running",
        )
        db.add(run2)
        db.commit()
        db.refresh(run2)
        run2_id = run2.id

    await run_engine_executor(run_id=run2_id, client=client_v2, enable_cache=False)

    with SessionLocal() as db:
        r2 = db.query(Run).filter(Run.id == run2_id).first()
        assert r2.status == "completed"
        assert r2.total_tests == 10
        assert r2.passed_tests == 8
        assert r2.failed_tests == 2
        assert (r2.passed_tests / r2.total_tests) == 0.8

        # Verify Regression Analysis on Run 2
        summary = r2.summary
        assert summary is not None
        assert summary.get("baseline_run_id") == run1_id
        assert summary.get("regressions") == 2
        assert summary.get("unchanged") == 8
        assert summary.get("improvements") == 0
        assert summary.get("verdict") == "regression"
        assert summary.get("has_regressions") is True

        # Verify that the two intentionally broken tests are flagged as regressions with full diff
        results_v2 = db.query(RunResult).filter(RunResult.run_id == run2_id).all()
        regressed_results = [r for r in results_v2 if r.classification == "regression"]
        assert len(regressed_results) == 2

        regressed_tc_ids = {r.test_case_id for r in regressed_results}
        assert created_tcs[0] in regressed_tc_ids  # TC1: Return Window
        assert created_tcs[1] in regressed_tc_ids  # TC2: Refund Method

        for reg_res in regressed_results:
            # Check failed assertion reasons are visible
            assert len(reg_res.assertion_results) > 0
            failed_assert = [a for a in reg_res.assertion_results if not a["passed"]]
            assert len(failed_assert) > 0
            assert "reason" in failed_assert[0]

    # 6. Prompt Version 3 (Fix the policies back to 30 days & original payment method)
    v3_content = """
    You are a customer support agent.
    Knowledge base:
    - Returns are accepted within 30 days of purchase.
    - Refunds are always issued to the original payment method.
    - Order cancellation is only allowed before shipment.
    - Standard delivery takes 3-5 business days.
    Answer the customer question: {{ question }}
    """
    with SessionLocal() as db:
        v3 = PromptVersion(
            prompt_id=prompt_id,
            version_number=3,
            content=v3_content,
            content_hash=f"hash_v3_{unique_suffix}",
        )
        db.add(v3)
        db.commit()
        db.refresh(v3)
        v3_id = v3.id

    # Execute Run 3 using client_v1 (fixed responses)
    with SessionLocal() as db:
        run3 = Run(
            project_id=project_id,
            prompt_version_id=v3_id,
            status="running",
        )
        db.add(run3)
        db.commit()
        db.refresh(run3)
        run3_id = run3.id

    await run_engine_executor(run_id=run3_id, client=client_v1, enable_cache=False)

    with SessionLocal() as db:
        r3 = db.query(Run).filter(Run.id == run3_id).first()
        assert r3.status == "completed"
        assert r3.total_tests == 10
        assert r3.passed_tests == 10
        assert r3.failed_tests == 0
        assert (r3.passed_tests / r3.total_tests) == 1.0

        # Verify Regressions Resolved (Run 3 compared against baseline Run 1)
        summary3 = r3.summary
        assert summary3.get("regressions") == 0
        assert summary3.get("has_regressions") is False

        # 7. Promote Run 3 to Baseline
        r1 = db.query(Run).filter(Run.id == run1_id).first()
        r1.is_baseline = False
        r3.is_baseline = True
        db.commit()

        # 8. Verify Full History Remains Available
        all_runs = (
            db.query(Run)
            .filter(Run.project_id == project_id)
            .order_by(Run.id.asc())
            .all()
        )
        assert len(all_runs) == 3
        assert all_runs[0].id == run1_id and (all_runs[0].passed_tests / all_runs[0].total_tests) == 1.0
        assert all_runs[1].id == run2_id and (all_runs[1].passed_tests / all_runs[1].total_tests) == 0.8
        assert all_runs[2].id == run3_id and (all_runs[2].passed_tests / all_runs[2].total_tests) == 1.0
        assert all_runs[2].is_baseline is True
