# Build on Windows without Docker or WSL. Dependencies are installed separately:
# SGDK's Windows compiler and shell, Megadev, Git for Windows, and xorriso.
param(
    [string]$Megadev = (Join-Path $env:TEMP 'valis-megadev'),
    [string]$Sgdk = (Join-Path $env:TEMP 'valis-sgdk'),
    [string]$Xorriso = (Join-Path $env:TEMP 'valis-xorriso\xorriso.exe')
)
$ErrorActionPreference = 'Stop'
$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Megadev = (Resolve-Path -LiteralPath $Megadev).Path
$Sgdk = (Resolve-Path -LiteralPath $Sgdk).Path
$Xorriso = (Resolve-Path -LiteralPath $Xorriso).Path
$GitCommand = (Get-Command git.exe -ErrorAction Stop).Source
$GitRoot = Split-Path (Split-Path $GitCommand -Parent) -Parent
$GitTools = Join-Path $GitRoot 'usr\bin'
foreach ($required in @((Join-Path $Megadev 'megadev.make'),
                         (Join-Path $Sgdk 'bin\sh.exe'),
                         (Join-Path $Sgdk 'bin\gcc.exe'),
                         (Join-Path $GitTools 'find.exe'), $Xorriso)) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing build dependency: $required" }
}
# Megadev's make rules do not quote its include paths.
if ($Megadev -match '\s') { throw 'Megadev path cannot contain spaces.' }

function Convert-ToMsysPath([string]$Path) {
    $match = [regex]::Match($Path, '^([A-Za-z]):[\\/](.*)$')
    if (-not $match.Success) { throw "Expected a local drive path: $Path" }
    return '/' + $match.Groups[1].Value.ToLowerInvariant() + '/' + $match.Groups[2].Value.Replace('\', '/')
}

$Stage = Join-Path ([System.IO.Path]::GetTempPath()) ('valis-native-' + [guid]::NewGuid().ToString('N'))
$OldPath = $env:PATH
$OldMegadev = $env:MEGADEV_PATH
$OldBuildDir = $env:VALIS_BUILD_DIR
try {
    New-Item -ItemType Directory -Path $Stage | Out-Null
    $Work = Join-Path $Stage 'game'
    Copy-Item -LiteralPath (Join-Path $Repo 'game') -Destination $Work -Recurse
    New-Item -ItemType Directory -Force -Path (Join-Path $Work 'build'), (Join-Path $Work 'disc') | Out-Null
    $env:PATH = (Join-Path $Sgdk 'bin') + ';' + $GitTools + ';' + $OldPath
    $env:MEGADEV_PATH = Convert-ToMsysPath $Megadev
    $env:VALIS_BUILD_DIR = Convert-ToMsysPath $Work
    @'
cd "$VALIS_BUILD_DIR" || exit 1
exec make M68K_PREFIX= disc/ipx.mmd disc/game.mmd disc/stage1.mmd disc/stage2.mmd disc/stage2b.mmd disc/stage3a.mmd disc/stage2c.mmd disc/stage2cg.mmd disc/stage2cb.mmd disc/stage4a.mmd disc/stage1a.mmd disc/stage4ax.mmd disc/stage2a2.mmd disc/spx.smd build/boot.bin > build.log 2>&1
'@ | Set-Content -LiteralPath (Join-Path $Stage 'build.sh') -Encoding ascii
    & (Join-Path $Sgdk 'bin\sh.exe') (Join-Path $Stage 'build.sh')
    Get-Content -LiteralPath (Join-Path $Work 'build.log')
    if ($LASTEXITCODE -ne 0) { throw 'Compilation failed; existing ISO was preserved.' }

    Push-Location $Work
    try {
        & $Xorriso -as mkisofs -quiet -iso-level 1 -G build/boot.bin -pad -V valis3 -sysid MEGA_CD -o valis3.iso disc
        if ($LASTEXITCODE -ne 0) { throw 'ISO creation failed; existing ISO was preserved.' }
    } finally { Pop-Location }
    $Iso = Join-Path $Work 'valis3.iso'
    $Bytes = [System.IO.File]::ReadAllBytes($Iso)
    if ($Bytes.Length -lt 34816 -or [System.Text.Encoding]::ASCII.GetString($Bytes, 0, 16) -ne 'SEGADISCSYSTEM  ' -or
        [System.Text.Encoding]::ASCII.GetString($Bytes, 32769, 5) -ne 'CD001') {
        throw 'The generated ISO is missing its Mega CD boot block or ISO9660 descriptor.'
    }
    $OutputDir = Join-Path $Repo 'build'
    New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
    $Artifacts = Join-Path (Join-Path $OutputDir 'native-artifacts') ([guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $Artifacts | Out-Null
    Copy-Item -LiteralPath (Join-Path $Work 'build'), (Join-Path $Work 'disc'), (Join-Path $Work 'build.log') -Destination $Artifacts -Recurse
    $Pending = Join-Path $OutputDir ('valis3-' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        Copy-Item -LiteralPath $Iso -Destination $Pending
        Move-Item -LiteralPath $Pending -Destination (Join-Path $OutputDir 'valis3.iso') -Force
    } finally {
        if (Test-Path -LiteralPath $Pending) { Remove-Item -LiteralPath $Pending -Force }
    }
    Write-Host "Built $(Join-Path $OutputDir 'valis3.iso')"
    Write-Host "Symbols and build log: $Artifacts"
} finally {
    $env:PATH = $OldPath
    $env:MEGADEV_PATH = $OldMegadev
    $env:VALIS_BUILD_DIR = $OldBuildDir
    if (Test-Path -LiteralPath $Stage) {
        $ResolvedStage = (Resolve-Path -LiteralPath $Stage).Path
        if ($ResolvedStage -eq $Stage) { Remove-Item -LiteralPath $ResolvedStage -Recurse -Force }
    }
}
