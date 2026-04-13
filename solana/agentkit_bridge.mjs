#!/usr/bin/env node

import crypto from "node:crypto";

function parsePayload(raw) {
  try {
    return JSON.parse(raw || "{}");
  } catch {
    return {};
  }
}

function out(obj) {
  process.stdout.write(JSON.stringify(obj));
}

const command = process.argv[2] || "";
const payload = parsePayload(process.argv[3]);

if (command === "connect_agent") {
  const agentAddress = String(payload.agent_address || "").trim();
  if (!agentAddress) {
    out({ error: "agent_address is required" });
    process.exit(1);
  }
  out({
    agent_address: agentAddress,
    wallet_provider: String(payload.wallet_provider || "embedded"),
    metadata: {
      private_key_supplied: Boolean(payload.private_key),
      adapter_mode: "node-bridge",
    },
  });
  process.exit(0);
}

if (command === "simulate_x402_transfer") {
  const fromAgent = String(payload.from_agent || "").trim();
  const toAgent = String(payload.to_agent || "").trim();
  const amount = Number(payload.amount_usdc || 0);
  const txRef = `x402-${crypto
    .createHash("sha256")
    .update(`${fromAgent}:${toAgent}:${amount}`)
    .digest("hex")
    .slice(0, 16)}`;
  out({
    x402_status: "simulated_settled",
    amount_usdc: amount,
    tx_ref: txRef,
    metadata: {
      adapter_mode: "node-bridge",
      from_agent: fromAgent,
      to_agent: toAgent,
    },
  });
  process.exit(0);
}

if (command === "submit_onchain_intent") {
  const cluster = String(payload.cluster || "devnet");
  const intentCommitment = String(payload.intent_commitment || "").trim();
  if (!intentCommitment) {
    out({ error: "intent_commitment is required" });
    process.exit(1);
  }
  const signature = crypto
    .createHash("sha256")
    .update(`${cluster}:${intentCommitment}`)
    .digest("hex")
    .slice(0, 64);
  out({
    submission_status: "simulated_confirmed",
    signature,
    cluster,
    explorer_url: `https://explorer.solana.com/tx/${signature}?cluster=${cluster}`,
    metadata: {
      adapter_mode: "node-bridge",
    },
  });
  process.exit(0);
}

out({ error: `unknown command: ${command}` });
process.exit(1);
