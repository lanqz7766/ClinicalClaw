from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from math import ceil
from threading import Lock
from typing import Any


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


KNOWLEDGE_BASE = [
    {
        "id": "roils_case_16",
        "title": "Prescription transcription error and incorrect monitor units",
        "theme": "prescription_transcription",
        "category": "Order Integrity",
        "process_step": "Plan Preparation",
        "severity_hint": "urgent",
        "evidence_level": "Published case study",
        "signals": [
            "prescription",
            "manual transcription",
            "monitor units",
            "mu",
            "extra zero",
            "whole brain",
            "first physics check",
        ],
        "summary": (
            "Manual dose transcription created a high-MU whole-brain plan pattern that was only caught during "
            "physics review."
        ),
        "contributing_factors": [
            "Manual handoff between prescription and TPS entry",
            "Weak hard-stop validation for outlier monitor units",
            "Time pressure during plan release",
        ],
        "detection_indicators": [
            "Monitor units well above site baseline",
            "Mismatch between prescribed fractionation and plan values",
            "Late-stage catch during first physics check",
        ],
        "recommended_checks": [
            "Verify prescribed total dose and fractionation against plan parameters.",
            "Independently review unusually high monitor units before approval.",
            "Require hard-stop verification for manual transcription steps.",
        ],
        "mitigation_playbook": [
            "Hold downstream approval until prescription and TPS values are reconciled.",
            "Escalate to physics lead when MU outlier exceeds site threshold.",
            "Record whether the error originated from physician order entry or planning transfer.",
        ],
        "review_questions": [
            "Was the prescription copied manually into the planning system?",
            "Did any independent reviewer compare MU against a known benchmark?",
            "Was the plan paused before treatment booking or only before first fraction?",
        ],
        "tags": ["whole_brain", "manual_entry", "physics_check", "mu_outlier"],
        "source": {
            "label": "RO-ILS Case Study 16",
            "url": "https://www.astro.org/practice-support/quality-and-safety/ro-ils/case-studies/case-study-16",
        },
    },
    {
        "id": "roils_case_11",
        "title": "Adjacent isocenters and timeout failure",
        "theme": "setup_timeout",
        "category": "Treatment Delivery",
        "process_step": "Pre Beam-On",
        "severity_hint": "alert",
        "evidence_level": "Published case study",
        "signals": [
            "adjacent isocenter",
            "timeout",
            "setup",
            "therapist",
            "distraction",
            "beam on",
            "spine",
        ],
        "summary": (
            "Complex adjacent-isocenter setup patterns become high risk when the timeout barrier is rushed or "
            "not shared across room and console staff."
        ),
        "contributing_factors": [
            "Complex patient setup with more than one isocenter",
            "Distraction or interruption during final setup confirmation",
            "Incomplete shared mental model across treatment team members",
        ],
        "detection_indicators": [
            "Therapist concern raised close to beam-on",
            "Documented distraction during setup verification",
            "Repeated couch/isocenter re-checks",
        ],
        "recommended_checks": [
            "Enforce structured timeout completion before beam-on.",
            "Highlight adjacent-isocenter cases as elevated setup risk.",
            "Escalate when therapists cannot reconcile setup context immediately.",
        ],
        "mitigation_playbook": [
            "Pause treatment start until all team members verbally confirm isocenter identity.",
            "Add a visible adjacent-isocenter banner to console workflow.",
            "Require supervisor review for repeated timeout uncertainty.",
        ],
        "review_questions": [
            "Was the timeout completed by both room and console staff?",
            "Did the team acknowledge the case as adjacent-isocenter before setup?",
            "Were there distractions or staffing changes during setup?",
        ],
        "tags": ["adjacent_isocenter", "timeout", "therapist", "delivery"],
        "source": {
            "label": "RO-ILS Case Study 11",
            "url": "https://www.astro.org/practice-support/quality-and-safety/ro-ils/case-studies/case-study-11",
        },
    },
    {
        "id": "roils_case_02",
        "title": "Adaptive planning communication delay",
        "theme": "adaptive_planning",
        "category": "Adaptive Workflow",
        "process_step": "Adaptive Review",
        "severity_hint": "watch",
        "evidence_level": "Published case study",
        "signals": [
            "adaptive",
            "qact",
            "repeat ct",
            "replan",
            "communication",
            "physician acknowledgement",
            "document",
        ],
        "summary": (
            "Adaptive planning decisions can stall between imaging, recalculation, and physician documentation, "
            "leaving a hidden release risk."
        ),
        "contributing_factors": [
            "Fragmented ownership across physics, physicians, and therapists",
            "Missing due-date visibility for adaptive review",
            "No hard-stop if physician acknowledgement is absent",
        ],
        "detection_indicators": [
            "Repeat CT completed without adaptive note in record",
            "Recalculation performed but no signed physician decision",
            "Replan status unclear during same-day treatment pressure",
        ],
        "recommended_checks": [
            "Track adaptive review due dates explicitly.",
            "Require physician acknowledgement for adaptive decisions.",
            "Audit whether replanning decisions were documented in the oncology record.",
        ],
        "mitigation_playbook": [
            "Create an adaptive review queue with physician owner and due time.",
            "Block release if the oncology record lacks a signed adaptive decision.",
            "Log whether recalculation changed target coverage or OAR constraints.",
        ],
        "review_questions": [
            "Is there a signed physician decision for this adaptive branch?",
            "Was recalculation completed before the case entered treatment readiness?",
            "Did the oncology record capture whether replanning is required?",
        ],
        "tags": ["adaptive", "qact", "documentation", "replan"],
        "source": {
            "label": "RO-ILS Case Study 02",
            "url": "https://www.astro.org/practice-support/quality-and-safety/ro-ils/case-studies/case-study-02",
        },
    },
    {
        "id": "roils_case_09",
        "title": "Contouring and naming convention mismatch",
        "theme": "contouring_naming",
        "category": "Contouring",
        "process_step": "Target Definition",
        "severity_hint": "alert",
        "evidence_level": "Published case study",
        "signals": [
            "contour",
            "naming",
            "ptv",
            "ctv",
            "expansion",
            "template mismatch",
            "second check",
        ],
        "summary": (
            "Structure naming mismatches can hide contouring or expansion errors and blunt the effectiveness of "
            "second-check review."
        ),
        "contributing_factors": [
            "Non-standard structure naming across planners",
            "Protocol assumptions not explicit in peer review",
            "Template drift between disease sites or planning systems",
        ],
        "detection_indicators": [
            "Unexpected target names in plan export",
            "PTV/CTV naming pattern does not match protocol template",
            "Reviewer uncertainty about expansion source",
        ],
        "recommended_checks": [
            "Standardize contour naming conventions and expansion labels.",
            "Require second-check review of target generation assumptions.",
            "Alert when structure names do not align with protocol templates.",
        ],
        "mitigation_playbook": [
            "Run a naming compliance check before physics handoff.",
            "Highlight manual contour deviations for physician sign-off.",
            "Capture whether target expansions were automated or manual.",
        ],
        "review_questions": [
            "Do structure names match site protocol naming rules?",
            "Was target expansion performed manually or by automation?",
            "Did the second check explicitly verify target identity?",
        ],
        "tags": ["contour", "ptv", "ctv", "template"],
        "source": {
            "label": "RO-ILS Case Study 09",
            "url": "https://www.astro.org/practice-support/quality-and-safety/ro-ils/case-studies/case-study-09",
        },
    },
    {
        "id": "roils_case_15",
        "title": "Brachytherapy applicator digitization risk",
        "theme": "brachytherapy",
        "category": "Brachytherapy",
        "process_step": "Applicator Reconstruction",
        "severity_hint": "urgent",
        "evidence_level": "Published case study",
        "signals": [
            "brachytherapy",
            "applicator",
            "digitization",
            "hdr",
            "specialized",
            "source path",
        ],
        "summary": (
            "Specialized HDR workflows concentrate risk because an applicator digitization issue can propagate "
            "directly into a high-dose event."
        ),
        "contributing_factors": [
            "Limited staffing familiar with HDR-specific workflow",
            "High consequence from small spatial reconstruction errors",
            "Case complexity and equipment setup variance",
        ],
        "detection_indicators": [
            "Applicator reconstruction discrepancy",
            "Unclear source path or channel definition",
            "Checklist gaps in specialized HDR workflow",
        ],
        "recommended_checks": [
            "Require dedicated brachytherapy checklist completion.",
            "Escalate applicator digitization discrepancies immediately.",
            "Confirm specialized staff and equipment readiness before treatment.",
        ],
        "mitigation_playbook": [
            "Block treatment release until applicator path is independently verified.",
            "Use a dedicated HDR readiness checklist with named reviewer.",
            "Capture whether reconstruction differs from historical implant pattern.",
        ],
        "review_questions": [
            "Did an HDR-trained reviewer confirm source path reconstruction?",
            "Was the specialized checklist completed and attached?",
            "Is this a standard applicator geometry or a novel setup?",
        ],
        "tags": ["hdr", "applicator", "digitization", "high_dose"],
        "source": {
            "label": "RO-ILS Case Study 15",
            "url": "https://www.astro.org/practice-support/quality-and-safety/ro-ils/case-studies/case-study-15",
        },
    },
    {
        "id": "roils_case_19",
        "title": "Automation or AI output requires human confirmation",
        "theme": "automation_validation",
        "category": "Automation Governance",
        "process_step": "Cross-Cutting",
        "severity_hint": "watch",
        "evidence_level": "Published case study",
        "signals": [
            "automation",
            "ai",
            "autosegmentation",
            "auto",
            "human confirmation",
            "workflow software",
        ],
        "summary": (
            "Automation accelerates planning, but missing human confirmation can silently propagate incorrect "
            "contours, plan assumptions, or workflow state."
        ),
        "contributing_factors": [
            "False trust in automation defaults",
            "Workflow software hides whether a human reviewed the result",
            "No escalation for high-impact auto-generated outputs",
        ],
        "detection_indicators": [
            "Automation output moved downstream without reviewer signature",
            "Autosegmentation changed planning assumptions unexpectedly",
            "Workflow record lacks explicit human validation event",
        ],
        "recommended_checks": [
            "Require documented human confirmation before downstream approval.",
            "Track whether automation changed target or planning assumptions.",
            "Escalate high-impact automation outputs for physics review.",
        ],
        "mitigation_playbook": [
            "Record explicit human validation events for each automated handoff.",
            "Force review if automation altered target set or plan objectives.",
            "Keep an audit trail of automation-generated deltas.",
        ],
        "review_questions": [
            "Who validated the automation output before downstream use?",
            "Did automation change targets, objectives, or dose constraints?",
            "Would a reviewer recognize this as an automation-derived artifact?",
        ],
        "tags": ["automation", "human_review", "audit", "validation"],
        "source": {
            "label": "RO-ILS Case Study 19",
            "url": "https://www.astro.org/practice-support/quality-and-safety/ro-ils/case-studies/case-study-19",
        },
    },
    {
        "id": "quarterly_wrong_laterality",
        "title": "Laterality mismatch across planning handoff",
        "theme": "laterality_mismatch",
        "category": "Handoff Integrity",
        "process_step": "Plan Review",
        "severity_hint": "urgent",
        "evidence_level": "Quarterly trend report",
        "signals": [
            "laterality",
            "left",
            "right",
            "handoff",
            "wrong side",
            "breast",
            "plan review",
        ],
        "summary": (
            "Laterality mismatches persist as a high-consequence handoff risk when planning context and treatment "
            "intent are not re-confirmed during review."
        ),
        "contributing_factors": [
            "Multiple copies of planning documentation",
            "Human review focuses on dosimetry but not side-specific context",
            "Disease site naming inconsistency",
        ],
        "detection_indicators": [
            "Left/right language inconsistent between consult and plan",
            "Beam naming or prescription notes reference the opposite side",
            "Reviewer uncertainty during final chart check",
        ],
        "recommended_checks": [
            "Confirm laterality against consult, simulation, and active plan.",
            "Add visible laterality status to final review.",
            "Escalate any side mismatch before scheduling treatment.",
        ],
        "mitigation_playbook": [
            "Require laterality confirmation during chart rounds.",
            "Surface opposite-side language mismatch as urgent.",
            "Track whether side-specific structure names match prescription intent.",
        ],
        "review_questions": [
            "Do consult, simulation, and plan all agree on laterality?",
            "Is any copied note referencing the opposite side?",
            "Was laterality explicitly confirmed during final plan review?",
        ],
        "tags": ["laterality", "handoff", "breast", "wrong_side"],
        "source": {
            "label": "RO-ILS Quarterly Reports",
            "url": "https://www.astro.org/practice-support/quality-and-safety/ro-ils",
        },
    },
]


INCOMING_CASES = [
    {
        "id": "incoming_case_001",
        "title": "Whole brain plan with unusually high MU after manual entry",
        "submitted_by": "Dosimetrist queue",
        "received_at": "2026-03-18T09:05:00+00:00",
        "status": "new",
        "owner": "Physics lead",
        "queue": "Plan review",
        "due_at": "2026-03-18T13:30:00+00:00",
        "patient_label": "WBRT-2048",
        "machine": "TrueBeam 2",
        "service_line": "CNS",
        "free_text": (
            "Whole brain treatment prepared from physician prescription. Manual transcription into the planning "
            "system may have introduced an extra zero. Physics noted monitor units far above expected range "
            "during first check and paused release."
        ),
        "fields": {
            "site": "Whole brain",
            "technique": "3D conformal RT",
            "stage": "plan review",
            "channel": "Dosimetry handoff",
        },
    },
    {
        "id": "incoming_case_002",
        "title": "Adjacent isocenter setup confusion before beam-on timeout",
        "submitted_by": "Therapist console",
        "received_at": "2026-03-18T10:20:00+00:00",
        "status": "new",
        "owner": "Treatment unit supervisor",
        "queue": "Delivery readiness",
        "due_at": "2026-03-18T11:30:00+00:00",
        "patient_label": "TSP-7112",
        "machine": "Halcyon 1",
        "service_line": "Spine",
        "free_text": (
            "Thoracic spine case with adjacent isocenters. Therapist reported distraction during setup and "
            "concern that timeout steps were not completed with full agreement between room and console staff."
        ),
        "fields": {
            "site": "Thoracic spine",
            "technique": "VMAT",
            "stage": "treatment delivery",
            "channel": "Console safety flag",
        },
    },
    {
        "id": "incoming_case_003",
        "title": "Adaptive review note missing after repeat CT",
        "submitted_by": "Physics QA feed",
        "received_at": "2026-03-18T11:15:00+00:00",
        "status": "new",
        "owner": "Adaptive workflow coordinator",
        "queue": "Adaptive review",
        "due_at": "2026-03-18T15:00:00+00:00",
        "patient_label": "HN-3156",
        "machine": "Ethos 3",
        "service_line": "Head and neck",
        "free_text": (
            "Head and neck patient had quality assurance repeat CT. Recalculation was performed, but the adaptive "
            "planning note was not visible in the oncology record and physician acknowledgement was not confirmed."
        ),
        "fields": {
            "site": "Head and neck",
            "technique": "IMRT adaptive workflow",
            "stage": "adaptive review",
            "channel": "Physics QA feed",
        },
    },
]


def _tokenize(text: str) -> set[str]:
    cleaned = "".join(char.lower() if char.isalnum() else " " for char in text)
    return {token for token in cleaned.split() if len(token) > 2}


def _score_match(source_text: str, item: dict[str, Any]) -> tuple[int, list[str]]:
    tokens = _tokenize(source_text)
    score = 0
    matched_signals: list[str] = []
    for signal in item["signals"]:
        signal_tokens = _tokenize(signal)
        if signal_tokens and signal_tokens.issubset(tokens):
            score += len(signal_tokens) + 1
            matched_signals.append(signal)
    return score, matched_signals[:5]


def _match_case(case: dict[str, Any]) -> list[dict[str, Any]]:
    source_text = " ".join(
        [
            case["title"],
            case["free_text"],
            " ".join(case["fields"].values()),
            case["service_line"],
        ]
    )
    matches: list[dict[str, Any]] = []
    for item in KNOWLEDGE_BASE:
        score, matched_signals = _score_match(source_text, item)
        if score:
            matches.append(
                {
                    "knowledge_id": item["id"],
                    "title": item["title"],
                    "theme": item["theme"],
                    "category": item["category"],
                    "process_step": item["process_step"],
                    "severity_hint": item["severity_hint"],
                    "evidence_level": item["evidence_level"],
                    "score": score,
                    "matched_signals": matched_signals,
                    "summary": item["summary"],
                    "contributing_factors": item["contributing_factors"],
                    "detection_indicators": item["detection_indicators"],
                    "recommended_checks": item["recommended_checks"],
                    "mitigation_playbook": item["mitigation_playbook"],
                    "review_questions": item["review_questions"],
                    "tags": item["tags"],
                    "source": item["source"],
                }
            )
    matches.sort(key=lambda entry: (entry["score"], entry["severity_hint"] == "urgent"), reverse=True)
    return matches


def _risk_tier(matches: list[dict[str, Any]]) -> str:
    if not matches:
        return "watch"
    top = matches[0]
    if top["severity_hint"] == "urgent" and top["score"] >= 4:
        return "urgent"
    if top["severity_hint"] in {"alert", "urgent"} and top["score"] >= 3:
        return "alert"
    return "watch"


def _status_copy(tier: str) -> dict[str, str]:
    mapping = {
        "watch": {
            "label": "Watch",
            "reason": "Pattern overlap exists, but immediate escalation is not yet required.",
        },
        "alert": {
            "label": "Alert",
            "reason": "Case overlaps strongly with a known failure mode and should be reviewed today.",
        },
        "urgent": {
            "label": "Urgent",
            "reason": "Case resembles a high-severity historical failure mode and should trigger immediate attention.",
        },
    }
    return mapping[tier]


def _queue_summary(cases: dict[str, dict[str, Any]]) -> dict[str, int]:
    summary = {"watch": 0, "alert": 0, "urgent": 0}
    for case in cases.values():
        summary[case["risk_tier"]] += 1
    return summary


def _summary_cards(case: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"label": "Risk", "value": case["risk_label"], "tone": case["risk_tier"]},
        {"label": "Owner", "value": case["owner"], "tone": "neutral"},
        {"label": "Queue", "value": case["queue"], "tone": "neutral"},
        {"label": "Due", "value": case["due_at"], "tone": "neutral"},
    ]


def _case_timeline(case: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "title": "Case entered monitor",
            "detail": f"{case['submitted_by']} created the intake record.",
            "created_at": case["received_at"],
        },
        {
            "title": "Pattern engine completed initial scan",
            "detail": f"Assigned {case['risk_label']} using local failure knowledge base.",
            "created_at": case["received_at"],
        },
        {
            "title": "Action deadline pending",
            "detail": f"Current owner: {case['owner']} with queue target {case['queue']}.",
            "created_at": case["due_at"],
        },
    ]


def _knowledge_base_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "title": item["title"],
        "theme": item["theme"],
        "category": item["category"],
        "process_step": item["process_step"],
        "severity_hint": item["severity_hint"],
        "evidence_level": item["evidence_level"],
        "source": item["source"],
    }


class SafetyMonitorStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._cases = self._seed_cases()

    def _seed_cases(self) -> dict[str, dict[str, Any]]:
        seeded: dict[str, dict[str, Any]] = {}
        for case in INCOMING_CASES:
            matches = _match_case(case)
            tier = _risk_tier(matches)
            status = _status_copy(tier)
            top = matches[0] if matches else None
            seeded_case = {
                **case,
                "risk_tier": tier,
                "risk_label": status["label"],
                "risk_reason": status["reason"],
                "matched_incidents": matches,
                "summary_cards": [],
                "timeline": [],
                "playbook": top["mitigation_playbook"] if top else [],
                "review_questions": top["review_questions"] if top else [],
                "review": {
                    "status": "open",
                    "comment": "Awaiting QA review.",
                    "updated_at": _now_iso(),
                },
                "mock_email": {
                    "to": "qa-lead@clinicalclaw.demo",
                    "subject": f"[{status['label']}] Safety monitor case {case['id']}",
                    "body": (
                        f"Case {case['id']} ({case['title']}) triggered {status['label']} based on RO-ILS-style "
                        f"pattern matching. Review recommended before downstream release."
                    ),
                    "sent": tier in {"alert", "urgent"},
                },
                "audit": [
                    {
                        "id": f"audit_seed_{case['id']}",
                        "title": "Initial pattern scan completed",
                        "detail": f"Knowledge-base matcher found {len(matches)} relevant historical patterns.",
                        "severity": "info",
                        "created_at": _now_iso(),
                    }
                ],
            }
            seeded_case["summary_cards"] = _summary_cards(seeded_case)
            seeded_case["timeline"] = _case_timeline(seeded_case)
            seeded[case["id"]] = seeded_case
        return seeded

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            default_case_id = next(iter(self._cases))
            queue = _queue_summary(self._cases)
            return {
                "cases": [
                    {
                        "id": case["id"],
                        "title": case["title"],
                        "risk_tier": case["risk_tier"],
                        "risk_label": case["risk_label"],
                        "status": case["status"],
                        "received_at": case["received_at"],
                        "submitted_by": case["submitted_by"],
                        "owner": case["owner"],
                        "queue": case["queue"],
                    }
                    for case in self._cases.values()
                ],
                "knowledge_base": [_knowledge_base_summary(item) for item in KNOWLEDGE_BASE],
                "queue_summary": queue,
                "default_case_id": default_case_id,
                "workspace": deepcopy(self._cases[default_case_id]),
            }

    def get_case(self, case_id: str) -> dict[str, Any]:
        with self._lock:
            case = self._cases.get(case_id)
            if not case:
                raise KeyError(case_id)
            return deepcopy(case)

    def rerun(self, case_id: str) -> dict[str, Any]:
        with self._lock:
            case = self._cases[case_id]
            matches = _match_case(case)
            tier = _risk_tier(matches)
            status = _status_copy(tier)
            top = matches[0] if matches else None
            case["matched_incidents"] = matches
            case["risk_tier"] = tier
            case["risk_label"] = status["label"]
            case["risk_reason"] = status["reason"]
            case["playbook"] = top["mitigation_playbook"] if top else []
            case["review_questions"] = top["review_questions"] if top else []
            case["mock_email"]["sent"] = tier in {"alert", "urgent"}
            case["summary_cards"] = _summary_cards(case)
            case["timeline"] = _case_timeline(case)
            case["audit"].insert(
                0,
                {
                    "id": f"audit_rerun_{case_id}_{ceil(datetime.now(UTC).timestamp())}",
                    "title": "Pattern matcher rerun",
                    "detail": f"Refreshed case risk tier to {status['label']} after rescoring historical failure overlap.",
                    "severity": "success" if tier in {"alert", "urgent"} else "info",
                    "created_at": _now_iso(),
                },
            )
            return deepcopy(case)

    def review(self, case_id: str, action: str, comment: str | None = None) -> dict[str, Any]:
        with self._lock:
            case = self._cases[case_id]
            normalized = action.strip().lower()
            case["review"]["status"] = normalized
            case["review"]["comment"] = comment or case["review"]["comment"]
            case["review"]["updated_at"] = _now_iso()
            case["audit"].insert(
                0,
                {
                    "id": f"audit_review_{case_id}_{ceil(datetime.now(UTC).timestamp())}",
                    "title": f"Reviewer action: {normalized}",
                    "detail": comment or f"Reviewer changed case state to {normalized}.",
                    "severity": "warning" if normalized in {"reject", "urgent"} else "success" if normalized == "approve" else "info",
                    "created_at": _now_iso(),
                },
            )
            return deepcopy(case)

    def explain(self, case_id: str, question: str) -> dict[str, Any]:
        with self._lock:
            case = self._cases[case_id]
            lowered = question.lower()
            if "email" in lowered or "alert" in lowered:
                answer = (
                    f"This case is currently {case['risk_label']}. The mock email alert is "
                    f"{'prepared and marked sent' if case['mock_email']['sent'] else 'prepared but not sent'} "
                    f"to {case['mock_email']['to']}."
                )
            elif "owner" in lowered or "next" in lowered or "action" in lowered:
                answer = (
                    f"The active owner is {case['owner']}. Next recommended actions are: "
                    f"{'; '.join(case['playbook'][:2])}."
                )
            else:
                top = case["matched_incidents"][0] if case["matched_incidents"] else None
                answer = (
                    f"The top match is {top['title']} in {top['category']} / {top['process_step']} because the "
                    f"incoming text overlaps with signals such as {', '.join(top['matched_signals'])}."
                    if top
                    else "No strong historical failure mode overlap was found. The case remains under watch."
                )
            case["audit"].insert(
                0,
                {
                    "id": f"audit_chat_{case_id}_{ceil(datetime.now(UTC).timestamp())}",
                    "title": "Safety explainer used",
                    "detail": answer,
                    "severity": "info",
                    "created_at": _now_iso(),
                },
            )
            return {"answer": answer, "workspace": deepcopy(case)}


safety_monitor_store = SafetyMonitorStore()
