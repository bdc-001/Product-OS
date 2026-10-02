# Release-note writing and design standard

Reference: the operator-edited Agent Monitoring release note, reviewed 28 September 2026:
https://docs.google.com/document/d/1O8GTi4QTeu5T8juBKXyh-vZWCHL3A8yLFXrkZIHUnVI/edit

This reference governs editorial quality and presentation. Its product facts, screenshots,
plan limits, navigation, category and contacts are not facts about another feature.
Preserve the edited source document; never replace it during campaign regeneration.

## Content

- Title: the buyer-facing feature name only. No long marketing headline, subtitle or audience preamble.
- Leave `dek` empty. The overview is the opening paragraph, without an Overview heading.
  Explain what the feature does, what the operator sees and what decision it enables in 40–75 words.
- Pre-requisites: explain activation, access, plan scope and sampling limits when supported.
  Distinguish eligibility, activation and limits; free availability never implies automatic activation.
- Workflow: Run and Review (adapt to the actual feature): numbered actions in execution order.
  Include the exact evidenced entry point, choices, filters, controls and expected result.
  When navigation is unknown, describe the supported action without inventing a menu path.
- How to Read the Results: name and explain actual outputs and how to interpret them.
  Use short bullets for parallel outputs or checks, without repeating the workflow.
- Action: explain the next decision, review/approval/application controls and the resulting change.
  Keep recommendations distinct from product behavior. Do not invent an approval flow for a read-only feature.
- Troubleshooting: specific symptom, explanation and supported recovery or contact.
- Limitations: sampling, scope, concurrency and known boundaries that change how the operator uses the feature.
- End with a short activation/help step supported by the current source. Do not append a sales essay.

Prefer the amount of useful detail in the reference, not a word target padded with generic benefits.
No internal component identifiers, source-audit commentary, boilerplate buyer/audience sections or repeated introductions.

## Images and presentation

- Nunito throughout, 11pt body, 22pt title, 14pt primary headings, restrained navy text on white.
- Place the actual lockup at the top right, repeating on each page; use normal document flow.
- Headings are descriptive and easy to scan. Ordered steps and bullets remain native list structures.
  If a section needs subheadings, mark them as `### Short label` in its body so they render as native
  subheadings. Avoid unnecessary subheadings and "Expected result" repeated on every numbered step.
- Keep each image with its caption and relevant section. Screenshots must come from the current feature's
  supplied or verified product captures; never fabricate a UI. The reference's captures are not transferable.
- Include explanatory diagrams for supported mechanisms and plan comparisons. Label them conceptual.
  They complement genuine product screenshots where those are supplied, rather than pretending to be screenshots.
- Figures must be readable at page width. No tiny full-screen captures, clipped labels or needless decoration.
- Keep source content editable in Google Docs, with semantic headings, lists and embedded images.
- Existing native reference dropdowns and other controls remain intact when working in a copied template.
  Do not infer another feature's category from the reference's selected value.
- Inspect every exported page for typography, image placement, split headings and blank pages.
