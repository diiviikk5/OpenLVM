import { NextResponse } from "next/server";

import { runWorkbenchBridge } from "@/lib/openlvm-bridge";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await runWorkbenchBridge("overview");
    if (typeof data === "object" && data && "error" in data) {
      return NextResponse.json(data, { status: 500 });
    }
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Failed to load overview" },
      { status: 500 }
    );
  }
}
