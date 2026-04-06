import { NextRequest, NextResponse } from "next/server";

import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  try {
    const payload = (await request.json()) as {
      collection_id?: string;
      name?: string;
      config_path?: string;
      input_text?: string;
    };
    if (!payload.collection_id || !payload.name || !payload.config_path || !payload.input_text) {
      return NextResponse.json(
        { error: "collection_id, name, config_path, and input_text are required" },
        { status: 400 }
      );
    }

    const data = await runWorkbenchBridge("save_scenario", [
      payload.collection_id,
      payload.name,
      payload.config_path,
      payload.input_text,
    ]);
    if (typeof data === "object" && data && "error" in data) {
      return NextResponse.json(data, { status: 500 });
    }
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Scenario save failed" },
      { status: 500 }
    );
  }
}
