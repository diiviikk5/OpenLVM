import { NextRequest } from "next/server";

import { contextError, contextJson, resolveApiContext, workbenchErrorStatus } from "@/lib/api-context";
import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const ctx = resolveApiContext(request);
  try {
    const payload = (await request.json()) as { name?: string; description?: string };
    if (!payload.name) {
      return contextError("name is required", ctx, 400);
    }
    const data = await runWorkbenchBridge("create_workspace", [payload.name, ctx.actorId, payload.description || ""]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Workspace creation failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Workspace creation failed", ctx, workbenchErrorStatus(detail), detail);
  }
}

export async function PATCH(request: NextRequest) {
  const ctx = resolveApiContext(request);
  try {
    const payload = (await request.json()) as {
      workspace_id?: string;
      name?: string;
      description?: string;
    };
    if (!payload.workspace_id) {
      return contextError("workspace_id is required", ctx, 400);
    }
    const data = await runWorkbenchBridge("update_workspace", [
      payload.workspace_id,
      ctx.actorId,
      payload.name || "",
      payload.description || "",
    ]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Workspace update failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Workspace update failed", ctx, workbenchErrorStatus(detail), detail);
  }
}

export async function DELETE(request: NextRequest) {
  const ctx = resolveApiContext(request);
  try {
    const payload = (await request.json()) as { workspace_id?: string };
    if (!payload.workspace_id) {
      return contextError("workspace_id is required", ctx, 400);
    }
    const data = await runWorkbenchBridge("delete_workspace", [payload.workspace_id, ctx.actorId]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Workspace delete failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Workspace delete failed", ctx, workbenchErrorStatus(detail), detail);
  }
}
