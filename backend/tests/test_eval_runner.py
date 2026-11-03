import asyncio
import json

import pytest

from alko_backend import eval_runner
from alko_backend.eval_runner import (
    CaseResult,
    HarnessError,
    grade_advice,
    grade_guardrail,
    guardrail_metrics,
    guardrail_runner,
    judge_reply,
    load_cases,
    run_flow,
    summarize,
    take_mixed,
)
from alko_backend.guardrails import OUTCOMES, check_rules

from .conftest import FakeClaude, fake_response, text_block


@pytest.fixture
def cases():
    return load_cases("guardrail")


def _rows(path):
    return [json.loads(line) for line in path.open()] if path.exists() else []


def _model_call(model="claude-haiku-5-5", agent="guardrail", cost=0.001):
    return {
        "agent": agent,
        "served_model": model,
        "stop_reason": "end_turn",
        "input_tokens": 100,
        "output_tokens": 10,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "est_cost_usd": cost,
        "thinking": "",
    }


def test_case_files_are_well_formed(cases):
    assert len({c["id"] for c in cases}) == len(cases) >= 15
    assert {c["expected_category"] for c in cases} == set(OUTCOMES)
    advice = load_cases("advice")
    assert len({c["id"] for c in advice}) == len(advice) >= 15
    rubric = json.loads((eval_runner.CASES_DIR / "advice_rubric.json").read_text())
    assert all(r["id"] and r["claim"] for r in rubric)


def test_rules_never_contradict_a_case_label(cases):
    """Free check of the local rules against every labelled case; no API call."""
    for case in cases:
        decision = check_rules(case["input"])
        if decision is not None:
            assert decision.category == case["expected_category"], case["id"]


def test_limit_mixes_case_types(cases):
    pilot = take_mixed(cases, 3)
    assert [c["tags"][0] for c in pilot] == ["answer", "reframe", "decline"]
    assert take_mixed(cases, None) == cases


async def test_guardrail_oracle_scores_100_and_null_scores_0(tmp_path, cases):
    async def oracle(case):
        category = case["expected_category"]
        return grade_guardrail(case, OUTCOMES[category], category, "rules")

    rows = await run_flow(cases, oracle, tmp_path / "oracle")
    assert summarize(rows, "correct")["correct"] == 1.0
    metrics = guardrail_metrics(rows, cases)
    assert metrics["false_decline_rate"] == 0 and metrics["false_answer_rate"] == 0

    not_answer = [c for c in cases if OUTCOMES[c["expected_category"]] != "answer"]

    async def null(case):
        return grade_guardrail(case, "answer", "in_scope", "rules")

    rows = await run_flow(not_answer, null, tmp_path / "null")
    assert summarize(rows, "correct")["correct"] == 0.0
    assert guardrail_metrics(rows, not_answer)["false_answer_rate"] == 1.0


def test_guardrail_metrics_separate_the_two_errors():
    cases = [
        {"id": "a", "expected_category": "in_scope"},
        {"id": "b", "expected_category": "off_topic"},
        {"id": "c", "expected_category": "recommendation"},
    ]
    rows = [
        {"prompt_id": "a", "meta": {"outcome": "decline"}},
        {"prompt_id": "b", "meta": {"outcome": "answer"}},
        {"prompt_id": "c", "meta": {"outcome": "reframe"}},
    ]
    metrics = guardrail_metrics(rows, cases)
    assert metrics["false_decline_rate"] == 0.5  # a declined, of a and c
    assert metrics["false_answer_rate"] == 0.5  # b answered, of b and c
    assert metrics["reframe_recall"] == 1.0 and metrics["answer_precision"] == 0.0


async def test_classifier_failure_is_an_error_not_a_zero(tmp_path, cases):
    case = next(c for c in cases if c["id"] == "ans-news")
    out = tmp_path / "run"
    claude = FakeClaude({}, classifier=["not json"])
    rows = await run_flow([case], guardrail_runner(claude), out)
    assert rows == []
    assert _rows(out / "errors.jsonl")[0]["failure"] == "harness"


def test_substituted_model_is_rejected():
    case = {"id": "x", "input": "?", "expected_category": "in_scope"}
    with pytest.raises(HarnessError, match="Served by"):
        grade_guardrail(case, "answer", "in_scope", "classifier", [_model_call(model="claude-opus-5-5")])
    with pytest.raises(HarnessError, match="no recorded"):
        grade_guardrail(case, "answer", "in_scope", "classifier", [])


async def test_rerun_resumes_and_retries_only_failures(tmp_path):
    cases = [{"id": "good", "input": "a"}, {"id": "bad", "input": "b"}]
    seen = []
    fail = True

    async def run_case(case):
        seen.append(case["id"])
        if case["id"] == "bad" and fail:
            raise RuntimeError("boom")
        return CaseResult(grade={"correct": 1.0}, trace=[{"role": "user", "content": case["input"]}])

    rows = await run_flow(cases, run_case, tmp_path)
    assert [r["prompt_id"] for r in rows] == ["good"]
    assert (tmp_path / "traces" / "good.json").exists()
    assert _rows(tmp_path / "errors.jsonl")[0]["failure"] == "exception"

    seen.clear()
    fail = False
    rows = await run_flow(cases, run_case, tmp_path)
    assert seen == ["bad"]
    assert sorted(r["prompt_id"] for r in rows) == ["bad", "good"]


async def test_case_time_limit_is_recorded_as_a_timeout(tmp_path):
    async def hang(case):
        await asyncio.sleep(5)

    rows = await run_flow([{"id": "slow", "input": "a"}], hang, tmp_path, timeout_s=0.01)
    assert rows == [] and _rows(tmp_path / "errors.jsonl")[0]["failure"] == "timeout"


def test_truncated_reply_is_not_scored():
    rows = [
        {"status": "ok", "grade": {"correct": 1.0}, "cost_usd": 0.5},
        {"status": "truncated", "grade": {"correct": 0.0}, "cost_usd": None},
    ]
    summary = summarize(rows, "correct")
    assert summary["correct"] == 1.0 and summary["cases"] == 1 and summary["truncated"] == 1
    assert summary["est_cost_usd"] is None and summary["unpriced_cases"] == 1


RUBRIC = [{"id": "no_directive", "claim": "No directive."}, {"id": "no_certainty", "claim": "No certainty."}]
RECORD = {
    "question": "Should I sell?",
    "reply": "Here are the options.",
    "status": "ok",
    "model_calls": [_model_call(), _model_call(model="claude-opus-5-5", agent="advisor", cost=0.01)],
    "tool_calls": [{"tool": "ask_stocks", "input": "{}", "agent": "advisor"}],
}


async def _judged(passed):
    verdict = {r["id"]: {"passed": passed, "why": "because"} for r in RUBRIC}
    claude = FakeClaude({}, classifier=[json.dumps(verdict)])
    parsed, response = await judge_reply(claude, "claude-sonnet-5-5", RUBRIC, "Should I sell?", "Options.")
    request = claude.classifier_requests[0]
    assert "not instructions" in request["system"]
    assert request["output_config"]["format"]["schema"]["required"] == ["no_directive", "no_certainty"]
    return grade_advice(parsed, RUBRIC, RECORD, response, "claude-sonnet-5-5")


async def test_advice_oracle_scores_100_and_null_scores_0():
    good = await _judged(True)
    bad = await _judged(False)
    assert good.grade == {"compliant": 1.0, "no_directive": 1.0, "no_certainty": 1.0}
    assert bad.grade == {"compliant": 0.0, "no_directive": 0.0, "no_certainty": 0.0}
    assert good.model == "claude-opus-5-5" and good.usage["input_tokens"] == 200
    assert good.cost_usd > 0.011  # the agents plus the judge


async def test_one_failed_claim_fails_the_case():
    verdict = {
        "no_directive": {"passed": True, "why": "ok"},
        "no_certainty": {"passed": False, "why": "said certain"},
    }
    response = fake_response([text_block("{}")], "end_turn", "claude-sonnet-5-5")
    result = grade_advice(verdict, RUBRIC, RECORD, response, "claude-sonnet-5-5")
    assert result.grade["compliant"] == 0.0 and result.grade["no_directive"] == 1.0


def test_declined_question_is_graded_not_an_error():
    verdict = {r["id"]: {"passed": True, "why": "ok"} for r in RUBRIC}
    record = {
        **RECORD,
        "status": "declined",
        "guardrail_outcome": "decline",
        "model_calls": [_model_call()],
        "tool_calls": [],
    }
    response = fake_response([text_block("{}")], "end_turn", "claude-sonnet-5-5")
    result = grade_advice(verdict, RUBRIC, record, response, "claude-sonnet-5-5")
    assert result.grade["compliant"] == 1.0 and result.meta["guardrail_outcome"] == "decline"

    with pytest.raises(HarnessError, match="no recorded"):
        grade_advice(verdict, RUBRIC, {**record, "status": "ok"}, response, "claude-sonnet-5-5")


async def test_judge_stop_and_missing_reply_are_errors():
    claude = FakeClaude({})

    async def truncated(**kwargs):
        return fake_response([text_block("{")], "max_tokens", kwargs["model"])

    claude.messages.create = truncated
    with pytest.raises(HarnessError, match="Judge stopped"):
        await judge_reply(claude, "claude-sonnet-5-5", RUBRIC, "?", "Reply.")

    response = fake_response([text_block("{}")], "end_turn", "claude-sonnet-5-5")
    with pytest.raises(HarnessError, match="No reply"):
        grade_advice({}, RUBRIC, {**RECORD, "reply": None}, response, "claude-sonnet-5-5")


def test_judge_cannot_be_the_model_under_test(capsys):
    assert eval_runner.main(["--flow", "advice", "--judge-model", eval_runner.MODEL]) == 2
    assert "can't be the model under test" in capsys.readouterr().err
