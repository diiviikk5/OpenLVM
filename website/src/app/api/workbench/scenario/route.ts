import { NextRequest } from "next/server";

import { contextError, contextJson, requireAuthenticated, resolveApiContext, workbenchErrorStatus } from "@/lib/api-context";
import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const ctx = resolveApiContext(request);
  const unauth = requireAuthenticated(ctx, "Scenario list");
  if (unauth) return unauth;
  try {
    const collectionId = request.nextUrl.searchParams.get("collection_id");
    if (!collectionId) {
      return contextError("collection_id is required", ctx, 400);
    }
    const data = await runWorkbenchBridge("list_scenarios", [collectionId, ctx.actorId]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Scenario list failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Scenario list failed", ctx, workbenchErrorStatus(detail), detail);
  }
}

export async function POST(request: NextRequest) {
  const ctx = resolveApiContext(request);
  const unauth = requireAuthenticated(ctx, "Scenario save");
  if (unauth) return unauth;
  try {
    const payload = (await request.json()) as {
      collection_id?: string;
      name?: string;
      config_path?: string;
      input_text?: string;
    };
    if (!payload.collection_id || !payload.name || !payload.config_path || !payload.input_text) {
      return contextError("collection_id, name, config_path, and input_text are required", ctx, 400);
    }

    const data = await runWorkbenchBridge("save_scenario", [
      payload.collection_id,
      payload.name,
      payload.config_path,
      payload.input_text,
      ctx.actorId,
    ]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Scenario save failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Scenario save failed", ctx, workbenchErrorStatus(detail), detail);
  }
}

export async function PATCH(request: NextRequest) {
  const ctx = resolveApiContext(request);
  const unauth = requireAuthenticated(ctx, "Scenario update");
  if (unauth) return unauth;
  try {
    const payload = (await request.json()) as {
      scenario_id?: string;
      name?: string;
      config_path?: string;
      input_text?: string;
    };
    if (!payload.scenario_id || !payload.name || !payload.config_path || !payload.input_text) {
      return contextError("scenario_id, name, config_path, and input_text are required", ctx, 400);
    }

    const data = await runWorkbenchBridge("update_scenario", [
      payload.scenario_id,
      payload.name,
      payload.config_path,
      payload.input_text,
      ctx.actorId,
    ]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Scenario update failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Scenario update failed", ctx, workbenchErrorStatus(detail), detail);
  }
}

export async function DELETE(request: NextRequest) {
  const ctx = resolveApiContext(request);
  const unauth = requireAuthenticated(ctx, "Scenario delete");
  if (unauth) return unauth;
  try {
    const payload = (await request.json()) as { scenario_id?: string };
    if (!payload.scenario_id) {
      return contextError("scenario_id is required", ctx, 400);
    }

    const data = await runWorkbenchBridge("delete_scenario", [payload.scenario_id, ctx.actorId]);
    if (typeof data === "object" && data && "error" in data) {
      const detail = String((data as { error: string }).error);
      return contextError("Scenario delete failed", ctx, workbenchErrorStatus(detail), detail);
    }
    return contextJson(data, ctx);
  } catch (error) {
    const detail = error instanceof Error ? error.message : undefined;
    return contextError("Scenario delete failed", ctx, workbenchErrorStatus(detail), detail);
  }
}
