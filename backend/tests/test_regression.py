import pytest

from app.engine.client import FakeGeminiClient
from app.engine.regression import (
    Classification,
    TestComparisonInput,
    apply_regression_analysis_to_run,
    calculate_test_score,
    compare_single_test,
    compute_regression_analysis,
    resolve_baseline_run,
)
from app.engine.runner import run_engine_executor
from app.models.project import Project
from app.models.prompt import Prompt, PromptVersion
from app.models.run import Run, RunResult
from app.models.test_case import TestCase
from app.models.user import User


def test_calculate_test_score():
    # Pass with no assertions
    assert calculate_test_score("passed", []) == 1.0
    # Fail with no assertions
    assert calculate_test_score("failed", []) == 0.0
    # Error
    assert calculate_test_score("error", [{"score": 1.0}]) == 0.0

    # Assertions with score
    assert calculate_test_score("passed", [{"score": 0.8}, {"score": 0.6}]) == 0.7
    # Assertions with boolean passed only
    assert calculate_test_score("passed", [{"passed": True}, {"passed": False}]) == 0.5


# ---------------------------------------------------------------------------
# 1. Exhaustive Pass/Fail Combination Matrix
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "base_status,cand_status,base_score,cand_score,expected_cls",
    [
        ("passed", "passed", 1.0, 1.0, Classification.UNCHANGED.value),
        ("passed", "failed", 1.0, 0.0, Classification.REGRESSION.value),
        ("failed", "passed", 0.0, 1.0, Classification.IMPROVEMENT.value),
        ("failed", "failed", 0.0, 0.0, Classification.UNCHANGED.value),
        ("passed", "error", 1.0, 0.0, Classification.INCONCLUSIVE.value),
        ("error", "passed", 0.0, 1.0, Classification.INCONCLUSIVE.value),
        ("error", "error", 0.0, 0.0, Classification.INCONCLUSIVE.value),
        ("passed", "cancelled", 1.0, 0.0, Classification.INCONCLUSIVE.value),
        ("cancelled", "passed", 0.0, 1.0, Classification.INCONCLUSIVE.value),
    ],
)
def test_every_pass_fail_combination(
    base_status, cand_status, base_score, cand_score, expected_cls
):
    cand = TestComparisonInput(
        test_case_id=1,
        status=cand_status,
        score=cand_score,
        assertion_results=[{"score": cand_score, "passed": cand_status == "passed"}],
    )
    base = TestComparisonInput(
        test_case_id=1,
        status=base_status,
        score=base_score,
        assertion_results=[{"score": base_score, "passed": base_status == "passed"}],
    )

    out = compare_single_test(cand, base)
    assert out.classification == expected_cls
    assert out.test_case_id == 1
    assert out.details["baseline_status"] == base_status
    assert out.details["candidate_status"] == cand_status


# ---------------------------------------------------------------------------
# 2. Added & Removed Tests
# ---------------------------------------------------------------------------
def test_added_tests():
    # New test case in candidate not present in baseline
    cand = TestComparisonInput(test_case_id=99, status="passed", score=1.0)
    out = compare_single_test(cand, baseline=None)

    assert out.classification == Classification.PASSED.value
    assert out.details["is_new"] is True

    # Error on new test case
    cand_err = TestComparisonInput(
        test_case_id=100, status="error", score=0.0, error_message="Syntax crash"
    )
    out_err = compare_single_test(cand_err, baseline=None)
    assert out_err.classification == Classification.ERROR.value
    assert out_err.details["is_new"] is True


def test_removed_tests_in_summary():
    cand_tests = [
        TestComparisonInput(test_case_id=1, status="passed"),
        TestComparisonInput(test_case_id=2, status="passed"),
    ]
    base_tests = [
        TestComparisonInput(test_case_id=1, status="passed"),
        TestComparisonInput(test_case_id=2, status="passed"),
        TestComparisonInput(test_case_id=3, status="passed"),  # Removed in candidate
        TestComparisonInput(test_case_id=4, status="passed"),  # Removed in candidate
    ]

    outputs, summary = compute_regression_analysis(
        candidate_tests=cand_tests,
        baseline_tests=base_tests,
        baseline_run_id=10,
    )

    assert summary["total_tests"] == 2
    assert summary["baseline_tests"] == 4
    assert summary["common_tests"] == 2
    assert summary["removed_tests"] == 2
    assert 3 in summary["removed_test_case_ids"]
    assert 4 in summary["removed_test_case_ids"]


# ---------------------------------------------------------------------------
# 3. Soft Regression Detection & Score Drops
# ---------------------------------------------------------------------------
def test_soft_regression_score_drops():
    # Both passed, but score dropped by 0.30 (from 1.0 to 0.70)
    base = TestComparisonInput(test_case_id=1, status="passed", score=1.0)
    cand = TestComparisonInput(test_case_id=1, status="passed", score=0.70)

    out = compare_single_test(cand, base, soft_regression_drop=0.15)
    assert out.classification == Classification.SOFT_REGRESSION.value
    assert out.score_delta == -0.30
    assert "Soft regression" in out.reason


def test_score_improvements():
    # Both passed, but score increased by +0.25 (from 0.65 to 0.90)
    base = TestComparisonInput(test_case_id=1, status="passed", score=0.65)
    cand = TestComparisonInput(test_case_id=1, status="passed", score=0.90)

    out = compare_single_test(cand, base, soft_regression_drop=0.15)
    assert out.classification == Classification.IMPROVEMENT.value
    assert out.score_delta == 0.25
    assert "Score improvement" in out.reason

    # Both failed, but score improved significantly
    base_f = TestComparisonInput(test_case_id=2, status="failed", score=0.10)
    cand_f = TestComparisonInput(test_case_id=2, status="failed", score=0.35)
    out_f = compare_single_test(cand_f, base_f, soft_regression_drop=0.15)
    assert out_f.classification == Classification.IMPROVEMENT.value


# ---------------------------------------------------------------------------
# 4. Repeated Tests, Pass-Rate Comparison & Flakiness
# ---------------------------------------------------------------------------
def test_repeated_tests_pass_rate_comparison():
    # Baseline had 5/5 passes (100%), candidate has 2/5 passes (40%) -> drop of 60%
    base = TestComparisonInput(
        test_case_id=1,
        status="passed",
        score=1.0,
        repeats_passed=5,
        repeats_total=5,
    )
    cand = TestComparisonInput(
        test_case_id=1,
        status="passed",
        score=0.4,
        repeats_passed=2,
        repeats_total=5,
    )

    out = compare_single_test(cand, base, pass_rate_drop_threshold=0.20)
    assert out.classification == Classification.SOFT_REGRESSION.value
    assert out.details["baseline_pass_rate"] == 1.0
    assert out.details["candidate_pass_rate"] == 0.4
    assert out.details["pass_rate_delta"] == -0.6
    assert out.is_flaky is True


def test_flaky_test_detection():
    # Test passed 3 out of 5 repeats (flaky, pass rate 0.60)
    cand = TestComparisonInput(
        test_case_id=1,
        status="passed",
        score=0.6,
        repeats_passed=3,
        repeats_total=5,
    )
    base = TestComparisonInput(
        test_case_id=1,
        status="passed",
        score=0.6,
        repeats_passed=3,
        repeats_total=5,
    )

    out = compare_single_test(cand, base)
    assert out.is_flaky is True
    assert out.classification == Classification.UNCHANGED.value


# ---------------------------------------------------------------------------
# 5. Database & Baseline Selection Hierarchy
# ---------------------------------------------------------------------------
def test_baseline_selection_hierarchy(db_session, user1):
    project = Project(user_id=user1.id, name="Regression Project")
    db_session.add(project)
    db_session.flush()

    prompt = Prompt(project_id=project.id, name="Prompt A")
    db_session.add(prompt)
    db_session.flush()

    pv = PromptVersion(prompt_id=prompt.id, version_number=1, content="Hello", content_hash="hash1")
    db_session.add(pv)
    db_session.flush()

    # Create 3 historical completed runs
    run1 = Run(project_id=project.id, prompt_version_id=pv.id, status="completed", total_tests=5)
    run2 = Run(project_id=project.id, prompt_version_id=pv.id, status="completed", total_tests=5)
    run3 = Run(project_id=project.id, prompt_version_id=pv.id, status="completed", total_tests=5)
    db_session.add_all([run1, run2, run3])
    db_session.flush()

    cand_run = Run(project_id=project.id, prompt_version_id=pv.id, status="queued", total_tests=5)
    db_session.add(cand_run)
    db_session.flush()

    # 1. Fallback to previous completed run: should select run3 (most recent)
    selected_fallback = resolve_baseline_run(db_session, cand_run)
    assert selected_fallback is not None
    assert selected_fallback.id == run3.id

    # 2. Project designated baseline: set project.baseline_run_id = run1.id
    project.baseline_run_id = run1.id
    db_session.commit()

    selected_proj = resolve_baseline_run(db_session, cand_run)
    assert selected_proj is not None
    assert selected_proj.id == run1.id

    # 3. Explicit baseline: explicit_baseline_id = run2.id overrides project baseline
    selected_explicit = resolve_baseline_run(
        db_session, cand_run, explicit_baseline_id=run2.id
    )
    assert selected_explicit is not None
    assert selected_explicit.id == run2.id


# ---------------------------------------------------------------------------
# 6. Apply Regression Analysis to Run in Database
# ---------------------------------------------------------------------------
def test_apply_regression_analysis_to_run_db(db_session, user1):
    project = Project(user_id=user1.id, name="Analysis Project")
    db_session.add(project)
    db_session.flush()

    prompt = Prompt(project_id=project.id, name="Prompt B")
    db_session.add(prompt)
    db_session.flush()

    pv = PromptVersion(prompt_id=prompt.id, version_number=1, content="Test", content_hash="hash2")
    db_session.add(pv)
    db_session.flush()

    tc1 = TestCase(project_id=project.id, name="TC1", inputs={"a": 1})
    tc2 = TestCase(project_id=project.id, name="TC2", inputs={"a": 2})
    tc3 = TestCase(project_id=project.id, name="TC3", inputs={"a": 3})
    db_session.add_all([tc1, tc2, tc3])
    db_session.flush()

    # Run 1 (Baseline): all 3 passed
    run_base = Run(project_id=project.id, prompt_version_id=pv.id, status="completed", total_tests=3, passed_tests=3)
    db_session.add(run_base)
    db_session.flush()

    res_b1 = RunResult(run_id=run_base.id, test_case_id=tc1.id, status="passed", score=1.0)
    res_b2 = RunResult(run_id=run_base.id, test_case_id=tc2.id, status="passed", score=1.0)
    res_b3 = RunResult(run_id=run_base.id, test_case_id=tc3.id, status="passed", score=1.0)
    db_session.add_all([res_b1, res_b2, res_b3])
    db_session.commit()

    # Run 2 (Candidate):
    # tc1: passed (unchanged)
    # tc2: failed (REGRESSION!)
    # tc3: passed with score 0.70 (SOFT REGRESSION!)
    run_cand = Run(project_id=project.id, prompt_version_id=pv.id, status="completed", total_tests=3, passed_tests=2, failed_tests=1)
    db_session.add(run_cand)
    db_session.flush()

    res_c1 = RunResult(run_id=run_cand.id, test_case_id=tc1.id, status="passed", score=1.0)
    res_c2 = RunResult(run_id=run_cand.id, test_case_id=tc2.id, status="failed", score=0.0)
    res_c3 = RunResult(run_id=run_cand.id, test_case_id=tc3.id, status="passed", score=0.70)
    db_session.add_all([res_c1, res_c2, res_c3])
    db_session.commit()

    # Apply regression analysis
    summary = apply_regression_analysis_to_run(db_session, run_cand.id)

    db_session.refresh(run_cand)
    assert run_cand.baseline_run_id == run_base.id
    assert summary["regressions"] == 1
    assert summary["soft_regressions"] == 1
    assert summary["unchanged"] == 1
    assert summary["verdict"] == "regression"
    assert summary["has_regressions"] is True

    # Check classifications stored on run_results
    db_session.refresh(res_c1)
    db_session.refresh(res_c2)
    db_session.refresh(res_c3)

    assert res_c1.classification == Classification.UNCHANGED.value
    assert res_c2.classification == Classification.REGRESSION.value
    assert res_c3.classification == Classification.SOFT_REGRESSION.value
    assert res_c2.comparison_details["reason"] == "Hard regression: test passed in baseline but failed in candidate run."


# ---------------------------------------------------------------------------
# 7. API POST /runs/{id}/baseline
# ---------------------------------------------------------------------------
def test_post_runs_baseline_api(client, auth_headers_user1, db_session, user1):
    project = Project(user_id=user1.id, name="API Baseline Test")
    db_session.add(project)
    db_session.flush()

    prompt = Prompt(project_id=project.id, name="Prompt C")
    db_session.add(prompt)
    db_session.flush()

    pv = PromptVersion(prompt_id=prompt.id, version_number=1, content="Hello", content_hash="hash_api")
    db_session.add(pv)
    db_session.flush()

    tc = TestCase(project_id=project.id, name="API TC", inputs={"x": 1})
    db_session.add(tc)
    db_session.flush()

    run = Run(project_id=project.id, prompt_version_id=pv.id, status="completed", total_tests=1, passed_tests=1)
    db_session.add(run)
    db_session.flush()

    res = RunResult(run_id=run.id, test_case_id=tc.id, status="passed", score=1.0)
    db_session.add(res)
    db_session.commit()

    # Test POST /runs/{id}/baseline sets as project baseline
    response = client.post(
        f"/runs/{run.id}/baseline",
        headers=auth_headers_user1,
        json={"set_as_project_baseline": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == run.id
    assert data["status"] == "completed"

    db_session.refresh(project)
    assert project.baseline_run_id == run.id

    # Also verify route works on /api/runs/{id}/baseline
    resp_api = client.post(
        f"/api/runs/{run.id}/baseline",
        headers=auth_headers_user1,
        json={"set_as_project_baseline": True},
    )
    assert resp_api.status_code == 200


# ---------------------------------------------------------------------------
# 8. End-to-End Run Engine with Regression Summary
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_run_engine_automatic_regression_calculation():
    import time

    from app.database import SessionLocal

    uid = f"reg_user_{time.time()}_{id(object())}"
    with SessionLocal() as db:
        user = User(
            email=f"{uid}@example.com",
            hashed_password="hashed_pass_test",
            full_name="Reg Test User",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        project = Project(user_id=user.id, name="E2E Regression Project")
        db.add(project)
        db.commit()
        db.refresh(project)

        prompt = Prompt(project_id=project.id, name="Prompt D")
        db.add(prompt)
        db.commit()
        db.refresh(prompt)

        pv1 = PromptVersion(
            prompt_id=prompt.id,
            version_number=1,
            content="Answer: {{query}}",
            content_hash=f"h_d1_{time.time()}",
        )
        db.add(pv1)
        db.commit()
        db.refresh(pv1)

        tc1 = TestCase(
            project_id=project.id,
            name="Q1",
            inputs={"query": "capital of France"},
            assertions=[{"type": "contains", "substring": "Paris"}],
        )
        tc2 = TestCase(
            project_id=project.id,
            name="Q2",
            inputs={"query": "capital of Germany"},
            assertions=[{"type": "contains", "substring": "Berlin"}],
        )
        db.add_all([tc1, tc2])
        db.commit()
        db.refresh(tc1)
        db.refresh(tc2)

        p_id = project.id
        v_id = pv1.id
        tc2_id = tc2.id

    client_mock = FakeGeminiClient()
    client_mock.set_response_for_prompt("capital of France", "The capital is Paris.")
    client_mock.set_response_for_prompt("capital of Germany", "The capital is Berlin.")

    # 1. Execute Run 1 (Baseline run)
    with SessionLocal() as db:
        run1 = Run(project_id=p_id, prompt_version_id=v_id, status="queued", total_tests=2)
        db.add(run1)
        db.commit()
        db.refresh(run1)
        run1_id = run1.id

    await run_engine_executor(run_id=run1_id, client=client_mock, enable_cache=False)

    with SessionLocal() as db:
        r1 = db.query(Run).filter(Run.id == run1_id).first()
        assert r1.status == "completed"
        assert r1.passed_tests == 2
        assert r1.summary is not None
        assert r1.summary["verdict"] == "passed"

    # 2. Execute Run 2 with regression on TC2 (Germany returns "Munich" instead of "Berlin")
    client_mock2 = FakeGeminiClient()
    client_mock2.set_response_for_prompt("capital of France", "The capital is Paris.")
    client_mock2.set_response_for_prompt("capital of Germany", "The capital is Munich.")

    with SessionLocal() as db:
        run2 = Run(project_id=p_id, prompt_version_id=v_id, status="queued", total_tests=2)
        db.add(run2)
        db.commit()
        db.refresh(run2)
        run2_id = run2.id

    await run_engine_executor(run_id=run2_id, client=client_mock2, enable_cache=False)

    with SessionLocal() as db:
        r2 = db.query(Run).filter(Run.id == run2_id).first()
        assert r2.status == "completed"
        assert r2.passed_tests == 1
        assert r2.failed_tests == 1
        assert r2.baseline_run_id == run1_id
        assert r2.summary is not None
        assert r2.summary["regressions"] == 1
        assert r2.summary["verdict"] == "regression"
        assert r2.summary["has_regressions"] is True

        # Check results on run2
        results = db.query(RunResult).filter(RunResult.run_id == r2.id).all()
        q2_res = next(r for r in results if r.test_case_id == tc2_id)
        assert q2_res.status == "failed"
        assert q2_res.classification == "regression"
