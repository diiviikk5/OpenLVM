#!/usr/bin/env node

import crypto from "node:crypto";
import http from "node:http";
import https from "node:https";

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

function resolveMode() {
  const mode = String(process.env.OPENLVM_SOLANA_BRIDGE_MODE || "").trim().toLowerCase();
  const hasApiKey = String(process.env.OPENLVM_SOLANA_AGENTKIT_API_KEY || "").trim().length > 0;
  const hasEndpoint = String(process.env.OPENLVM_SOLANA_AGENTKIT_ENDPOINT || "").trim().length > 0;
  if (mode === "stub") {
    return "mvp-local-stub";
  }
  if (mode === "agentkit" && hasApiKey && hasEndpoint) {
    return "agentkit-session";
  }
  return "node-bridge";
}

const adapterMode = resolveMode();
const command = process.argv[2] || "";
const payload = parsePayload(process.argv[3]);
const agentkitEndpoint = String(process.env.OPENLVM_SOLANA_AGENTKIT_ENDPOINT || "").trim();
const agentkitApiKey = String(process.env.OPENLVM_SOLANA_AGENTKIT_API_KEY || "").trim();

function ensureString(value, fallback = "") {
  return typeof value === "string" ? value : fallback;
}

function ensureNumber(value, fallback = 0) {
  return Number.isFinite(Number(value)) ? Number(value) : fallback;
}

async function callAgentKitBridge(callCommand, callPayload) {
  if (!agentkitEndpoint || !agentkitApiKey) {
    return { error: "agentkit endpoint/api key is not configured" };
  }
  const timeoutMs = Math.max(
    1000,
    Number.parseInt(String(process.env.OPENLVM_SOLANA_AGENTKIT_TIMEOUT_MS || "15000"), 10) || 15000,
  );
  try {
    const body = JSON.stringify({ command: callCommand, payload: callPayload });
    const endpointUrl = new URL(agentkitEndpoint);
    const client = endpointUrl.protocol === "https:" ? https : http;
    const response = await new Promise((resolve, reject) => {
      const req = client.request(
        {
          protocol: endpointUrl.protocol,
          hostname: endpointUrl.hostname,
          port: endpointUrl.port || (endpointUrl.protocol === "https:" ? 443 : 80),
          method: "POST",
          path: `${endpointUrl.pathname}${endpointUrl.search}`,
          headers: {
            "content-type": "application/json",
            authorization: `Bearer ${agentkitApiKey}`,
            "content-length": Buffer.byteLength(body),
          },
        },
        (res) => {
          const chunks = [];
          res.on("data", (chunk) => chunks.push(chunk));
          res.on("end", () => {
            resolve({
              statusCode: res.statusCode || 0,
              statusMessage: res.statusMessage || "",
              text: Buffer.concat(chunks).toString("utf-8"),
            });
          });
        },
      );
      req.on("error", reject);
      req.on("timeout", () => req.destroy(new Error(`request timed out after ${timeoutMs}ms`)));
      req.setTimeout(timeoutMs);
      req.write(body);
      req.end();
    });
    const text = response.text;
    let data = {};
    if (text.trim()) {
      try {
        data = JSON.parse(text);
      } catch {
        return { error: `invalid JSON from agentkit endpoint (${response.statusCode})` };
      }
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      const detail =
        (typeof data === "object" && data && "error" in data ? String(data.error || "") : "") || response.statusMessage;
      return { error: `agentkit endpoint error: ${response.statusCode} ${detail}`.trim() };
    }
    if (typeof data === "object" && data && "result" in data && typeof data.result === "object") {
      return data.result;
    }
    return data;
  } catch (error) {
    const detail = error instanceof Error ? error.message : "request failed";
    return { error: `agentkit request failed: ${detail}` };
  }
}

if (command === "connect_agent") {
  const agentAddress = String(payload.agent_address || "").trim();
  if (!agentAddress) {
    out({ error: "agent_address is required" });
    process.exit(1);
  }
  if (adapterMode === "agentkit-session") {
    const remote = await callAgentKitBridge(command, payload);
    if (typeof remote === "object" && remote && !("error" in remote)) {
      const remoteMeta = typeof remote.metadata === "object" && remote.metadata ? remote.metadata : {};
      const sessionId = ensureString(remote.session_id || remoteMeta.session_id);
      if (!sessionId) {
        out({ error: "agentkit connect response missing session_id" });
        process.exit(1);
      }
      out({
        agent_address: ensureString(remote.agent_address, agentAddress),
        wallet_provider: ensureString(remote.wallet_provider, String(payload.wallet_provider || "embedded")),
        metadata: {
          ...remoteMeta,
          private_key_supplied: Boolean(payload.private_key),
          adapter_mode: "agentkit-session",
          session_id: sessionId,
          session_state: ensureString(remote.session_state || remoteMeta.session_state, "connected"),
          agentkit_endpoint: agentkitEndpoint,
        },
      });
      process.exit(0);
    }
    out(remote);
    process.exit(1);
  }
  out({
    agent_address: agentAddress,
    wallet_provider: String(payload.wallet_provider || "embedded"),
    metadata: {
      private_key_supplied: Boolean(payload.private_key),
      adapter_mode: adapterMode,
      session_id:
        adapterMode === "agentkit-session"
          ? `ak_${crypto
              .createHash("sha256")
              .update(`${agentAddress}:${Date.now()}:${Math.random()}`)
              .digest("hex")
              .slice(0, 24)}`
          : "",
      session_state: adapterMode === "agentkit-session" ? "connected" : "simulated",
      agentkit_endpoint: String(process.env.OPENLVM_SOLANA_AGENTKIT_ENDPOINT || "").trim(),
    },
  });
  process.exit(0);
}

if (command === "simulate_x402_transfer") {
  const fromAgent = String(payload.from_agent || "").trim();
  const toAgent = String(payload.to_agent || "").trim();
  const amount = Number(payload.amount_usdc || 0);
  const sessionId = String(payload.session_id || "").trim();
  if (adapterMode === "agentkit-session" && !sessionId) {
    out({ error: "agentkit session_id is required" });
    process.exit(1);
  }
  if (adapterMode === "agentkit-session") {
    const remote = await callAgentKitBridge(command, payload);
    if (typeof remote === "object" && remote && !("error" in remote)) {
      const remoteMeta = typeof remote.metadata === "object" && remote.metadata ? remote.metadata : {};
      out({
        x402_status: ensureString(remote.x402_status, "settled"),
        amount_usdc: ensureNumber(remote.amount_usdc, amount),
        tx_ref: ensureString(remote.tx_ref),
        metadata: {
          ...remoteMeta,
          adapter_mode: "agentkit-session",
          session_id: sessionId,
          from_agent: fromAgent,
          to_agent: toAgent,
          agentkit_endpoint: agentkitEndpoint,
        },
      });
      process.exit(0);
    }
    out(remote);
    process.exit(1);
  }
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
      adapter_mode: adapterMode,
      session_id: sessionId,
      from_agent: fromAgent,
      to_agent: toAgent,
    },
  });
  process.exit(0);
}

if (command === "submit_onchain_intent") {
  const cluster = String(payload.cluster || "devnet");
  const intentCommitment = String(payload.intent_commitment || "").trim();
  const sessionId = String(payload.session_id || "").trim();
  if (!intentCommitment) {
    out({ error: "intent_commitment is required" });
    process.exit(1);
  }
  if (adapterMode === "agentkit-session" && !sessionId) {
    out({ error: "agentkit session_id is required" });
    process.exit(1);
  }
  if (adapterMode === "agentkit-session") {
    const remote = await callAgentKitBridge(command, payload);
    if (typeof remote === "object" && remote && !("error" in remote)) {
      const remoteMeta = typeof remote.metadata === "object" && remote.metadata ? remote.metadata : {};
      const signature = ensureString(remote.signature);
      if (!signature) {
        out({ error: "agentkit submit response missing signature" });
        process.exit(1);
      }
      out({
        submission_status: ensureString(remote.submission_status, "confirmed"),
        signature,
        cluster: ensureString(remote.cluster, cluster),
        explorer_url: ensureString(
          remote.explorer_url,
          `https://explorer.solana.com/tx/${signature}?cluster=${cluster}`,
        ),
        metadata: {
          ...remoteMeta,
          adapter_mode: "agentkit-session",
          session_id: sessionId,
          agentkit_endpoint: agentkitEndpoint,
        },
      });
      process.exit(0);
    }
    out(remote);
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
      adapter_mode: adapterMode,
      session_id: sessionId,
    },
  });
  process.exit(0);
}

out({ error: `unknown command: ${command}` });
process.exit(1);
