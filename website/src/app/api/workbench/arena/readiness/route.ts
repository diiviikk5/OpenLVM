import { NextRequest } from "next/server";

import { contextError, contextJson, requireAuthenticated, resolveApiContext, workbenchErrorStatus } from "@/lib/api-context";
import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const ctx = resolveApiContext(request);
  const unauth = requireAuthenticated(ctx, "Arena readiness");
  if (unauth) return unauth;
  try {
    const data = await runWorkbenchBridge("arena_readiness", [ctx.actorId]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Arena readiness failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Arena readiness failed", ctx, workbenchErrorStatus(detail), detail);
  }
}
