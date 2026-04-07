import { createHmac, timingSafeEqual } from "node:crypto";

type SessionPayload = {
  userId: string;
  sessionId: string;
  iat: number;
};

const DEFAULT_SECRET = "openlvm-dev-secret";

function sessionSecret(): string {
  return process.env.OPENLVM_SESSION_SECRET || DEFAULT_SECRET;
}

function toBase64Url(input: string): string {
  return Buffer.from(input, "utf-8").toString("base64url");
}

function fromBase64Url(input: string): string {
  return Buffer.from(input, "base64url").toString("utf-8");
}

function signPayload(payloadB64: string): string {
  return createHmac("sha256", sessionSecret()).update(payloadB64).digest("base64url");
}

export function createSessionToken(payload: SessionPayload): string {
  const payloadB64 = toBase64Url(JSON.stringify(payload));
  const signature = signPayload(payloadB64);
  return `${payloadB64}.${signature}`;
}

export function parseSessionToken(token: string | undefined): SessionPayload | null {
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length !== 2) return null;
  const [payloadB64, providedSig] = parts;
  const expectedSig = signPayload(payloadB64);
  const provided = Buffer.from(providedSig, "utf-8");
  const expected = Buffer.from(expectedSig, "utf-8");
  if (provided.length !== expected.length) return null;
  if (!timingSafeEqual(provided, expected)) return null;
  try {
    const payload = JSON.parse(fromBase64Url(payloadB64)) as SessionPayload;
    if (!payload.userId || !payload.sessionId) return null;
    return payload;
  } catch {
    return null;
  }
}

