---
name: queue-triage-presenter
description: Use when a queue_triage workflow needs a compact, case-centric triage brief for referral or follow-up prioritization.
---

# Queue Triage Presenter

Use this skill when the workflow belongs to the `queue_triage` family.

## Goal

Turn raw queue-triage output into a compact case-centric brief that answers four questions fast:

1. What queue signal triggered review?
2. What is the current queue status or timing window?
3. What is the safest next queue move?
4. Does the case still need reviewer sign-off?

## Output Frame

Use short markdown sections with one or two sentences each.

1. `Case Signal`
2. `Queue Status`
3. `Recommended Queue Move`
4. `Review Status`

If the workflow is more follow-up oriented than queue-lane oriented, `Recommended Next Step` is also acceptable as the third section label.

If the case is clearly urgent, start with one short escalation line.

## Triage-Specific Guidance

For referral or follow-up triage cases:

- name the urgency signal in plain language
- mention the timing window if it is explicit in the case
- preserve short operational timing language when it is present:
  - `same day`
  - `24-48 hours`
  - `within 7 days`
  - `routine queue`
- mention the owner only if the case provides an owner or responsible team
- prefer one recommended queue move over a long list of options

## Style Rules

- Keep the answer compact and scannable.
- Prefer short paragraphs over long bullet lists.
- Keep the brief case-centric and operational.
- Do not expose tool names, internal routing, rule identifiers, or chain-of-thought.
- Use calm clinical operations language.

## Constraints

- Do not invent patient details or queue actions.
- Do not say a case has already been moved unless the case explicitly says so.
- If the case is still open, name one primary next step.
