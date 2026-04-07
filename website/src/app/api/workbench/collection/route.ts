import { NextRequest } from "next/server";

import { contextError, contextJson, requireAuthenticated, resolveApiContext, workbenchErrorStatus } from "@/lib/api-context";
import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const ctx = resolveApiContext(request);
  const unauth = requireAuthenticated(ctx, "Collection create");
  if (unauth) return unauth;
  try {
    const payload = (await request.json()) as {
      workspace_id?: string;
      name?: string;
      description?: string;
    };
    if (!payload.workspace_id || !payload.name) {
      return contextError("workspace_id and name are required", ctx, 400);
    }

    const data = await runWorkbenchBridge("create_collection", [
      payload.workspace_id,
      payload.name,
      ctx.actorId,
      payload.description || "",
    ]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Collection creation failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Collection creation failed", ctx, workbenchErrorStatus(detail), detail);
  }
}

export async function PATCH(request: NextRequest) {
  const ctx = resolveApiContext(request);
  const unauth = requireAuthenticated(ctx, "Collection update");
  if (unauth) return unauth;
  try {
    const payload = (await request.json()) as {
      collection_id?: string;
      name?: string;
      description?: string;
    };
    if (!payload.collection_id) {
      return contextError("collection_id is required", ctx, 400);
    }
    const data = await runWorkbenchBridge("update_collection", [
      payload.collection_id,
      ctx.actorId,
      payload.name || "",
      payload.description || "",
    ]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Collection update failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Collection update failed", ctx, workbenchErrorStatus(detail), detail);
  }
}

export async function DELETE(request: NextRequest) {
  const ctx = resolveApiContext(request);
  const unauth = requireAuthenticated(ctx, "Collection delete");
  if (unauth) return unauth;
  try {
    const payload = (await request.json()) as { collection_id?: string };
    if (!payload.collection_id) {
      return contextError("collection_id is required", ctx, 400);
    }
    const data = await runWorkbenchBridge("delete_collection", [payload.collection_id, ctx.actorId]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Collection delete failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Collection delete failed", ctx, workbenchErrorStatus(detail), detail);
  }
}
