from clinicalclaw.runtime import build_tool_gate
from clinicalclaw.models import ToolPolicy
from clinicalclaw.scenarios import load_scenario_map


def test_scenarios_load_v1_contracts():
    scenarios = load_scenario_map("scenarios")

    assert {"diagnostic_prep", "imaging_qc"} <= set(scenarios)
    assert scenarios["diagnostic_prep"].review.required is True
    assert scenarios["diagnostic_prep"].policy.connectors.ehr == "read"
    assert scenarios["imaging_qc"].outputs[1].target_mappings[0].resource_type == "Observation"


def test_tool_gate_honors_allow_and_block_lists():
    policy = ToolPolicy(
        allowed_tools=["read_file", "think", "write_file"],
        blocked_tools=["write_file"],
    )
    gate = build_tool_gate(policy)

    assert gate("read_file", {}) is True
    assert gate("think", {}) is True
    assert gate("write_file", {}) is False
    assert gate("execute", {}) is False
