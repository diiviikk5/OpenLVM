import { randomUUID } from "node:crypto";

import { NextRequest, NextResponse } from "next/server";
import { parseSessionToken } from "@/lib/session";

export type ApiContext = {
  requestId: string;
  userId: string;
  sessionId: string;
  actorId: string;
  workspaceId: string | null;
  authenticated: boolean;
};

export function resolveApiContext(request: NextRequest): ApiContext {
  const sessionToken = request.cookies.get("openlvm_session")?.value;
  const parsedSession = parseSessionToken(sessionToken);
  const headerUserId = request.headers.get("x-openlvm-user-id");
  const cookieUserId = request.cookies.get("openlvm_user_id")?.value;
  const headerSessionId = request.headers.get("x-openlvm-session-id");
  const cookieSessionId = request.cookies.get("openlvm_session_id")?.value;
  const userId = (
    parsedSession?.userId ||
    headerUserId ||
    cookieUserId ||
    "anonymous"
  ).trim();
  const sessionId = (
    parsedSession?.sessionId ||
    headerSessionId ||
    cookieSessionId ||
    "local-session"
  ).trim();
  const workspaceId = request.headers.get("x-openlvm-workspace-id");
  const actorId = `${userId}#${sessionId}`;
  return {
    requestId: request.headers.get("x-request-id") || randomUUID(),
    userId,
    sessionId,
    actorId,
    workspaceId,
    authenticated: userId !== "anonymous",
  };
}

export function contextJson(data: unknown, ctx: ApiContext, status = 200): NextResponse {
  const response = NextResponse.json(data, { status });
  response.headers.set("x-openlvm-request-id", ctx.requestId);
  response.headers.set("x-openlvm-user-id", ctx.userId);
  response.headers.set("x-openlvm-session-id", ctx.sessionId);
  response.headers.set("x-openlvm-actor-id", ctx.actorId);
  response.headers.set("x-openlvm-authenticated", String(ctx.authenticated));
  if (ctx.workspaceId) {
    response.headers.set("x-openlvm-workspace-id", ctx.workspaceId);
  }
  return response;
}

export function contextError(
  message: string,
  ctx: ApiContext,
  status = 500,
  detail?: string
): NextResponse {
  return contextJson(
    {
      error: message,
      request_id: ctx.requestId,
      user_id: ctx.userId,
      session_id: ctx.sessionId,
      actor_id: ctx.actorId,
      detail,
    },
    ctx,
    status
  );
}
