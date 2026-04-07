import { NextRequest } from "next/server";

import { contextError, contextJson, resolveApiContext } from "@/lib/api-context";
import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const ctx = resolveApiContext(request);
  try {
    const data = await runWorkbenchBridge("overview", [ctx.workspaceId || "", ctx.actorId]);
    if (typeof data === "object" && data && "error" in data) {
      return contextError("Failed to load overview", ctx, 500, String((data as { error: string }).error));
    }
    return contextJson(data, ctx);
  } catch (error) {
    return contextError("Failed to load overview", ctx, 500, error instanceof Error ? error.message : undefined);
  }
}
