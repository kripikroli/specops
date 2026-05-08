"""Example: Detecting infinite loops in agent behavior.

Demonstrates using the simulation sandbox to catch agents that get stuck
repeating the same action indefinitely.
"""

from specops import SimulationEnvironment, simulate, simulation

# --- Using the context manager ---


def run_with_context_manager():
    """Detect a looping agent using the simulation() context manager."""
    with simulation("loop-detection", max_steps=20, loop_threshold=3) as sim:
        # Simulate an agent that gets stuck searching
        actions = ["search", "search", "search", "search", "summarize"]
        for action in actions:
            event = sim.record("research-agent", action)
            if event.anomaly:
                print(
                    f"⚠️  Anomaly at step {event.step}: "
                    f"{event.anomaly.value}"
                )
                break

        result = sim.stop()
        print(f"Scenario: {result.scenario}")
        print(f"Passed: {result.passed}")
        print(f"Anomalies: {len(result.anomalies)}")


# --- Using the @simulate decorator ---


@simulate("decorator-loop-test", max_steps=50, loop_threshold=4)
def test_agent_loop(sim: SimulationEnvironment):
    """Test that an agent doesn't loop when processing tasks."""
    tasks = ["analyze", "plan", "execute", "verify"]

    for _round in range(3):
        for task in tasks:
            sim.record("task-agent", task)

    # This agent cycles through tasks properly — no loop detected
    # because it alternates between different actions


@simulate("stuck-agent", max_steps=10, loop_threshold=3)
def test_stuck_agent(sim: SimulationEnvironment):
    """Simulate an agent stuck retrying the same failed action."""
    for _ in range(10):
        event = sim.record("stuck-agent", "call_api")
        if event.anomaly:
            print(f"  Caught loop at step {event.step}!")
            return


if __name__ == "__main__":
    print("=== Context Manager: Loop Detection ===")
    run_with_context_manager()

    print("\n=== Decorator: Healthy Agent ===")
    result = test_agent_loop()
    print(f"Passed: {result.passed}, Steps: {len(result.events)}")

    print("\n=== Decorator: Stuck Agent ===")
    result = test_stuck_agent()
    print(f"Passed: {result.passed}, Anomalies: {len(result.anomalies)}")
