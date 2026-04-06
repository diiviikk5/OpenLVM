import { NextRequest } from "next/server";

import { contextError, contextJson, resolveApiContext } from "@/lib/api-context";
import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const ctx = resolveApiContext(request);
  try {
    const payload = (await request.json()) as { name?: string; description?: string };
    if (!payload.name) {
      return contextError("name is required", ctx, 400);
    }
    const data = await runWorkbenchBridge("create_workspace", [payload.name, payload.description || ""]);
    if (typeof data === "object" && data && "error" in data) {
      return contextError("Workspace creation failed", ctx, 500, String((data as { error: string }).error));
    }
    return contextJson(data, ctx);
  } catch (error) {
    return contextError("Workspace creation failed", ctx, 500, error instanceof Error ? error.message : undefined);
  }
}
