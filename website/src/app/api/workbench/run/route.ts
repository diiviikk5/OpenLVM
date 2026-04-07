import { NextRequest } from "next/server";

import { contextError, contextJson, resolveApiContext, workbenchErrorStatus } from "@/lib/api-context";
import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const ctx = resolveApiContext(request);
  try {
    const runId = request.nextUrl.searchParams.get("run_id") || "latest";
    const data = await runWorkbenchBridge("run_details", [runId]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Run inspection failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Run inspection failed", ctx, workbenchErrorStatus(detail), detail);
  }
}

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
    args.push(ctx.workspaceId || "");
    args.push(ctx.actorId);

    const data = await runWorkbenchBridge("run_collection", args);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Collection run failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Collection run failed", ctx, workbenchErrorStatus(detail), detail);
  }
}
