import { NextRequest } from "next/server";

import { contextError, contextJson, resolveApiContext } from "@/lib/api-context";
import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const ctx = resolveApiContext(request);
  try {
    const artifactId = request.nextUrl.searchParams.get("artifact_id");
    const collectionId = request.nextUrl.searchParams.get("collection_id");
    const format = request.nextUrl.searchParams.get("format") || "json";
    if (artifactId) {
      const data = await runWorkbenchBridge("download_compare_artifact", [
        artifactId,
        format,
        ctx.workspaceId || "",
        ctx.actorId,
      ]);
      if (typeof data === "object" && data && "error" in data) {
        return contextError("Artifact download failed", ctx, 500, String((data as { error: string }).error));
      }
      return contextJson(data, ctx);
    }
    if (!collectionId) {
      return contextError("collection_id is required", ctx, 400);
    }
    const data = await runWorkbenchBridge("list_compare_artifacts", [collectionId, ctx.workspaceId || "", ctx.actorId]);
    if (typeof data === "object" && data && "error" in data) {
      return contextError("Artifact list failed", ctx, 500, String((data as { error: string }).error));
    }
    return contextJson(data, ctx);
  } catch (error) {
    return contextError("Artifact request failed", ctx, 500, error instanceof Error ? error.message : undefined);
  }
}

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
    const data = await runWorkbenchBridge("save_compare_artifact", [
      payload.collection_id,
      payload.run_id,
      (payload.baseline_ids || []).join(","),
      ctx.actorId,
      ctx.workspaceId || "",
    ]);
    if (typeof data === "object" && data && "error" in data) {
      return contextError("Artifact save failed", ctx, 500, String((data as { error: string }).error));
    }
    return contextJson(data, ctx);
  } catch (error) {
    return contextError("Artifact save failed", ctx, 500, error instanceof Error ? error.message : undefined);
  }
}

export async function DELETE(request: NextRequest) {
  const ctx = resolveApiContext(request);
  try {
    const payload = (await request.json()) as {
      artifact_id?: string;
      artifact_ids?: string[];
      collection_id?: string;
      keep_latest?: number;
    };
    if (payload.artifact_id) {
      const data = await runWorkbenchBridge("delete_compare_artifact", [
        payload.artifact_id,
        ctx.actorId,
        ctx.workspaceId || "",
      ]);
      if (typeof data === "object" && data && "error" in data) {
        return contextError("Artifact delete failed", ctx, 500, String((data as { error: string }).error));
      }
      return contextJson(data, ctx);
    }
    if (Array.isArray(payload.artifact_ids) && payload.artifact_ids.length > 0) {
      const data = await runWorkbenchBridge("delete_compare_artifacts_bulk", [
        payload.artifact_ids.join(","),
        ctx.actorId,
        ctx.workspaceId || "",
      ]);
      if (typeof data === "object" && data && "error" in data) {
        return contextError("Artifact bulk delete failed", ctx, 500, String((data as { error: string }).error));
      }
      return contextJson(data, ctx);
    }
    if (payload.collection_id && typeof payload.keep_latest === "number") {
      const data = await runWorkbenchBridge("prune_compare_artifacts", [
        payload.collection_id,
        String(payload.keep_latest),
        ctx.actorId,
        ctx.workspaceId || "",
      ]);
      if (typeof data === "object" && data && "error" in data) {
        return contextError("Artifact prune failed", ctx, 500, String((data as { error: string }).error));
      }
      return contextJson(data, ctx);
    }
    return contextError("artifact_id or collection_id+keep_latest is required", ctx, 400);
  } catch (error) {
    return contextError("Artifact delete/prune failed", ctx, 500, error instanceof Error ? error.message : undefined);
  }
}
