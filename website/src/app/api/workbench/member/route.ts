import { NextRequest } from "next/server";

import { contextError, contextJson, resolveApiContext } from "@/lib/api-context";
import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const ctx = resolveApiContext(request);
  try {
    const workspaceId = request.nextUrl.searchParams.get("workspace_id");
    if (!workspaceId) {
      return contextError("workspace_id is required", ctx, 400);
    }
    const data = await runWorkbenchBridge("list_workspace_members", [workspaceId, ctx.actorId]);
    if (typeof data === "object" && data && "error" in data) {
      return contextError("Workspace member list failed", ctx, 500, String((data as { error: string }).error));
    }
    return contextJson(data, ctx);
  } catch (error) {
    return contextError("Workspace member list failed", ctx, 500, error instanceof Error ? error.message : undefined);
  }
}

export async function POST(request: NextRequest) {
  const ctx = resolveApiContext(request);
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
      return contextError("Workspace member save failed", ctx, 500, String((data as { error: string }).error));
    }
    return contextJson(data, ctx);
  } catch (error) {
    return contextError("Workspace member save failed", ctx, 500, error instanceof Error ? error.message : undefined);
  }
}

export async function DELETE(request: NextRequest) {
  const ctx = resolveApiContext(request);
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
      return contextError("Workspace member remove failed", ctx, 500, String((data as { error: string }).error));
    }
    return contextJson(data, ctx);
  } catch (error) {
    return contextError("Workspace member remove failed", ctx, 500, error instanceof Error ? error.message : undefined);
  }
}
