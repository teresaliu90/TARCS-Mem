from tarcsmem.evaluation import run_evaluation


def test_reference_evaluation_runs(tmp_path):
    summary = run_evaluation(tmp_path / "test.db")
    assert summary["cases"] == 4
    assert summary["tarcs_accuracy"] >= summary["naive_baseline_accuracy"]
    assert summary["expected_abstention_cases"] == 1
    assert summary["correct_abstentions"] == 1
    assert summary["correct_abstention_rate"] == 1.0
