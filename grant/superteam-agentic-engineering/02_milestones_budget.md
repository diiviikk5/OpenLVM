# Milestones and Budget (Revised Minimal Ask)

## Budget Ask
We are **not** requesting a large grant amount.

We are requesting support equivalent to:
- **1 Codex Pro subscription** (primary tooling need)

## Milestone 1: Real Solana Submission Path
Deliverables:
- Replace submission fallback path with production AgentKit-backed submission path.
- Preserve strict real-submission enforcement for CI and production usage.
- Add submission failure taxonomy + retry policy.

## Milestone 2: On-chain Commitment + Leaderboard Indexing
Deliverables:
- Write run-result commitment artifacts to Solana-compatible records.
- Index run outcomes into a leaderboard service with reproducible links.
- Add replay-verify hooks from workbench to commitment records.

## Milestone 3: Operator-Grade Arena UX
Deliverables:
- Scenario packs for common Solana agent tasks.
- Improved run trace drilldown + compare workflows for QA teams.
- Team-ready docs/templates for hackathon and grant program users.

## Success Criteria
- Teams can run scenario -> compare -> submit intent from one operator flow.
- Strict mode passes only with real submission plumbing.
- Publicly shareable run artifacts enable transparent evaluation and ranking.
