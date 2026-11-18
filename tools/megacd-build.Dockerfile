FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      binutils-m68k-linux-gnu \
      ca-certificates \
      gcc-m68k-linux-gnu \
      git \
      genisoimage \
      make \
      xorriso \
 && rm -rf /var/lib/apt/lists/*

ARG MEGADEV_COMMIT=7a7246c14b845ad2f1bd3c7d73afb04cf67d83ef
RUN git clone https://github.com/drojaazu/megadev.git /opt/megadev \
 && git -C /opt/megadev checkout --detach "${MEGADEV_COMMIT}" \
 && test "$(git -C /opt/megadev rev-parse HEAD)" = "${MEGADEV_COMMIT}"

ENV MEGADEV_PATH=/opt/megadev
WORKDIR /work
