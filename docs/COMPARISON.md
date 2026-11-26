# Harness4 and Claude Ship

**Our extension of the PR workflow: own the engine, choose the model, and control
how review guidance learns.** Harness4 implements three concrete capabilities
central to this direction:

1. **An open, self-hosted engine.** Inspect, modify and redistribute the coordinator
   under MIT. Keep its state and policies on infrastructure you operate.
2. **A replaceable model endpoint.** Select a compatible hosted or local deployment.
   Model behavior still needs qualification; endpoint choice is not a quality guarantee.
3. **A governed learning lifecycle.** Propose checklist changes from verified feedback,
   evaluate on fresh target and regression data, explicitly approve a version, and
   roll it back or revoke its evidence dependencies.

The comparison below separates shipped Harness4 capabilities from what Anthropic
publicly documents. Checked **2026-11-26** against its
[announcement][ship-announcement], [product page][ship-product] and
[documentation][ship-docs]. “Not described” means absent from those reviewed pages,
not proof that Anthropic lacks an internal capability.

| Dimension | Claude Ship — official description | Harness4 — current alpha |
|---|---|---|
| PR lifecycle | Code Review, PR Steward and Claude Approvals coordinate reviews, fixes and policy decisions. [Source][ship-docs] | Two review passes, bounded text repairs, fresh CI checks and separate-account approval. |
| Ownership and deployment | Claude organization setup; the reviewed pages do not describe a self-hostable MIT engine. [Source][ship-docs] | MIT source; run and modify the coordinator yourself. Model requests go to your chosen endpoint. |
| Model choice | Claude-based workflow; interchangeable model endpoints are not offered in the reviewed pages. [Source][ship-product] | Explicit Chat Completions-compatible endpoint, with a pinned profile for learning. |
| Improving review guidance | `REVIEW.md` customization; the reviewed pages do not describe a held-out learning/promotion/rollback lifecycle. [Source][ship-product] | Verified labels, dev-only proposals, one-use release cohorts, approval, rollback and evidence retraction. |
| CI failures, conflicts and feedback | Steward handles failing checks, merge conflicts and feedback from humans and review tools. [Source][ship-announcement] | Repairs findings from its own review; CI failures, conflicts and external review feedback need human handling today. |
| Adoption and cost | Team/Enterprise service with token billing; `/ship` is also available in Claude Code. [Source][ship-announcement] | Install the repository and configure tokens/policy yourself. MIT code; infrastructure and model usage can cost money. |

**Choose Harness4 when open ownership, endpoint choice and inspectable learning
controls matter enough to operate an early-stage tool.** Claude Ship currently
documents broader PR stewardship and integrated onboarding. We have not run a
cost-matched head-to-head benchmark, so we claim neither better accuracy nor lower
cost. Our “upgrade” is the implemented architecture and control surface; proving
better engineering outcomes is the next step.

[ship-announcement]: https://claude.com/resources/articles/introducing-claude-ship
[ship-product]: https://claude.com/product/claude-ship
[ship-docs]: https://code.claude.com/docs/en/claude-ship


[Back to the README](../README.md#harness4-and-claude-ship).
