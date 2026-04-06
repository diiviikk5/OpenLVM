$ErrorActionPreference = "Stop"
$root = Join-Path $PSScriptRoot ".."
$localZig = Join-Path $root "tools\zig-0.15.2\zig.exe"
$zig = if (Test-Path $localZig) { $localZig } else { "zig" }

Push-Location (Join-Path $root "core")
try {
    & $zig build test
}
finally {
    Pop-Location
}

Push-Location (Join-Path $root "python")
try {
    python -m pytest tests -q
}
finally {
    Pop-Location
}
