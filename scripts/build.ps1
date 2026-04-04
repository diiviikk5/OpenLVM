$ErrorActionPreference = "Stop"

Push-Location (Join-Path $PSScriptRoot "..\core")
try {
    zig build
}
finally {
    Pop-Location
}

Push-Location (Join-Path $PSScriptRoot "..\python")
try {
    python -m pip install -e ".[dev,mcp,eval,tracing]"
}
finally {
    Pop-Location
}
