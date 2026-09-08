# Rendering Guidance

Use this guidance after the source has been read and the explanation model is complete.

## Template Contract

Copy `assets/template.html` into a task-owned scratch directory and replace:

- `{{LANG}}` with an appropriate BCP 47 language tag.
- `{{TITLE}}` with a concise HTML-escaped title.
- `{{SOURCE}}` with the HTML-escaped source path or URL.
- `{{REVISION}}` with the HTML-escaped revision or snapshot identifier.
- `{{BODY}}` with the explanation sections.

Do not remove the provenance metadata, visible derived-view notice, page-height script, or source
revision. Do not add external scripts, stylesheets, fonts, images, frames, media, CSS imports, or
runtime network requests. External hyperlinks in ordinary anchor elements are allowed as source
references.

## Reading Order

Use the smallest structure that makes the target easier to understand. A useful default order is:

1. One- or two-sentence overview using `.tldr`.
2. A prerequisite or likely misunderstanding using `.headline`, when needed.
3. A flow, relationship, hierarchy, or exact mapping that benefits from a visual form.
4. Documented decisions using `D-` identifiers.
5. Source coverage, interpretations, unresolved items, and questions.
6. Pointers to the most valuable parts of the original source.

Do not create a diagram merely because the page has several sections. Keep related explanation
beside the visual element it qualifies.

## Available Components

- `.section-heading` and `.section-number` establish a stable section hierarchy.
- `.grid` and `.card` compare several cohesive concepts.
- `.label.fact`, `.label.interpretation`, and `.label.unverified` identify epistemic status.
- `.id` displays a `D-`, `U-`, or `Q-` identifier.
- `.flow` and `.step` show a short linear sequence.
- `.layers` and `.layer` show hierarchy or dependency direction.
- `.table-wrap` contains an exact mapping or comparison table.
- `.diagram` contains a self-contained inline SVG for branching or non-linear relationships.
- `.callout`, `.coverage-list`, `.question-list`, and `.ask` provide supporting detail.

Use inline SVG only when HTML and CSS components cannot express the relationship clearly. Give the
SVG a `viewBox`, `role="img"`, and an informative `aria-label`. Keep text readable without zooming,
avoid encoding meaning through color alone, and place detailed prose outside the SVG.

## Fidelity Rules

- Attach a fact label only to claims directly supported by identified source material.
- Attach an interpretation label when combining facts or inferring a consequence not stated in the
  source.
- Attach an unverified label to inaccessible, contradictory, ambiguous, or explicitly unresolved
  material.
- Quote only when exact wording is necessary and keep the excerpt short. Prefer a source pointer
  and a faithful paraphrase.
- Escape source text before placing it in HTML, including code examples and user-supplied labels.
- Avoid visual prominence that implies an interpretation is more authoritative than a fact.

## Visual Inspection

Inspect the verifier's screenshot at a normal reading width. Check that:

- No label, code block, table, or diagram is clipped or overlaps another element.
- The page does not require excessive horizontal scrolling.
- Heading hierarchy and reading order remain obvious.
- Facts, interpretations, and unverified items are distinguishable without relying on color alone.
- Tables have useful column proportions and remain legible.
- Inline SVG text is large enough and connectors point in the intended direction.
- Source, revision, coverage, and derived-view status are visible.

Revise the HTML and repeat both mechanical verification and visual inspection until the result is
usable. A successful script result does not replace human visual inspection.
