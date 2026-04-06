import { execFile } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

function getRepoRoot(): string {
  if (process.env.OPENLVM_REPO_ROOT) {
    const configured = process.env.OPENLVM_REPO_ROOT;
    const pythonRoot = path.join(configured, "python", "openlvm");
    if (!fs.existsSync(pythonRoot)) {
      throw new Error(`OpenLVM python package not found at ${pythonRoot}`);
    }
    return configured;
  }

  const cwd = process.cwd();
  const cwdRoot = path.join(cwd, "python", "openlvm");
  if (fs.existsSync(cwdRoot)) {
    return cwd;
  }

  const parent = path.join(/* turbopackIgnore: true */ cwd, "..");
  const parentRoot = path.join(parent, "python", "openlvm");
  if (fs.existsSync(parentRoot)) {
    return parent;
  }

  throw new Error(`OpenLVM python package not found near ${cwd}`);
}

export async function runWorkbenchBridge(command: string, args: string[] = []): Promise<unknown> {
  const repoRoot = getRepoRoot();
  const scriptPath = path.join(repoRoot, "website", "scripts", "workbench_api.py");
  const python = process.platform === "win32" ? "python" : "python3";

  const { stdout } = await execFileAsync(python, [scriptPath, command, ...args], {
    cwd: repoRoot,
    maxBuffer: 1024 * 1024 * 10,
    env: {
      ...process.env,
      PYTHONPATH: [path.join(repoRoot, "python"), process.env.PYTHONPATH || ""]
        .filter(Boolean)
        .join(path.delimiter),
    },
  });

  return JSON.parse(stdout);
}
