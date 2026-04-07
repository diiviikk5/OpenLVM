import { NextRequest } from "next/server";

import { contextError, contextJson, requireAuthenticated, resolveApiContext, workbenchErrorStatus } from "@/lib/api-context";
import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const ctx = resolveApiContext(request);
  const unauth = requireAuthenticated(ctx, "Workspace member list");
  if (unauth) return unauth;
  try {
    const workspaceId = request.nextUrl.searchParams.get("workspace_id");
    if (!workspaceId) {
      return contextError("workspace_id is required", ctx, 400);
    }
    const data = await runWorkbenchBridge("list_workspace_members", [workspaceId, ctx.actorId]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Workspace member list failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Workspace member list failed", ctx, workbenchErrorStatus(detail), detail);
  }
}

export async function POST(request: NextRequest) {
  const ctx = resolveApiContext(request);
  const unauth = requireAuthenticated(ctx, "Workspace member save");
  if (unauth) return unauth;
  try {
    const payload = (await request.json()) as {
      workspace_id?: string;
      user_id?: string;
      role?: string;
    };
    if (!payload.workspace_id || !payload.user_id || !payload.role) {
      return contextError("workspace_id, user_id, and role are required", ctx, 400);
    }
    const data = await runWorkbenchBridge("upsert_workspace_member", [
      payload.workspace_id,
      payload.user_id,
      payload.role,
      ctx.actorId,
    ]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Workspace member save failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Workspace member save failed", ctx, workbenchErrorStatus(detail), detail);
  }
}

export async function DELETE(request: NextRequest) {
  const ctx = resolveApiContext(request);
  const unauth = requireAuthenticated(ctx, "Workspace member remove");
  if (unauth) return unauth;
  try {
    const payload = (await request.json()) as {
      workspace_id?: string;
      user_id?: string;
    };
    if (!payload.workspace_id || !payload.user_id) {
      return contextError("workspace_id and user_id are required", ctx, 400);
    }
    const data = await runWorkbenchBridge("remove_workspace_member", [
      payload.workspace_id,
      payload.user_id,
      ctx.actorId,
    ]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Workspace member remove failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Workspace member remove failed", ctx, workbenchErrorStatus(detail), detail);
  }
}
