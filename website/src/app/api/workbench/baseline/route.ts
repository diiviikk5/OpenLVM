import { NextRequest } from "next/server";

import { contextError, contextJson, resolveApiContext } from "@/lib/api-context";
import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const ctx = resolveApiContext(request);
  try {
    const payload = (await request.json()) as {
      collection_id?: string;
      run_id?: string;
      label?: string;
    };
    if (!payload.collection_id || !payload.run_id || !payload.label) {
      return contextError("collection_id, run_id, and label are required", ctx, 400);
    }

    const data = await runWorkbenchBridge("save_baseline", [
      payload.collection_id,
      payload.run_id,
      payload.label,
      ctx.actorId,
    ]);
    if (typeof data === "object" && data && "error" in data) {
      return contextError("Baseline save failed", ctx, 500, String((data as { error: string }).error));
    }
    return contextJson(data, ctx);
  } catch (error) {
    return contextError("Baseline save failed", ctx, 500, error instanceof Error ? error.message : undefined);
  }
}
