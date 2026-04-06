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
    ]);
    if (typeof data === "object" && data && "error" in data) {
      return contextError("Baseline compare failed", ctx, 500, String((data as { error: string }).error));
    }
    return contextJson(data, ctx);
  } catch (error) {
    return contextError("Baseline compare failed", ctx, 500, error instanceof Error ? error.message : undefined);
  }
}
