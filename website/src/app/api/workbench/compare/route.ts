import { NextRequest, NextResponse } from "next/server";

import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  try {
    const payload = (await request.json()) as {
      collection_id?: string;
      run_id?: string;
    };
    if (!payload.collection_id || !payload.run_id) {
      return NextResponse.json({ error: "collection_id and run_id are required" }, { status: 400 });
    }

    const data = await runWorkbenchBridge("compare_baseline", [payload.collection_id, payload.run_id]);
    if (typeof data === "object" && data && "error" in data) {
      return NextResponse.json(data, { status: 500 });
    }
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Baseline compare failed" },
      { status: 500 }
    );
  }
}
