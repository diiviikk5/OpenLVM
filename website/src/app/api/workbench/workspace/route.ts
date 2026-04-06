import { NextRequest, NextResponse } from "next/server";

import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  try {
    const payload = (await request.json()) as { name?: string; description?: string };
    if (!payload.name) {
      return NextResponse.json({ error: "name is required" }, { status: 400 });
    }
    const data = await runWorkbenchBridge("create_workspace", [payload.name, payload.description || ""]);
    if (typeof data === "object" && data && "error" in data) {
      return NextResponse.json(data, { status: 500 });
    }
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Workspace creation failed" },
      { status: 500 }
    );
  }
}
