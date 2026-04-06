import { randomUUID } from "node:crypto";

import { NextRequest, NextResponse } from "next/server";

export type ApiContext = {
  requestId: string;
  userId: string;
  workspaceId: string | null;
  authenticated: boolean;
};

export function resolveApiContext(request: NextRequest): ApiContext {
  const headerUserId = request.headers.get("x-openlvm-user-id");
  const cookieUserId = request.cookies.get("openlvm_user_id")?.value;
  const userId = (headerUserId || cookieUserId || "anonymous").trim();
  const workspaceId = request.headers.get("x-openlvm-workspace-id");
  return {
    requestId: request.headers.get("x-request-id") || randomUUID(),
    userId,
    workspaceId,
    authenticated: userId !== "anonymous",
  };
}

export function contextJson(data: unknown, ctx: ApiContext, status = 200): NextResponse {
  const response = NextResponse.json(data, { status });
  response.headers.set("x-openlvm-request-id", ctx.requestId);
  response.headers.set("x-openlvm-user-id", ctx.userId);
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
      detail,
    },
    ctx,
    status
  );
}
