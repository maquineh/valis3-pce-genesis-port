# Mega CD Docker toolchain

The `megacd-build` image is based on Debian `bookworm-slim` and installs the
m68k cross compiler, binutils, Make, xorriso, `mkisofs` (from `genisoimage`)
and Megadev pinned to commit `7a7246c14b845ad2f1bd3c7d73afb04cf67d83ef`.

From the repository root, build or refresh the local image with:

```powershell
docker build --pull -f tools/megacd-build.Dockerfile -t megacd-build .
```

Then build the game ISO with:

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_megacd.ps1
```

This creates/replaces only `build/valis3.iso` after a successful build. The
script initializes the `build/` and `disc/` directories because `make clean`
removes their contents and Megadev's rules expect those directories to exist.
For an isolated validation, copy `game/` to a temporary directory and build it
with this Dockerfile:

```dockerfile
FROM megacd-build
COPY game /work/game
WORKDIR /work/game
RUN mkdir -p build disc && make clean && make all
```
