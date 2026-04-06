import { NextRequest, NextResponse } from "next/server";

import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  try {
    const payload = (await request.json()) as {
      collection_id?: string;
      run_id?: string;
      label?: string;
    };
    if (!payload.collection_id || !payload.run_id || !payload.label) {
      return NextResponse.json({ error: "collection_id, run_id, and label are required" }, { status: 400 });
    }

    const data = await runWorkbenchBridge("save_baseline", [
      payload.collection_id,
      payload.run_id,
      payload.label,
    ]);
    if (typeof data === "object" && data && "error" in data) {
      return NextResponse.json(data, { status: 500 });
    }
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Baseline save failed" },
      { status: 500 }
    );
  }
}
