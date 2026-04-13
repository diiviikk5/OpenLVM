import { NextRequest } from "next/server";

import { contextError, contextJson, requireAuthenticated, resolveApiContext, workbenchErrorStatus } from "@/lib/api-context";
import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const ctx = resolveApiContext(request);
  const unauth = requireAuthenticated(ctx, "Arena run list");
  if (unauth) return unauth;
  try {
    const limit = request.nextUrl.searchParams.get("limit") || "50";
    const data = await runWorkbenchBridge("arena_runs", [ctx.actorId, limit]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Arena run list failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Arena run list failed", ctx, workbenchErrorStatus(detail), detail);
  }
}

export async function POST(request: NextRequest) {
  const ctx = resolveApiContext(request);
  const unauth = requireAuthenticated(ctx, "Arena run create");
  if (unauth) return unauth;
  try {
    const payload = (await request.json()) as {
      agent_address?: string;
      scenario_path?: string;
      wallet_provider?: string;
      private_key?: string;
      submit_intent?: boolean;
      require_real_submission?: boolean;
    };
    if (!payload.agent_address || !payload.scenario_path) {
      return contextError("agent_address and scenario_path are required", ctx, 400);
    }
    const data = await runWorkbenchBridge("arena_run", [
      payload.agent_address,
      payload.scenario_path,
      ctx.actorId,
      payload.wallet_provider || "embedded",
      payload.private_key || "",
      payload.submit_intent ? "1" : "0",
      payload.require_real_submission ? "1" : "0",
    ]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Arena run create failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Arena run create failed", ctx, workbenchErrorStatus(detail), detail);
  }
}
