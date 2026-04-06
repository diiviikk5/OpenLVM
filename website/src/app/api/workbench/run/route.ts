import { NextRequest, NextResponse } from "next/server";

import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  try {
    const payload = (await request.json()) as {
      collection_id?: string;
      scenarios?: number;
      chaos_mode?: string;
    };
    if (!payload.collection_id) {
      return NextResponse.json({ error: "collection_id is required" }, { status: 400 });
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
      return NextResponse.json(data, { status: 500 });
    }
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Collection run failed" },
      { status: 500 }
    );
  }
}
