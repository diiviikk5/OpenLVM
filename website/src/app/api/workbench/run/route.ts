import { NextRequest } from "next/server";

import { contextError, contextJson, resolveApiContext } from "@/lib/api-context";
import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const ctx = resolveApiContext(request);
  try {
    const payload = (await request.json()) as {
      collection_id?: string;
      scenarios?: number;
      chaos_mode?: string;
    };
    if (!payload.collection_id) {
      return contextError("collection_id is required", ctx, 400);
    }
    const args = [payload.collection_id];
    if (payload.scenarios) {
      args.push(String(payload.scenarios));
    } else {
      args.push("");
    }
    args.push(payload.chaos_mode || "");

    const data = await runWorkbenchBridge("run_collection", args);
    if (typeof data === "object" && data && "error" in data) {
      return contextError("Collection run failed", ctx, 500, String((data as { error: string }).error));
    }
    return contextJson(data, ctx);
  } catch (error) {
    return contextError("Collection run failed", ctx, 500, error instanceof Error ? error.message : undefined);
  }
}
