# Milestones and Budget (Proposed)

## Milestone 1: Real Solana Submission Path (2-3 weeks)
Deliverables:
- Replace submission fallback path with production AgentKit-backed submission path.
- Preserve strict real-submission enforcement for CI and production usage.
- Add submission failure taxonomy + retry policy.

Requested: **$4,000**

## Milestone 2: On-chain Commitment + Leaderboard Indexing (3-4 weeks)
Deliverables:
- Write run-result commitment artifacts to Solana-compatible records.
- Index run outcomes into a leaderboard service with reproducible links.
- Add replay-verify hooks from workbench to commitment records.

Requested: **$6,000**

## Milestone 3: Operator-Grade Arena UX (2-3 weeks)
Deliverables:
- Scenario packs for common Solana agent tasks.
- Improved run trace drilldown + compare workflows for QA teams.
- Team-ready docs/templates for hackathon and grant program users.

Requested: **$5,000**

## Total Requested
**$15,000**

## Success Criteria
- Teams can run scenario -> compare -> submit intent from one operator flow.
- Strict mode passes only with real submission plumbing.
- Publicly shareable run artifacts enable transparent evaluation and ranking.
