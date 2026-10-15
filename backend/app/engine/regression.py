"""
PromptCheck Phase 4: Baseline and Regression Engine

Handles:
1. Baseline selection (explicit -> project -> fallback to previous completed run)
2. Pass/fail regression classification
3. Improvement classification
4. Unchanged classification
5. Inconclusive classification
6. Soft regression detection (score drops, latency degradation, repeat pass-rate drop)
7. Repeat / pass-rate comparison & flaky test detection
8. Added / removed test case detection
9. Run-level regression summary generation for runs.summary
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.run import Run, RunResult


class Classification(StrEnum):
    REGRESSION = "regression"
    SOFT_REGRESSION = "soft_regression"
    IMPROVEMENT = "improvement"
    UNCHANGED = "unchanged"
    INCONCLUSIVE = "inconclusive"
    PASSED = "passed"
    FAILED = "failed"
    ADDED = "added"
    REMOVED = "removed"
    ERROR = "error"


@dataclass
class TestComparisonInput:
    __test__ = False
    test_case_id: int
    status: str  # passed, failed, error, cancelled
    score: float = 1.0
    latency_ms: float = 0.0
    error_message: str | None = None
    assertion_results: list[dict[str, Any]] = field(default_factory=list)
    repeats_passed: int | None = None
    repeats_total: int | None = None


@dataclass
class TestComparisonOutput:
    __test__ = False
    test_case_id: int
    classification: str
    score: float
    score_delta: float
    reason: str
    details: dict[str, Any]
    is_flaky: bool = False


# Default threshold parameters
DEFAULT_SCORE_TOLERANCE = 0.05
DEFAULT_SOFT_REGRESSION_DROP = 0.15
DEFAULT_PASS_RATE_DROP = 0.20


def calculate_test_score(status: str, assertion_results: list[dict[str, Any]]) -> float:
    """Calculate normalized test score (0.0 to 1.0) from status and assertion results."""
    if status == "error" or status == "cancelled":
        return 0.0

    if not assertion_results:
        return 1.0 if status == "passed" else 0.0

    scores: list[float] = []
    for assertion in assertion_results:
        if "score" in assertion and assertion["score"] is not None:
            try:
                scores.append(float(assertion["score"]))
            except (ValueError, TypeError):
                scores.append(1.0 if assertion.get("passed") else 0.0)
        else:
            scores.append(1.0 if assertion.get("passed") else 0.0)

    if not scores:
        return 1.0 if status == "passed" else 0.0

    avg = sum(scores) / len(scores)
    return round(max(0.0, min(1.0, avg)), 4)


def compare_single_test(
    candidate: TestComparisonInput,
    baseline: TestComparisonInput | None,
    score_tolerance: float = DEFAULT_SCORE_TOLERANCE,
    soft_regression_drop: float = DEFAULT_SOFT_REGRESSION_DROP,
    pass_rate_drop_threshold: float = DEFAULT_PASS_RATE_DROP,
) -> TestComparisonOutput:
    """
    Pure-function comparison of a candidate test result against a baseline result.
    Evaluates:
    - Added tests (baseline is None)
    - Errors / Cancelled -> inconclusive
    - Pass -> Fail -> regression (hard)
    - Fail -> Pass -> improvement
    - Both pass with score drop -> soft_regression
    - Repeat / pass-rate degradation -> soft_regression or regression
    - Flakiness detection
    - Unchanged
    """
    cand_score = calculate_test_score(candidate.status, candidate.assertion_results)
    if candidate.score is not None and candidate.score != 1.0:
        cand_score = round(max(0.0, min(1.0, float(candidate.score))), 4)

    # 1. No baseline result: Added test
    if baseline is None:
        if candidate.status == "error":
            return TestComparisonOutput(
                test_case_id=candidate.test_case_id,
                classification=Classification.ERROR.value,
                score=0.0,
                score_delta=0.0,
                reason="New test case encountered execution error.",
                details={"is_new": True, "error": candidate.error_message},
            )
        cls = Classification.PASSED.value if candidate.status == "passed" else Classification.FAILED.value
        return TestComparisonOutput(
            test_case_id=candidate.test_case_id,
            classification=cls,
            score=cand_score,
            score_delta=0.0,
            reason=f"New test case in candidate run (no baseline result). Status: {candidate.status}.",
            details={"is_new": True, "status": candidate.status, "score": cand_score},
        )

    base_score = calculate_test_score(baseline.status, baseline.assertion_results)
    if baseline.score is not None and baseline.score != 1.0:
        base_score = round(max(0.0, min(1.0, float(baseline.score))), 4)

    score_delta = round(cand_score - base_score, 4)

    # Check for repeat pass rates and flakiness
    is_flaky = False
    cand_pass_rate: float | None = None
    base_pass_rate: float | None = None
    pass_rate_delta: float | None = None

    if candidate.repeats_total and candidate.repeats_total > 1:
        cand_pass_rate = (candidate.repeats_passed or 0) / candidate.repeats_total
        if 0.0 < cand_pass_rate < 1.0:
            is_flaky = True

    if baseline.repeats_total and baseline.repeats_total > 1:
        base_pass_rate = (baseline.repeats_passed or 0) / baseline.repeats_total
        if 0.0 < base_pass_rate < 1.0:
            is_flaky = True

    if cand_pass_rate is not None and base_pass_rate is not None:
        pass_rate_delta = round(cand_pass_rate - base_pass_rate, 4)

    comparison_context = {
        "baseline_status": baseline.status,
        "candidate_status": candidate.status,
        "baseline_score": base_score,
        "candidate_score": cand_score,
        "score_delta": score_delta,
        "is_flaky": is_flaky,
        "baseline_pass_rate": base_pass_rate,
        "candidate_pass_rate": cand_pass_rate,
        "pass_rate_delta": pass_rate_delta,
    }

    # 2. Inconclusive: Errors or Cancellations in candidate or baseline
    if candidate.status in ("error", "cancelled") or baseline.status in ("error", "cancelled"):
        reason = "Test comparison is inconclusive due to execution error or cancellation."
        if candidate.status == "error":
            reason = f"Candidate test encountered error: {candidate.error_message or 'Unknown error'}."
        elif baseline.status == "error":
            reason = f"Baseline test had error: {baseline.error_message or 'Unknown error'}."

        return TestComparisonOutput(
            test_case_id=candidate.test_case_id,
            classification=Classification.INCONCLUSIVE.value,
            score=cand_score,
            score_delta=score_delta,
            reason=reason,
            details=comparison_context,
            is_flaky=is_flaky,
        )

    # 3. Repeat pass-rate drop check
    if pass_rate_delta is not None:
        if pass_rate_delta <= -pass_rate_drop_threshold:
            # Significant drop in repeated pass rate
            cls = (
                Classification.REGRESSION.value
                if cand_pass_rate == 0.0
                else Classification.SOFT_REGRESSION.value
            )
            return TestComparisonOutput(
                test_case_id=candidate.test_case_id,
                classification=cls,
                score=cand_score,
                score_delta=score_delta,
                reason=(
                    f"Pass rate across repeats dropped by {abs(pass_rate_delta):.1%} "
                    f"(from {base_pass_rate:.1%} to {cand_pass_rate:.1%})."
                ),
                details=comparison_context,
                is_flaky=is_flaky,
            )
        elif pass_rate_delta >= pass_rate_drop_threshold:
            return TestComparisonOutput(
                test_case_id=candidate.test_case_id,
                classification=Classification.IMPROVEMENT.value,
                score=cand_score,
                score_delta=score_delta,
                reason=(
                    f"Pass rate across repeats improved by {pass_rate_delta:.1%} "
                    f"(from {base_pass_rate:.1%} to {cand_pass_rate:.1%})."
                ),
                details=comparison_context,
                is_flaky=is_flaky,
            )

    # 4. Hard Pass/Fail Regression
    if baseline.status == "passed" and candidate.status == "failed":
        return TestComparisonOutput(
            test_case_id=candidate.test_case_id,
            classification=Classification.REGRESSION.value,
            score=cand_score,
            score_delta=score_delta,
            reason="Hard regression: test passed in baseline but failed in candidate run.",
            details=comparison_context,
            is_flaky=is_flaky,
        )

    # 5. Improvement (failed in baseline -> passed in candidate)
    if baseline.status == "failed" and candidate.status == "passed":
        return TestComparisonOutput(
            test_case_id=candidate.test_case_id,
            classification=Classification.IMPROVEMENT.value,
            score=cand_score,
            score_delta=score_delta,
            reason="Improvement: test failed in baseline but passed in candidate run.",
            details=comparison_context,
            is_flaky=is_flaky,
        )

    # 6. Both passed -> Check for Soft Regression or Score Improvement
    if baseline.status == "passed" and candidate.status == "passed":
        # Check score drop
        if score_delta <= -soft_regression_drop:
            return TestComparisonOutput(
                test_case_id=candidate.test_case_id,
                classification=Classification.SOFT_REGRESSION.value,
                score=cand_score,
                score_delta=score_delta,
                reason=(
                    f"Soft regression: score dropped by {abs(score_delta):.2f} "
                    f"(from {base_score:.2f} to {cand_score:.2f}) despite passing."
                ),
                details=comparison_context,
                is_flaky=is_flaky,
            )
        # Check score improvement
        elif score_delta >= soft_regression_drop:
            return TestComparisonOutput(
                test_case_id=candidate.test_case_id,
                classification=Classification.IMPROVEMENT.value,
                score=cand_score,
                score_delta=score_delta,
                reason=(
                    f"Score improvement: score increased by +{score_delta:.2f} "
                    f"(from {base_score:.2f} to {cand_score:.2f})."
                ),
                details=comparison_context,
                is_flaky=is_flaky,
            )
        else:
            return TestComparisonOutput(
                test_case_id=candidate.test_case_id,
                classification=Classification.UNCHANGED.value,
                score=cand_score,
                score_delta=score_delta,
                reason=f"Test passed consistently with stable score (delta: {score_delta:+.2f}).",
                details=comparison_context,
                is_flaky=is_flaky,
            )

    # 7. Both failed
    if baseline.status == "failed" and candidate.status == "failed":
        if score_delta <= -soft_regression_drop:
            return TestComparisonOutput(
                test_case_id=candidate.test_case_id,
                classification=Classification.SOFT_REGRESSION.value,
                score=cand_score,
                score_delta=score_delta,
                reason=f"Failed with degraded score (delta: {score_delta:.2f}).",
                details=comparison_context,
                is_flaky=is_flaky,
            )
        elif score_delta >= soft_regression_drop:
            return TestComparisonOutput(
                test_case_id=candidate.test_case_id,
                classification=Classification.IMPROVEMENT.value,
                score=cand_score,
                score_delta=score_delta,
                reason=f"Failed but score improved by +{score_delta:.2f}.",
                details=comparison_context,
                is_flaky=is_flaky,
            )
        else:
            return TestComparisonOutput(
                test_case_id=candidate.test_case_id,
                classification=Classification.UNCHANGED.value,
                score=cand_score,
                score_delta=score_delta,
                reason="Test failed consistently across both baseline and candidate runs.",
                details=comparison_context,
                is_flaky=is_flaky,
            )

    # Fallback to unchanged
    return TestComparisonOutput(
        test_case_id=candidate.test_case_id,
        classification=Classification.UNCHANGED.value,
        score=cand_score,
        score_delta=score_delta,
        reason="Test status and score are unchanged.",
        details=comparison_context,
        is_flaky=is_flaky,
    )


def compute_regression_analysis(
    candidate_tests: list[TestComparisonInput],
    baseline_tests: list[TestComparisonInput] | None = None,
    baseline_run_id: int | None = None,
    score_tolerance: float = DEFAULT_SCORE_TOLERANCE,
    soft_regression_drop: float = DEFAULT_SOFT_REGRESSION_DROP,
    pass_rate_drop_threshold: float = DEFAULT_PASS_RATE_DROP,
) -> tuple[list[TestComparisonOutput], dict[str, Any]]:
    """
    Compute full regression analysis across all tests in candidate run against baseline.
    Returns (list_of_test_outputs, summary_dict).
    """
    baseline_map: dict[int, TestComparisonInput] = {}
    if baseline_tests:
        for bt in baseline_tests:
            baseline_map[bt.test_case_id] = bt

    test_outputs: list[TestComparisonOutput] = []
    candidate_ids = set()

    for cand in candidate_tests:
        candidate_ids.add(cand.test_case_id)
        base = baseline_map.get(cand.test_case_id)
        output = compare_single_test(
            candidate=cand,
            baseline=base,
            score_tolerance=score_tolerance,
            soft_regression_drop=soft_regression_drop,
            pass_rate_drop_threshold=pass_rate_drop_threshold,
        )
        test_outputs.append(output)

    # Removed tests: present in baseline, but absent in candidate run
    removed_tests: list[int] = []
    if baseline_tests:
        for bt in baseline_tests:
            if bt.test_case_id not in candidate_ids:
                removed_tests.append(bt.test_case_id)

    # Aggregate metrics
    total_candidate = len(candidate_tests)
    total_baseline = len(baseline_tests) if baseline_tests is not None else 0
    common_tests_count = len(candidate_ids.intersection(baseline_map.keys()))
    added_tests_count = len(candidate_ids - set(baseline_map.keys()))
    removed_tests_count = len(removed_tests)

    regressions = sum(1 for o in test_outputs if o.classification == Classification.REGRESSION.value)
    soft_regressions = sum(
        1 for o in test_outputs if o.classification == Classification.SOFT_REGRESSION.value
    )
    improvements = sum(
        1 for o in test_outputs if o.classification == Classification.IMPROVEMENT.value
    )
    unchanged = sum(1 for o in test_outputs if o.classification == Classification.UNCHANGED.value)
    inconclusive = sum(
        1 for o in test_outputs if o.classification == Classification.INCONCLUSIVE.value
    )
    flaky_count = sum(1 for o in test_outputs if o.is_flaky)

    passed_count = sum(
        1 for c in candidate_tests if c.status == "passed"
    )
    failed_count = sum(
        1 for c in candidate_tests if c.status in ("failed", "error")
    )

    cand_scores = [o.score for o in test_outputs]
    candidate_avg_score = round(sum(cand_scores) / len(cand_scores), 4) if cand_scores else 0.0

    if baseline_tests:
        b_scores = [calculate_test_score(bt.status, bt.assertion_results) for bt in baseline_tests]
        baseline_avg_score = round(sum(b_scores) / len(b_scores), 4) if b_scores else 0.0
        baseline_pass_rate = (
            round(sum(1 for bt in baseline_tests if bt.status == "passed") / len(baseline_tests), 4)
            if baseline_tests
            else 0.0
        )
    else:
        baseline_avg_score = 0.0
        baseline_pass_rate = 0.0

    candidate_pass_rate = (
        round(passed_count / total_candidate, 4) if total_candidate > 0 else 0.0
    )
    score_delta = round(candidate_avg_score - baseline_avg_score, 4) if baseline_tests else 0.0
    pass_rate_delta = (
        round(candidate_pass_rate - baseline_pass_rate, 4) if baseline_tests else 0.0
    )

    # Determine overall verdict
    if regressions > 0:
        verdict = "regression"
    elif soft_regressions > 0:
        verdict = "soft_regression"
    elif improvements > 0 and regressions == 0 and soft_regressions == 0:
        verdict = "improvement"
    elif failed_count > 0:
        verdict = "failed"
    elif inconclusive > 0 and passed_count == 0:
        verdict = "inconclusive"
    else:
        verdict = "passed"

    summary: dict[str, Any] = {
        "baseline_run_id": baseline_run_id,
        "total_tests": total_candidate,
        "baseline_tests": total_baseline,
        "common_tests": common_tests_count,
        "added_tests": added_tests_count,
        "removed_tests": removed_tests_count,
        "removed_test_case_ids": removed_tests,
        "passed_tests": passed_count,
        "failed_tests": failed_count,
        "regressions": regressions,
        "soft_regressions": soft_regressions,
        "improvements": improvements,
        "unchanged": unchanged,
        "inconclusive": inconclusive,
        "flaky_tests": flaky_count,
        "candidate_avg_score": candidate_avg_score,
        "baseline_avg_score": baseline_avg_score,
        "score_delta": score_delta,
        "candidate_pass_rate": candidate_pass_rate,
        "baseline_pass_rate": baseline_pass_rate,
        "pass_rate_delta": pass_rate_delta,
        "verdict": verdict,
        "has_regressions": regressions > 0,
        "has_soft_regressions": soft_regressions > 0,
        "computed_at": datetime.now(UTC).isoformat(),
    }

    return test_outputs, summary


def resolve_baseline_run(
    db: Session,
    run: Run,
    explicit_baseline_id: int | None = None,
) -> Run | None:
    """
    Select the baseline run according to PromptCheck resolution order:
    1. Explicit baseline ID (if provided and valid)
    2. Project baseline (if configured on project and valid)
    3. Fallback to previous completed run in the same project
    """
    project = db.query(Project).filter(Project.id == run.project_id).first()

    # 1. Explicit baseline
    if explicit_baseline_id is not None:
        explicit_run = (
            db.query(Run)
            .filter(
                Run.id == explicit_baseline_id,
                Run.project_id == run.project_id,
                Run.id != run.id,
            )
            .first()
        )
        if explicit_run and explicit_run.status == "completed":
            return explicit_run
        elif explicit_run:
            raise ValueError(f"Explicit baseline run #{explicit_baseline_id} is not in 'completed' status (current: '{explicit_run.status}').")
        else:
            raise ValueError(f"Explicit baseline run #{explicit_baseline_id} does not exist or belong to this project.")

    # 2. Project designated baseline
    if project and project.baseline_run_id and project.baseline_run_id != run.id:
        proj_baseline = (
            db.query(Run)
            .filter(
                Run.id == project.baseline_run_id,
                Run.project_id == run.project_id,
                Run.status == "completed",
            )
            .first()
        )
        if proj_baseline:
            return proj_baseline

    # 3. Fallback to previous completed run in the project
    # Look for the latest completed run created before this run, or having a smaller ID
    fallback_run = (
        db.query(Run)
        .filter(
            Run.project_id == run.project_id,
            Run.id != run.id,
            Run.status == "completed",
            Run.created_at <= run.created_at,
        )
        .order_by(Run.created_at.desc(), Run.id.desc())
        .first()
    )

    if not fallback_run:
        # Also try by ID in case timestamps are identical in fast test transactions
        fallback_run = (
            db.query(Run)
            .filter(
                Run.project_id == run.project_id,
                Run.id < run.id,
                Run.status == "completed",
            )
            .order_by(Run.id.desc())
            .first()
        )

    return fallback_run


def apply_regression_analysis_to_run(
    db: Session,
    run_id: int,
    explicit_baseline_id: int | None = None,
) -> dict[str, Any]:
    """
    Loads run and candidate results from DB, resolves baseline, runs analysis,
    updates run_results records with classification & score, and stores summary on run.
    Accurately aggregates multiple repeated executions per test case for flakiness analysis.
    """
    from collections import defaultdict

    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise ValueError(f"Run #{run_id} not found.")

    baseline_run = resolve_baseline_run(db, run, explicit_baseline_id=explicit_baseline_id)
    run.baseline_run_id = baseline_run.id if baseline_run else None

    # Load candidate run_results
    cand_records = (
        db.query(RunResult).filter(RunResult.run_id == run.id).order_by(RunResult.id.asc()).all()
    )
    cand_by_test = defaultdict(list)
    for cr in cand_records:
        cand_by_test[cr.test_case_id].append(cr)

    cand_inputs: list[TestComparisonInput] = []
    for tid, recs in cand_by_test.items():
        total_reps = len(recs)
        passed_reps = sum(1 for r in recs if r.status == "passed")
        any_error = any(r.status == "error" for r in recs)
        any_cancelled = any(r.status == "cancelled" for r in recs)

        if any_error:
            status_val = "error"
        elif any_cancelled:
            status_val = "cancelled"
        elif passed_reps == total_reps:
            status_val = "passed"
        else:
            status_val = "failed"

        scores = [r.score if r.score is not None else 1.0 for r in recs]
        avg_score = sum(scores) / len(scores) if scores else 0.0

        cand_inputs.append(
            TestComparisonInput(
                test_case_id=tid,
                status=status_val,
                score=round(avg_score, 4),
                latency_ms=sum(r.latency_ms for r in recs) / len(recs),
                error_message=recs[0].error_message,
                assertion_results=recs[0].assertion_results or [],
                repeats_passed=passed_reps,
                repeats_total=total_reps,
            )
        )

    # Load baseline run_results (if baseline exists)
    base_inputs: list[TestComparisonInput] | None = None
    if baseline_run:
        base_records = (
            db.query(RunResult)
            .filter(RunResult.run_id == baseline_run.id)
            .order_by(RunResult.id.asc())
            .all()
        )
        base_by_test = defaultdict(list)
        for br in base_records:
            base_by_test[br.test_case_id].append(br)

        base_inputs = []
        for tid, recs in base_by_test.items():
            total_reps = len(recs)
            passed_reps = sum(1 for r in recs if r.status == "passed")
            any_error = any(r.status == "error" for r in recs)
            any_cancelled = any(r.status == "cancelled" for r in recs)

            if any_error:
                status_val = "error"
            elif any_cancelled:
                status_val = "cancelled"
            elif passed_reps == total_reps:
                status_val = "passed"
            else:
                status_val = "failed"

            scores = [r.score if r.score is not None else 1.0 for r in recs]
            avg_score = sum(scores) / len(scores) if scores else 0.0

            base_inputs.append(
                TestComparisonInput(
                    test_case_id=tid,
                    status=status_val,
                    score=round(avg_score, 4),
                    latency_ms=sum(r.latency_ms for r in recs) / len(recs),
                    error_message=recs[0].error_message,
                    assertion_results=recs[0].assertion_results or [],
                    repeats_passed=passed_reps,
                    repeats_total=total_reps,
                )
            )

    # Run analysis
    outputs, summary = compute_regression_analysis(
        candidate_tests=cand_inputs,
        baseline_tests=base_inputs,
        baseline_run_id=baseline_run.id if baseline_run else None,
    )

    # Update database records
    output_map = {o.test_case_id: o for o in outputs}
    for cr in cand_records:
        out = output_map.get(cr.test_case_id)
        if out:
            cr.classification = out.classification
            cr.comparison_details = {
                "score_delta": out.score_delta,
                "reason": out.reason,
                "details": out.details,
                "is_flaky": out.is_flaky,
            }

    run.summary = summary
    db.commit()
    db.refresh(run)

    return summary
