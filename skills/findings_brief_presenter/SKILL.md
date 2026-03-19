---
name: findings-brief-presenter
description: Use when a findings_closure workflow needs a compact, clinician-facing or operator-facing brief. Especially useful for actionable radiology findings that need a clear signal line, closure check, next step, and review status without verbose narrative.
---

# Findings Brief Presenter

Use this skill when the workflow belongs to the `findings_closure` family, with extra emphasis on actionable radiology findings.

## Goal

Turn raw workflow output into a compact closure brief that answers four questions fast:

1. What was found?
2. Has the finding already been closed?
3. What is the next safest action?
4. Does the case need review or escalation now?

## Output Frame

Use short markdown sections with one or two sentences each.

1. `Signal`
2. `Closure Check`
3. `Recommended Next Step`
4. `Review Status`

Start with a one-line lead only when it adds value:

- for urgent findings: one short escalation line
- for already addressed findings: one short closure line

## Radiology-Specific Guidance

For actionable radiology findings:

- name the radiology signal in plain language
- mention the requested follow-up if it is explicit in the source text
- preserve timeframe language when it is present:
  - `same day`
  - `24-48 hours`
  - `short-interval follow-up`
  - `3 months`
  - `6 months`
- mention ownership only if the case provides an owner or responsible team
- if there is a concise evidence phrase, use a short quoted fragment rather than reproducing the full report

## Style Rules

- Keep the answer compact and scannable.
- Prefer short paragraphs over long bullet lists.
- Do not expose tool names, internal routing, rule identifiers, or chain-of-thought.
- Do not restate the entire report.
- Use calm clinical language.
- If the case is urgent, say so clearly in one short line.

## Constraints

- Do not invent patient details, modality details, or follow-up instructions.
- Do not claim a finding is resolved unless the case explicitly says so.
- Do not imply that an order was placed, a patient was notified, or scheduling happened unless the workflow says so.
- If closure is still open, name one primary next step rather than listing every possible downstream action.
