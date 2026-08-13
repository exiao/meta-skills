# Installing & Integrating Third-Party Skills

How to bring a skill published elsewhere (the `skills` CLI / GitHub) into the
Hermes library cleanly, and the gotchas that bite during integration.

## Installing from the `skills` registry

Third-party skills are distributed via `npx skills add <org>/<repo>` (e.g.
`npx skills add diffusionstudio/lottie`). Notes:

- The installer is **interactive by default** (prompts for which agents to
  install to). Pass `--yes --global` to skip the prompts:
  `npx skills add <org>/<repo> --yes --global`.
- It installs to `~/.agents/skills/<name>` (the universal location) and creates
  **symlinks** into each agent's skill dir, including
  `~/.hermes/skills/<name> -> ../../.agents/skills/<name>`.
- Files land with **restrictive perms** (`-rw-------`, sometimes `u` only). Run
  `chmod -R u+rw` on the copied dir before editing.

## Installing a whole multi-skill repo — enumerate from the repo, not from screenshots

Some repos publish many skills (e.g. `heygen-com/hyperframes` shipped 15 in
May 2026, then restructured to 19 by v0.7.12 in June — the count and the shape
both drift, so always re-enumerate from the repo, never from memory). To
install all of them:

- `npx skills add <url> --skill <name>` installs ONE named skill per call; loop
  over the names to get them all. Some repos (HyperFrames) now support
  `npx skills add <org>/<repo> --all` to grab the whole set in one shot — try
  it, but if it's unavailable, drive the loop from the real list.
- **Get the real list by cloning the repo and finding SKILL.md dirs**, not from a
  `skills.sh` search page or a screenshot. Search results / site rankings surface
  phantom or aliased names that aren't real skill directories (this session a
  screenshot showed `hyperframes-compose`, `hyperframes-captions`,
  `claude-design-hyperframes` — none were actual skills; the real set was 15
  different dirs):
  ```bash
  cd /tmp && gh repo clone <org>/<repo> probe -- --depth 1
  find /tmp/probe -name SKILL.md | sed 's#/SKILL.md##; s#/tmp/probe/##' | sort
  trash /tmp/probe        # never rm
  ```
- The per-call `✗ ... → PromptScript: does not support global skill installation`
  line is **harmless** — the `✓ ~/.agents/skills/<name>` line above it confirms
  success. Don't treat it as a failure.
- For a large set (10+), leaving them in `~/.agents/skills/` (symlinked into
  Hermes) is usually fine; only copy into `~/.hermes/skills/<category>/` the ones
  you'll modify or publish. Ask the user rather than bulk-copying.

## Upgrading an already-installed multi-skill repo (it restructured its architecture)

When the user points at a launch post for a repo you *already have installed*
("upgrade my X skills") the upstream may have **restructured**, not just bumped
versions — e.g. HyperFrames went from a flat 6-skill set to a router + 9 workflow
skills + domain skills (19 total) in v0.7.12. Treat it as a re-sync, not a patch:

1. **Resolve the launch link → the real repo + release.** `bird read <tweet>` for
   the announcement, then clone the repo (`gh-as <acct> git clone --depth 1`) and
   `git log -1 --format="%ci %s"` to confirm it's a *fresh* release, not a
   downgrade. Compare `git`-cloned SKILL.md count vs your live set.
2. **Find your live copies.** They may be real dirs (not symlinks) under a
   category, e.g. `~/.hermes/skills/<category>/<name>`. `find ... -name SKILL.md`
   under the category, and check `[ -L <dir> ]` to know if you're editing a
   symlink into `~/.agents/skills/` or an independent repo copy.
3. **Check for Hermes-local customization before clobbering.** `grep -l "hermes:"`
   the live SKILL.md frontmatter. If they're vanilla upstream (no `metadata.hermes`
   block, no local tags/related_skills you added), a clean swap is safe. If
   customized, port your additions forward.
4. **Back up the old set first** (`cp -R` each into
   `~/.hermes/skills/.curator_backups/<name>-pre-<version>-<date>/`), then `trash`
   each old dir and `cp -R` the new ones in. Watch for **renames** (HyperFrames'
   `website-to-hyperframes` → `website-to-video`); the old name must be trashed
   separately so it doesn't linger as a dead duplicate.
5. **`chmod -R u+rw`** the copied dirs, then validate every new SKILL.md has
   `name:` + a `description:` line so Hermes can route them.
6. **The npm CLI version is separate from the skills.** A stale `npx <tool>
   --version` is almost always just a cached npx binary, NOT a real downgrade —
   confirm with `npm view <tool> version` (latest on registry) and tell the user
   `npx <tool>@latest` / the tool's own `init` pulls current. Don't "fix" a
   phantom CLI downgrade.

## Enriching an installed skill with new upstream knowledge (no new package)

When the user points at a launch post / repo feature that is **already part of an
installed skill's repo** (e.g. the HyperFrames `frame.md` templates live in the
same `heygen-com/hyperframes` repo, served via the registry — not a separate
package), there is nothing new to `npx skills add`. The durable value is
capturing the knowledge so the agent knows the feature exists:

1. Confirm it's already reachable (clone/grep the repo; check the installed
   skill's existing references).
2. Add a concise `references/<feature>.md` to the **owning installed skill**
   capturing the concept, the concrete list (template slugs, command names), and
   the workflow — written for task value, not a full upstream mirror.
3. Add a one-line pointer in that skill's SKILL.md at the most relevant step, with
   trigger phrases, so future sessions route to it.

Note: enriching a skill under `~/.agents/skills/` updates the symlinked Hermes
copy too. If you later promote it into the repo, carry the references along.

## Importing a vendor-shipped skill ZIP (no registry package)

Some vendors ship a downloadable Claude Code skill bundle straight off their
docs/API page (e.g. reel.farm serves `reelfarm-claude-code-skill.zip` from
`/api-docs`). There's no `npx skills add` for these — you fetch, unzip, and
integrate by hand. The bundle is typically `SKILL.md` + a few sibling reference
files (`api-reference.md`, `faq.md`).

Workflow:

1. Fetch + unzip into a temp dir, then enumerate what's actually inside (don't
   assume one file): `curl -sL -o skill.zip <url> && unzip -o skill.zip && find . -type f`.
2. **Read every file in full before trimming.** The vendor SKILL.md is usually
   too long and not in house style; the sibling refs may carry the bulk content.
3. Install under the right category: a fresh `SKILL.md` you trim to conventions
   (env-var key handling, a Safety section gating the externally-visible/destructive
   calls, your project-toolkit pattern, a core-endpoint table), plus the vendor's
   bulky files copied verbatim into `references/`.
4. In the description, **route against the sibling skill** if one exists (this
   session: reel.farm's description explicitly hands multi-platform off to
   `usefastlane-ai`) so the two don't fight to trigger.

### Pitfall — trimming SKILL.md breaks intra-bundle cross-references

Vendor reference files often link back into their SKILL.md by section
(`see the "X Prompt" section in [SKILL.md](SKILL.md)`). When you rewrite SKILL.md
into your own shape, those sections vanish and the links in the copied refs now
dangle at a file that no longer contains the target. The fix is mechanical but
easy to forget:

1. After trimming, grep the copied refs for back-links:
   `grep -rn "SKILL.md\|](.*\.md)" references/`.
2. For any link pointing at content you removed, **re-home that content into its
   own `references/<topic>.md`** (e.g. extract the vendor's prompt-grammar section
   out of their old SKILL.md into `references/prompt-grammar.md`) and repoint the
   dangling links there with `sed`.
3. Verify ALL internal references resolve before reporting done — loop over every
   `references/foo.md` mentioned in SKILL.md and every `(bar.md)` link inside the
   refs, and assert each file exists. A bundle that ships clean can still end up
   with broken links purely because you reshaped the entry file.

## Integrating into the Hermes library properly

The auto-created symlink at `~/.hermes/skills/<name>` works, but it's a
root-level entry pointing **outside** the repo. That breaks portability (if the
skills repo is ever published or moved, the symlink dangles) and bypasses the
category structure. To make it a real, version-controlled Hermes skill:

1. **Remove the root symlink:** `trash ~/.hermes/skills/<name>` (never `rm`).
2. **Copy into the right category:** `cp -R ~/.agents/skills/<name>
   ~/.hermes/skills/<category>/<name>`. Pick the category by what the skill does
   (a Lottie/animation authoring skill → `creative`; a CLI integration →
   `external-services`; etc.), matching the repo's AGENTS.md category table.
3. **Fix perms:** `chmod -R u+rw ~/.hermes/skills/<category>/<name>`.
4. **Add a References section** if you enriched it this session (prompting
   guides, worked examples, generator scripts the upstream skill lacked). Put
   them in `references/` and add a one-line pointer block near the top of the
   copied SKILL.md.
5. **Regenerate the catalog:** `cd ~/.hermes/skills && python3
   scripts/generate_catalog.py`. Confirm the skill appears in CATALOG.md.

Leave the original `~/.agents/skills/<name>` in place — other agents (Claude
Code, Codex) are symlinked to it and rely on it. Your Hermes copy is now
independent of upstream.

## Catalog generator pitfall — category DESCRIPTION.md needs frontmatter

`scripts/generate_catalog.py` calls `parse_simple_frontmatter()` on **every**
category `DESCRIPTION.md` and hard-fails with
`"<path> is missing YAML frontmatter"` if any one lacks a `---`-delimited
frontmatter block with a `description:` key. The body markdown alone is not
enough. When the generator dies on a DESCRIPTION.md:

1. Find all offenders at once:
   ```bash
   cd ~/.hermes/skills
   for f in $(find . -name DESCRIPTION.md -not -path "./.hub/*"); do
     head -1 "$f" | grep -q '^---' || echo "MISSING: $f"
   done
   ```
2. For each, prepend a frontmatter block (derive `description:` from the
   existing intro paragraph) while **keeping the body**:
   ```bash
   printf -- '---\ndescription: <one-line summary>\n---\n\n' > /tmp/h.md
   cat /tmp/h.md "$f" > /tmp/n.md && mv /tmp/n.md "$f"
   ```
3. Keep the description em-dash-free (house style); use a colon instead.
4. Re-run the generator until it prints `Generated CATALOG.md and README.md with
   N skills` and exits 0.

This is a content fix (missing metadata), not an environment failure — the same
DESCRIPTION.md files will keep breaking the generator until they carry
frontmatter.

## Fixing stale path references in skills (`~/clawd` → `~/.hermes`)

Older skills migrated from a prior runtime sometimes reference dead paths like
`~/clawd/memory/...`, `~/clawd/skills/...`, or `profile=clawd`. The correct
targets on this machine:

| Stale | Correct |
|-------|---------|
| `~/clawd/memory/<file>` | `~/.hermes/memories/<file>` |
| `~/clawd/memory/<state>.json` | `~/.hermes/cron/state/<state>.json` (cron-driven state) |
| `~/clawd/skills/<name>` | `~/.hermes/skills/<category>/<name>` (resolve the category) |
| `~/clawd/characters` | `~/.hermes/characters` |
| `~/clawd/output` | `~/.hermes/output` (incl. Python `Path.home()/"clawd"/"output"` defaults) |
| `~/clawd/assets` | `~/.hermes/assets` |
| `~/clawd/remotion-videos` | scaffold fresh at `~/projects/remotion-videos` — see "Lost git-submodule projects" below; the archive copy is EMPTY |
| `profile=clawd` / prose "clawd browser" | `profile=chrome` (6+ current skills already use `chrome`; verify the live profile name first) |

### Resolve a skill name to its real category before rewriting

`~/clawd/skills/<name>` paths must map to `<category>/<name>`, and the category
is NOT guessable from the name (e.g. `ios-simulator`->`app-store`,
`excalidraw`->`visual-design/excalidraw-mcp` — note the folder name also
differs). Build the index from the actual tree once, then drive your `sed` from
it:

```bash
cd ~/.hermes/skills
find . -name SKILL.md -not -path "./.hub/*" | while read s; do
  d=$(dirname "$s"); echo "$(basename "$d") -> ${d#./}"
done | sort
```

If a referenced name resolves to **MISSING** (no SKILL.md anywhere), do not
invent a target — leave it and flag it. This session hit `phoneagent` (gone) and
left it untouched rather than guess.

### Scripts/binaries that only survive in archive → bundle, don't dangle

`~/clawd/bin/*` and `~/clawd/scripts/*.sh` map to binaries/scripts, **not** the
`skills/` tree. Resolve each individually:

- If the script now lives in a skill's own `scripts/` dir, point the SKILL.md at
  `~/.hermes/skills/<category>/<skill>/scripts/<file>`.
- If it only survives under `~/projects/archive/clawd/scripts/`, **copy it into
  the owning skill's `scripts/` dir** so the skill is self-contained, then fix
  the reference. If that script has its own internal dead path (e.g. a hardcoded
  `$HOME/clawd/remotion-videos`), rewrite it to point at the archive location
  **behind an env override** so it's overridable later:
  `REMOTION_DIR="${BLOOM_REMOTION_DIR:-$HOME/projects/archive/clawd/remotion-videos}"`.
- Caveat to flag back to the user: anything still depending on
  `~/projects/archive/` breaks if the archive is cleaned. Note it; suggest
  migrating the underlying project to a live location.

### Lost git-submodule projects — verify, then scaffold fresh (don't chase a recovery)

A dead path pointing at a *project directory* (not a script) may be an **empty
git submodule** — a gitlink to a repo that was never cloned to this machine.
Before assuming "it only survives in archive," check whether the dir actually
has files:

```bash
du -sh ~/projects/archive/clawd/remotion-videos   # 0B == empty
git -C ~/projects/archive/clawd ls-tree HEAD remotion-videos
# 160000 commit <sha>  remotion-videos  ->  it's a submodule (gitlink), files are NOT here
```

If it's an empty submodule with no `.gitmodules` / no remote and the content
exists nowhere on disk (`grep -rl <UniqueComposition> --exclude-dir=node_modules`
returns nothing), it is **gone** — don't burn time hunting it.

For tool-backed skills (Remotion, etc.) the project was usually never the source
of truth anyway: the upstream skill scaffolds it in one command. The right fix:

1. Scaffold a fresh project at a **live** location (e.g.
   `cd ~/projects && npx create-video@latest --yes --blank --no-tailwind remotion-videos`),
   `npm install`, and run any browser/asset bootstrap the tool needs
   (`npx remotion browser ensure`).
2. **Rebuild only the composition(s) the skills actually call.** Read the
   bundled render script to get the exact composition ID + prop names it passes
   (e.g. `FeatureReveal` with `screenshotPath`/`copyText`/`featureTitle`), build
   that one `.tsx`, register it in `Root.tsx`, and **render it end-to-end via the
   real skill script** to prove the chain works — don't stop at a scaffold.
3. Repoint the skill's project path + the render script's env default at the new
   live location.
4. Make the SKILL.md **honest about state**: add a short History note that the
   original compositions are gone, preserve the old schema/scene list as a
   "rebuild spec," and list which compositions still need rebuilding. Don't leave
   the SKILL.md describing files that no longer exist.

### Don't touch intentional `clawd`/`clawdbot` mentions

After fixing, `grep -rn clawd` will still show legit hits. Exclude these from the
sweep instead of rewriting them:

- `skills-meta/skill-audit` and `skills-meta/skill-creator` *document* this
  migration rule — the `~/clawd/` strings are examples.
- **"clawdbot" is Eric's code word for THIS Hermes instance** — he uses it all
  the time. Never strip it, rewrite it, or "disambiguate" it as a different
  product. SOLE exception: `marketing/last30days`'s anti-conflation note is about
  a genuinely separate public product (a self-hosted AI agent named ClawdBot)
  explicitly NOT to be confused with Claude Code. Leave that one note as-is; treat
  every other "clawdbot" as referring to this assistant.
- An SSH key named `clawdbot` (`render-cli` refs), and the `~/clawd` entry in the
  root `CLAUDE.md` "portable paths" convention list.

Final verification one-liner (empty output = clean):

```bash
grep -rn clawd . --include="*.md" --include="*.sh" --include="*.py" \
  | grep -v "/.hub/" \
  | grep -viE "clawdbot|skill-audit|skill-creator|last30days|render-cli/references/cpe|CLAUDE.md|INSTALL.md|phoneagent|archive/clawd"
```
