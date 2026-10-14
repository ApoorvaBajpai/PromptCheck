import re
from typing import Any


def evaluate_assertions(
    output: str, assertions: list[dict[str, Any]]
) -> tuple[bool, list[dict[str, Any]]]:
    """
    Evaluate deterministic assertions against model output.
    Returns (all_passed: bool, details: list[dict]).
    """
    if not assertions:
        return True, []

    results: list[dict[str, Any]] = []
    all_passed = True

    for a in assertions:
        a_type = a.get("type", "").lower()
        val = a.get("value")
        passed = False
        message = ""

        if a_type in ("contains", "contain"):
            expected = str(val)
            passed = expected.lower() in output.lower()
            message = f"Output should contain '{expected}'"

        elif a_type in ("not_contains", "does_not_contain", "not_contain"):
            expected = str(val)
            passed = expected.lower() not in output.lower()
            message = f"Output should not contain '{expected}'"

        elif a_type in ("equals", "exact"):
            expected = str(val).strip()
            passed = output.strip() == expected
            message = f"Output should exactly equal '{expected}'"

        elif a_type in ("starts_with", "startswith"):
            expected = str(val).strip()
            passed = output.strip().lower().startswith(expected.lower())
            message = f"Output should start with '{expected}'"

        elif a_type in ("ends_with", "endswith"):
            expected = str(val).strip()
            passed = output.strip().lower().endswith(expected.lower())
            message = f"Output should end with '{expected}'"

        elif a_type in ("max_length", "max_len"):
            max_len = int(val or 0)
            passed = len(output.strip()) <= max_len
            message = f"Output length ({len(output.strip())}) should be <= {max_len}"

        elif a_type in ("regex", "matches"):
            pattern = str(val)
            passed = bool(re.search(pattern, output, flags=re.IGNORECASE))
            message = f"Output should match regex pattern '{pattern}'"

        else:
            # Default fallback pass
            passed = True
            message = f"Unknown assertion type '{a_type}', passed by default"

        if not passed:
            all_passed = False

        results.append(
            {
                "type": a_type,
                "expected": val,
                "passed": passed,
                "message": message,
            }
        )

    return all_passed, results
