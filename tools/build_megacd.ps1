# Build a fresh ISO using the locally installed megacd-build Docker image.
# Usage: powershell -ExecutionPolicy Bypass -File tools/build_megacd.ps1
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Stage = Join-Path ([System.IO.Path]::GetTempPath()) ('valis3-build-' + [guid]::NewGuid().ToString('N'))
$Image = 'valis3-build-' + [guid]::NewGuid().ToString('N')
$Container = $null

try {
    # Fail before touching existing outputs if Docker is unavailable.
    $ServerVersion = & docker info --format '{{.ServerVersion}}'
    if ($LASTEXITCODE -ne 0 -or -not ($ServerVersion -match '^\d+\.\d+')) {
        throw 'Docker is unavailable; existing build artifacts were preserved.'
    }

    New-Item -ItemType Directory -Path $Stage | Out-Null
    Copy-Item -Recurse (Join-Path $Repo 'game') (Join-Path $Stage 'game')
    @'
FROM megacd-build
COPY game /work/game
WORKDIR /work/game
RUN mkdir -p build disc && make clean && make all
'@ | Set-Content -LiteralPath (Join-Path $Stage 'Dockerfile') -Encoding ascii

    & docker build --progress plain -t $Image $Stage
    if ($LASTEXITCODE -ne 0) { throw 'Mega CD build failed; existing build artifacts were preserved.' }

    $Container = (& docker create $Image | Select-Object -First 1)
    if ($LASTEXITCODE -ne 0 -or -not $Container) { throw 'Could not create the build container.' }
    $Iso = Join-Path $Stage 'valis3.iso'
    & docker cp "${Container}:/work/game/valis3.iso" $Iso
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Iso -PathType Leaf) -or (Get-Item -LiteralPath $Iso).Length -eq 0) {
        throw 'The build did not produce a valid ISO; existing build artifacts were preserved.'
    }

    $OutputDir = Join-Path $Repo 'build'
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    # Copy to the destination filesystem first, then replace only after success.
    $Pending = Join-Path $OutputDir ('valis3-' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        Copy-Item -LiteralPath $Iso -Destination $Pending
        Move-Item -LiteralPath $Pending -Destination (Join-Path $OutputDir 'valis3.iso') -Force
    } finally {
        if (Test-Path -LiteralPath $Pending) { Remove-Item -LiteralPath $Pending -Force }
    }
    Write-Host "Built $(Join-Path $OutputDir 'valis3.iso')"
} finally {
    if ($Container) { & docker rm $Container | Out-Null }
    # Only remove the uniquely named directory created by this invocation.
    if (Test-Path -LiteralPath $Stage) {
        $ResolvedStage = (Resolve-Path -LiteralPath $Stage).Path
        if ($ResolvedStage -eq $Stage) { Remove-Item -LiteralPath $ResolvedStage -Recurse -Force }
    }
}
