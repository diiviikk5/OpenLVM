import { NextRequest } from "next/server";

import { contextError, contextJson, requireAuthenticated, resolveApiContext, workbenchErrorStatus } from "@/lib/api-context";
import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const ctx = resolveApiContext(request);
  const unauth = requireAuthenticated(ctx, "Baseline compare");
  if (unauth) return unauth;
  try {
    const payload = (await request.json()) as {
      collection_id?: string;
      run_id?: string;
      baseline_ids?: string[];
    };
    if (!payload.collection_id || !payload.run_id) {
      return contextError("collection_id and run_id are required", ctx, 400);
    }

    const baselineIds = payload.baseline_ids ?? [];
    const data = await runWorkbenchBridge("compare_baseline", [
      payload.collection_id,
      payload.run_id,
      baselineIds.join(","),
      ctx.workspaceId || "",
      ctx.actorId,
    ]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Baseline compare failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Baseline compare failed", ctx, workbenchErrorStatus(detail), detail);
  }
}
