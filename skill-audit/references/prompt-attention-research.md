# Prompt-Attention Research (basis for the P dimension)

The P1-P3 items in `checklist.md` aren't style preferences; each is backed by a finding
about how models actually attend to and follow instructions in a long prompt. Cite the
relevant paper when you flag a P item, so the author sees *why* the placement/redundancy/
enforceability matters rather than treating it as taste.

## Positional attention (backs P1)

- **Lost in the Middle: How Language Models Use Long Contexts** — arXiv:2307.03172 (Liu et al., Stanford, 2023).
  On multi-document QA and key-value retrieval, accuracy is highest when the relevant
  information sits at the *start or end* of the input and degrades sharply in the middle,
  a U-shaped curve, even for models explicitly built for long context. The empirical spine
  of "put non-negotiables at the top and restate them at the end."

- **Positional Biases Shift as Inputs Approach Context Window Limits** — arXiv:2508.07479 (Veseli et al., 2025).
  Measures the effect relative to each model's window. The Lost-in-the-Middle effect is
  *strongest when input fills up to ~50% of the window*; past that, primacy weakens, recency
  stays stable, and it becomes a pure distance-to-end bias. Also: successful retrieval is a
  prerequisite for reasoning, and positional bias in reasoning is inherited from retrieval.
  Practical read: a bloated prompt doesn't just cost tokens, it pushes your early rules out
  of the high-attention zone. This is also why B2's 20KB body cap matters for *attention*,
  not only token budget.

## Redundant / conflicting instructions (backs P2)

- **A Closer Look at System Prompt Robustness** — arXiv:2502.12197 (Mu, Lu, Lavery, Wagner; Berkeley; 2025).
  Built from real GPT-Store and HuggingChat prompts. Models routinely forget guardrails and
  fail to resolve conflicting demands *within the system prompt itself*. Fine-tuning and
  inference-time interventions help but "current techniques fall short." Contradictory or
  overlapping instructions in a prompt are a real failure source, not a cosmetic nit.

- **Dynamic System Instructions and Tool Exposure for Efficient Agentic LLMs** — arXiv:2602.17046 (Franko, 2025).
  Re-ingesting long instructions plus large tool catalogs every turn raises cost, latency,
  *and derailment probability*. Their Instruction-Tool Retrieval (retrieve only the minimal
  prompt fragment + smallest tool subset per step) cuts per-step context 95%, improves tool
  routing 32% relative, cuts episode cost 70%, and enables 2-20x more loops. The case for
  pulling mutable or rarely-needed content out of the always-on prompt body.

## Enforceability / instruction hierarchy (backs P3)

- **Control Illusion: The Failure of Instruction Hierarchies in LLMs** — arXiv:2502.15851 (Geng et al., 2025).
  Across six SOTA models, system/user separation *fails* to establish a reliable hierarchy
  even on simple formatting conflicts, and models have strong inherent biases toward certain
  constraint types regardless of assigned priority. Twist: *societal* framings (authority,
  expertise, consensus) sway behavior more than the system/user role label. Implication:
  "IMPORTANT/NEVER" weighting is weaker than assumed, and unenforceable aspirational rules
  erode the whole document's authority.

- **The Instruction Hierarchy: Training LLMs to Prioritize Privileged Instructions** — arXiv:2404.13208 (Wallace et al., OpenAI, 2024).
  Attacks work because models treat system, user, and third-party text as equal priority.
  Training an explicit hierarchy (selectively ignore lower-privilege instructions) sharply
  raises robustness with minimal capability loss. Why a hard-line "never without approval"
  block belongs at the privileged top of a prompt.

## Anchor survey

- **The Prompt Report: A Systematic Survey of Prompt Engineering Techniques** — arXiv:2406.06608 (Schulhoff et al., 2024).
  58 prompting techniques, 33-term vocabulary, meta-analysis of the prefix-prompting
  literature. The single authoritative citation for "prompt engineering best practices."
