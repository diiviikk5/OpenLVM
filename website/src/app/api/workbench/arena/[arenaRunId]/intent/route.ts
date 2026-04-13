import { NextRequest } from "next/server";

import { contextError, contextJson, requireAuthenticated, resolveApiContext, workbenchErrorStatus } from "@/lib/api-context";
import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ arenaRunId: string }> }
) {
  const ctx = resolveApiContext(request);
  const unauth = requireAuthenticated(ctx, "Arena intent fetch");
  if (unauth) return unauth;
  try {
    const { arenaRunId } = await params;
    const data = await runWorkbenchBridge("arena_intent", [arenaRunId, ctx.actorId]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Arena intent fetch failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Arena intent fetch failed", ctx, workbenchErrorStatus(detail), detail);
  }
}
