# Mega CD build: bake project into an image, run make as a build step, copy artefacts out.
# Usage: powershell -ExecutionPolicy Bypass -File tools/build_megacd.ps1 [-Log]
$ErrorActionPreference = "Stop"

$Repo = "C:\projetos\valis3-pce-genesis-port"
$Stage = "C:\projetos\tools\megacd-stage"
$Image = "valis3-build"

Write-Host "== staging project =="
if (Test-Path $Stage) { Remove-Item -Recurse -Force $Stage }
if (Test-Path "$Repo\game.built") { Remove-Item -Recurse -Force "$Repo\game.built" }
if (Test-Path "$Repo\game\build.log") { Remove-Item -Recurse -Force "$Repo\game\build.log" }
New-Item -ItemType Directory -Force -Path $Stage | Out-Null
Copy-Item -Recurse "$Repo\game" "$Stage\game"

@"
FROM megacd-build
COPY game /work/game
WORKDIR /work/game
RUN make clean > /dev/null 2>&1; make all > /tmp/build.log 2>&1 || true; cp /tmp/build.log /work/game/build.log; ls -la
"@ | Set-Content "$Stage\Dockerfile" -Encoding ascii

Write-Host "== building image (runs make inside) =="
$buildLog = docker build --progress plain -t $Image $Stage | Out-String
if ($env:BUILD_VERBOSE) { Write-Host $buildLog }
Write-Host ($buildLog -split "`n" | Select-Object -Last 6)

Write-Host "== copying artefacts back =="
$cid = docker create ${Image}
docker cp "${cid}:/work/game" "$Repo\game.built" 2>&1 | Out-Null
docker rm ${cid} | Out-Null

Write-Host "== artefacts =="
Get-ChildItem -Recurse "$Repo\game.built" -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in '.iso','.mmd','.smd','.bin','.sym' } |
    Select-Object @{n='Name';e={$_.FullName.Replace("$Repo\game.built\",'')}},Length |
    Format-Table -AutoSize | Out-String
