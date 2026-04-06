$ErrorActionPreference = "Stop"
$root = Join-Path $PSScriptRoot ".."
$localZig = Join-Path $root "tools\zig-0.15.2\zig.exe"
$zig = if (Test-Path $localZig) { $localZig } else { "zig" }

Push-Location (Join-Path $root "core")
try {
    & $zig build
}
finally {
    Pop-Location
}

Push-Location (Join-Path $root "python")
try {
    python -m pip install -e ".[dev,mcp,eval,tracing]"
}
finally {
    Pop-Location
}
