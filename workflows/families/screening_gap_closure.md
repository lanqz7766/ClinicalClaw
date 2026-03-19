# Screening Gap Closure

`screening_gap_closure` is the workflow family for identifying overdue or unresolved screening follow-up, preparing the next clinical step, and routing the case into a review-first operational queue.

## Operating Pattern

1. Detect a screening signal.
2. Check whether the recommended follow-up is already ordered, scheduled, or completed.
3. If the gap is still open, draft the next action and create a review item.
4. Keep escalation human-approved before any outreach or ordering is finalized.

## First Workflow

- `screening_gap_positive_fit_followup`
  - input: positive FIT result text + follow-up summary
  - output: gap signal, review recommendation, order draft suggestion, outreach draft

## Skill Pairing

- presentation skill: `screening_gap_presenter`
- base formatting skill: `clinical_report_presentation`

## Recommended Next Workflows

- lung cancer screening eligibility
- cervical screening gap closure
- diabetic eye exam follow-up
