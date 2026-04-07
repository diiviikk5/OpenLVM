import { randomUUID } from "node:crypto";

import { NextRequest, NextResponse } from "next/server";

import { contextError, contextJson, resolveApiContext, type ApiContext } from "@/lib/api-context";
import { createSessionToken } from "@/lib/session";

export const dynamic = "force-dynamic";

function buildSessionResponse(ctx: ApiContext): NextResponse {
  return contextJson(
    {
      user_id: ctx.userId,
      session_id: ctx.sessionId,
      actor_id: ctx.actorId,
      authenticated: ctx.authenticated,
    },
    ctx
  );
}

export async function GET(request: NextRequest) {
  const ctx = resolveApiContext(request);
  return buildSessionResponse(ctx);
}

export async function POST(request: NextRequest) {
  const incoming = resolveApiContext(request);
  try {
    const payload = (await request.json().catch(() => ({}))) as { user_id?: string };
    const requestedUser = (payload.user_id || "").trim();
    const userId =
      requestedUser ||
      (incoming.userId !== "anonymous" ? incoming.userId : `guest-${randomUUID().slice(0, 8)}`);
    const sessionId = randomUUID().slice(0, 12);
    const actorId = `${userId}#${sessionId}`;
    const token = createSessionToken({
      userId,
      sessionId,
      iat: Date.now(),
    });
    const ctx: ApiContext = {
      ...incoming,
      userId,
      sessionId,
      actorId,
      authenticated: true,
    };
    const response = buildSessionResponse(ctx);
    response.cookies.set("openlvm_session", token, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });
    response.cookies.set("openlvm_user_id", userId, {
      httpOnly: false,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });
    response.cookies.set("openlvm_session_id", sessionId, {
      httpOnly: false,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });
    return response;
  } catch (error) {
    return contextError("Session creation failed", incoming, 500, error instanceof Error ? error.message : undefined);
  }
}

export async function DELETE(request: NextRequest) {
  const ctx = resolveApiContext(request);
  const response = contextJson(
    { cleared: true },
    { ...ctx, userId: "anonymous", sessionId: "local-session", actorId: "anonymous#local-session", authenticated: false }
  );
  response.cookies.set("openlvm_session", "", { path: "/", maxAge: 0 });
  response.cookies.set("openlvm_user_id", "", { path: "/", maxAge: 0 });
  response.cookies.set("openlvm_session_id", "", { path: "/", maxAge: 0 });
  return response;
}

