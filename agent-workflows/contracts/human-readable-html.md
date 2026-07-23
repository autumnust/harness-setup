# Human-readable HTML contract

This contract applies whenever the coordinator publishes HTML for a human user,
including `progress.html`, execution dashboards, education briefs, reports, and
indexes. The HTML is an operational reading surface, not an unstyled data dump.

- Make each artifact self-contained by default: use semantic HTML and inline
  CSS, with no remote font, script, or stylesheet dependency unless the task
  explicitly requires one.
- Start with the artifact title, current status or purpose, last-updated time,
  and the most important next action. Organize the remaining content into
  plainly named sections in reading order.
- Use a system font at a readable base size, at least `1.5` line height,
  restrained line length, clear heading levels, and visible keyboard focus.
  Keep letter spacing at `0` and do not scale type with viewport width.
- Use high-contrast neutral surfaces plus distinct status colors. Never rely on
  color alone: pair status color with text such as `Ready`, `Blocked`, or
  `Complete`.
- Keep dense operational data scannable. Align labels and values, place wide
  tables in horizontal overflow containers, let code blocks scroll, and avoid
  decorative sections or nested cards.
- Make every referenced file, section, PR, issue, and external resource a
  descriptive clickable link. Do not display a bare path when the rendered
  artifact can link to it.
- Use a responsive layout that supports narrow and desktop screens without
  overlapping or clipped text. Include print styles that remove
  navigation-only controls and preserve readable contrast.
- Before publishing, render or open the artifact when browser tooling is
  available. Check one desktop width and one narrow width, verify that links
  resolve as intended, and fix overflow or unreadable contrast.

Use `templates/education-brief.html` as a compact styling reference. Adapt its
information structure to the artifact; do not force education-specific
sections into execution dashboards.
