################################################################################
# VALIS III - PC Engine CD -> Sega Mega CD port
# Builds with megadev (Sega Mega CD devkit) inside the megacd-build toolchain.
################################################################################

## Project ID (max 11 chars, ASCII only)
PROJECT_ID:=valis3

## Build target: MEGACD (bootable Mega CD disc image)
TARGET:=MEGACD

PROJECT_NAME:="VALIS III MEGA CD"
HEADER_SOFTWARE_ID="VALIS III MDCD"
HEADER_DISC_ID:="SEGADISCSYSTEM"

## Region: US security code (NTSC, 60Hz - matches the NTSC-J source)
REGION?=US
VIDEO?=NTSC

## Paths (relative to this makefile)
SRC_PATH:=src
RES_PATH:=res
BUILD_PATH:=build
DISC_PATH:=disc

## Optimisation flags for the 68000
CC_FLAGS?=-O2 -fomit-frame-pointer -ffunction-sections -fdata-sections
AS_FLAGS?=
LD_FLAGS?=

## megadev location (inside the toolchain container)
MEGADEV_PATH?=/opt/megadev

include $(MEGADEV_PATH)/megadev.make

all: \
	$(DISC_PATH)/ipx.mmd \
	$(DISC_PATH)/game.mmd \
	$(DISC_PATH)/stage1.mmd \
	$(PROJECT_ID).iso

clean:
	@rm -f $(PROJECT_ID).iso $(DISC_PATH)/*.mmd $(DISC_PATH)/*.smd $(BUILD_PATH)/* > /dev/null 2>&1

## The IPX: the kernel that runs after the boot sector. It loads the first
## user module (the title screen) and provides the engine services.
## (note: headers must not be listed as prerequisites - megadev's pattern rule
##  turns every prerequisite into a .o target, so we do clean builds instead)
$(DISC_PATH)/ipx.mmd: \
	ipx_layout.s \
	main/ipx_init.s \
	ipx.c

## The game module: the title screen / stage logic
$(DISC_PATH)/game.mmd: \
	shared_mmd_layout.s \
	std_init.s \
	game.c \
	game_res.s \
	$(DISC_PATH)/ipx.mmd

## Stage 1: the decoded PC Engine stage screen + scrolling test
$(DISC_PATH)/stage1.mmd: \
	shared_mmd_layout.s \
	std_init.s \
	stage1.c \
	stage1_res.s \
	$(DISC_PATH)/ipx.mmd
