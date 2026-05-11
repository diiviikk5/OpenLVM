import { NextRequest } from "next/server";

import { contextError, contextJson, requireAuthenticated, resolveApiContext, workbenchErrorStatus } from "@/lib/api-context";
import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const ctx = resolveApiContext(request);
  const unauth = requireAuthenticated(ctx, "Arena release readiness");
  if (unauth) return unauth;
  try {
    const ping = request.nextUrl.searchParams.get("ping") ?? "1";
    const timeoutMs = request.nextUrl.searchParams.get("timeout_ms") ?? "5000";
    const failOnPingWarning = request.nextUrl.searchParams.get("fail_on_ping_warning") ?? "1";
    const minReadinessScore = request.nextUrl.searchParams.get("min_readiness_score") ?? "80";
    const minIntegrationReadyPercent = request.nextUrl.searchParams.get("min_integration_ready_percent") ?? "70";
    const data = await runWorkbenchBridge("arena_release_readiness", [
      ctx.actorId,
      ping,
      timeoutMs,
      failOnPingWarning,
      minReadinessScore,
      minIntegrationReadyPercent,
    ]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Arena release readiness failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Arena release readiness failed", ctx, workbenchErrorStatus(detail), detail);
  }
}
