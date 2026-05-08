"""Example: Golden-set evaluation with LLM-as-judge.

Demonstrates how to evaluate an agent against a set of expected outputs
and use an LLM judge to assess process quality.
"""

from specops import EvalCase, eval_golden_set, llm_judge, trace_agent


@trace_agent(name="qa-agent")
def qa_agent(question: str) -> str:
    """Simple Q&A agent (simulated)."""
    answers = {
        "What is 2+2?": "4",
        "Capital of Japan?": "Tokyo",
        "Largest planet?": "Jupiter",
    }
    return answers.get(question, "I don't know")


def mock_judge_llm(prompt: str) -> str:
    """Mock LLM for judging (replace with real LLM in production)."""
    return '{"score": 0.9, "reasoning": "The answer is correct and concise."}'


def main() -> None:
    # --- Golden-Set Evaluation ---
    print("=== Golden-Set Evaluation ===")
    cases = [
        EvalCase(input="What is 2+2?", expected="4"),
        EvalCase(input="Capital of Japan?", expected="Tokyo"),
        EvalCase(input="Largest planet?", expected="Jupiter"),
        EvalCase(input="Unknown question", expected="I don't know"),
    ]

    results = eval_golden_set(qa_agent, cases)

    for r in results:
        status = "✓" if r.passed else "✗"
        print(f"  {status} '{r.case.input}' → score={r.score:.1f}")

    passed = sum(1 for r in results if r.passed)
    print(f"\nPassed: {passed}/{len(results)}")

    # --- LLM-as-Judge ---
    print("\n=== LLM-as-Judge ===")
    output = qa_agent("What is 2+2?")
    verdict = llm_judge(
        output,
        criteria="correctness and conciseness",
        judge_fn=mock_judge_llm,
        context="The user asked a simple math question.",
    )
    print(f"  Score: {verdict.score}")
    print(f"  Reasoning: {verdict.reasoning}")
    print(f"  Criteria: {verdict.criteria}")


if __name__ == "__main__":
    main()
