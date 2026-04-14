# Superteam Agentic Engineering Grant Application

## Project
**OpenLVM: Solana Agent Arena**

OpenLVM is a Postman-style testing and benchmarking platform for AI agents, with a Zig runtime core, Python orchestration layer, and a web workbench.  
Our Solana direction is to make this the default battleground for Solana-native agents (AgentKit, elizaOS-style agents, skill-based agents), where runs are reproducible and submission artifacts are verifiable.

## Problem
Agent teams currently lack:
- A dedicated Solana-native workflow to run repeatable agent evaluation scenarios.
- A clean way to compare runs against baselines and detect regressions.
- A standardized artifact for submitting/payment/scoring events that can be bridged to on-chain verification.

## Solution
OpenLVM provides:
- Scenario collections/workspaces and saved test flows.
- Deterministic run traces and baseline comparison.
- Solana Arena run flow with:
  - x402-style payment simulation metadata
  - deterministic trace commitments
  - deterministic `onchain_intent` payloads (PDA-seed-ready)
  - intent submission flow with cluster targeting and strict real-submission mode

## Why this fits Agentic Engineering
This is core developer tooling for agent builders:
- Speeds iteration and debugging loops.
- Reduces test ambiguity with deterministic replay/compare artifacts.
- Creates a pathway from local testing to verifiable Solana submission flows.

## Existing progress (already built)
- CLI:
  - `arena-run`, `arena-intent`, `arena-submit`, `arena-runs`, `arena-integrations`
  - one-step run+submit mode
  - strict real-submission enforcement mode
  - explicit cluster targeting (`devnet|testnet|mainnet-beta`)
- Workbench UI/API:
  - arena run list/create
  - intent export + submit
  - readiness endpoint and operator visibility
  - submission metadata and explorer links
- Storage/testing:
  - arena run persistence and metadata lifecycle
  - test coverage for bridge flow, CLI flow, and submission behavior

## solana.new usage
We are using `solana.new` as the recommended Solana CLI setup path:
`curl -fsSL https://www.solana.new/setup.sh | bash`

## What grant support unlocks
Our ask is intentionally small: funding equivalent to a **Codex Pro subscription** so we can sustain rapid implementation velocity.

This directly supports:
- production-grade Solana submission path (non-stub, strict mode default for production)
- on-chain commitment recording and leaderboard indexing
- scenario libraries and QA-grade run inspection UX for teams/hackathons

## Team execution style
We ship incrementally with small validated commits, with Python tests + web build checks for each slice, and we keep a developer-first product scope aligned to real agent teams.
