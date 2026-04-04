$ErrorActionPreference = "Stop"

Push-Location (Join-Path $PSScriptRoot "..\core")
try {
    zig build test
}
finally {
    Pop-Location
}

Push-Location (Join-Path $PSScriptRoot "..\python")
try {
    pytest tests -q
}
finally {
    Pop-Location
}
