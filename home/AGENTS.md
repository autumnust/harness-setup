# Communication style

## Lead explanations with concept, not code

When explaining a bug, a design issue, or "why X is happening," structure the
explanation by abstraction level: concept first, code anchors last.

**Order to use:**
1. What the user should be experiencing, or what the system was promising.
2. The symptom in domain language (what's actually visible to them).
3. The conceptual gap — what guarantee is broken, what input the system
   should have tracked but didn't, what the design assumed and shouldn't
   have.
4. Only then mention specific functions, structs, fields, file paths — and
   only as anchors for "the fix lives here," not as the explanation itself.

**Smell test:** if the first paragraph has more backticks than verbs, the
explanation has been led by code. Rewrite leading with what the user
notices.

### Example — explaining a cache-staleness bug

❌ Code-first (avoid):

> `cache.Save` filters items by the `focusSet` it's given at write time and
> writes a file keyed only on `projectURL`. When focus changes later,
> `cache.Load` returns a stale snapshot because the cache identity doesn't
> include focus.

✅ Concept-first (prefer):

> The board shows a snapshot of issues currently relevant to your team.
> Relevance comes from your focus list. You changed that list, but the
> board kept showing the old set — because the saved snapshot's identity
> was "the snapshot for this project," not "the snapshot for this project
> as filtered by these focus issues." Two inputs shaped what got saved,
> but only one was part of how the saved copy identified itself, so a
> stale snapshot got served undetected.

The technical content is identical. The difference is whether the reader
has to swim through the code to extract the mental model, or gets the
mental model up front.

### When to skip this rule

- The user explicitly asks for a code walkthrough, debugger-level
  inspection, or implementation review.
- The user's question is itself at the implementation level (e.g., "what
  does this function return") — match their abstraction level instead of
  forcing a higher one.
- A short, scoped technical answer is what's wanted.

# Available skill catalog

Customized agent skills live in `~/Documents/kumo-skills-catalog` (repo:
`kumo-ai/kumo-skills-catalog`). It's an [agentskills.io](https://agentskills.io)
catalog with a **per-project** install model — `install.sh` or
`sync-skills-catalog.py` symlinks selected skills into a project's
`.agents/skills/` and registers them as slash commands under
`.claude/commands/`. Skills are not auto-loaded globally; they have to be
installed per consuming repo.

**Browsing what's available:** read `<catalog>/README.md` for the table,
or look in the domain dirs (`collab/`, `github/`, `VPC/`, `aws/`, `kumo/`)
for individual `SKILL.md` files. Notable ones I should know exist:

- `collab/annotate-iterate` — iterate on a written doc / RFC / spec via
  inline `annotate:` markers. Use when the user reviews a markdown file
  by editing in `annotate:` lines and expects me to address each one in
  place. Stable protocol for first-pass replies, follow-ups, resolution,
  and promotion of inline answers into the doc body.
- `github/gh-issue-management`, `github/learn-diff` — GitHub workflows.
- `VPC/*`, `aws/billing-investigate`, `kumo/kumo-rfm-agent`,
  `kumo/kumo-tuning-agent` — domain-specific (Kumo infra / SDK).

**When the user references a catalog skill by name** that isn't in the
current session's available-skills list:
1. Check whether the project has the catalog installed
   (`.agents/skills/<name>` or `.claude/commands/<name>`).
2. If not, read the SKILL.md from the catalog directly
   (`~/Documents/kumo-skills-catalog/<domain>/<name>/SKILL.md`) and
   follow it as a manual procedure — don't blindly invoke `Skill(...)`,
   since the runtime won't have the schema loaded.
3. Offer to install it for the project via the catalog's sync script if
   the workflow looks like it'll recur.
