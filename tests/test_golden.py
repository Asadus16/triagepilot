from app.golden import run_golden


def test_golden_regression_suite_passes_completely():
    result = run_golden()
    failures = [r for r in result["results"] if not r["passed"]]
    assert not failures, f"golden regression failures: {failures}"
    assert result["passed"] == result["total"]
