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
	$(DISC_PATH)/spx.smd \
	$(DISC_PATH)/game.mmd \
	$(DISC_PATH)/stage1.mmd \
	$(DISC_PATH)/stage2.mmd \
	$(DISC_PATH)/stage2b.mmd \
	$(DISC_PATH)/stage3a.mmd \
	$(DISC_PATH)/stage2c.mmd \
	$(DISC_PATH)/stage2cg.mmd \
	$(DISC_PATH)/stage2cb.mmd \
	$(DISC_PATH)/stage1a.mmd \
	$(DISC_PATH)/stage4ax.mmd \
	$(DISC_PATH)/stage4a.mmd \
	$(DISC_PATH)/stage2a2.mmd \
	$(PROJECT_ID).iso

## ISO generation must wait for every module, including on parallel builds.
$(PROJECT_ID).iso: \
	$(BUILD_PATH)/boot.bin \
	$(DISC_PATH)/ipx.mmd \
	$(DISC_PATH)/spx.smd \
	$(DISC_PATH)/game.mmd \
	$(DISC_PATH)/stage1.mmd \
	$(DISC_PATH)/stage2.mmd \
	$(DISC_PATH)/stage2b.mmd \
	$(DISC_PATH)/stage3a.mmd \
	$(DISC_PATH)/stage2c.mmd \
	$(DISC_PATH)/stage2cg.mmd \
	$(DISC_PATH)/stage2cb.mmd \
	$(DISC_PATH)/stage1a.mmd \
	$(DISC_PATH)/stage4ax.mmd \
	$(DISC_PATH)/stage4a.mmd \
	$(DISC_PATH)/stage2a2.mmd

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

## The sub-CPU kernel loaded by sp.s during boot.
$(DISC_PATH)/spx.smd: \
	spx_layout.s \
	std_init.s \
	cham_voice_res.s \
	spx.c \
	$(BUILD_PATH)/sp.bin

## The game module: the title screen / stage logic
$(DISC_PATH)/game.mmd: \
	shared_mmd_layout.s \
	std_init.s \
	game.c \
	game_res.s \
	$(DISC_PATH)/ipx.mmd

## First playable stage: the Genesis city, from the street to the rooftops
$(DISC_PATH)/stage1.mmd: \
	shared_mmd_layout.s \
	std_init.s \
	city.c \
	city_res.s \
	$(DISC_PATH)/ipx.mmd

## Stage 2: real save-state BAT/VRAM/CRAM snapshot
$(DISC_PATH)/stage2.mmd: \
	shared_mmd_layout.s \
	std_init.s \
	stage2_state.c \
	stage2_state_res.s \
	$(DISC_PATH)/ipx.mmd

## Stage 2B: real .mc2 save-state forest room
$(DISC_PATH)/stage2b.mmd: \
	shared_mmd_layout.s \
	std_init.s \
	stage2b_state.c \
	stage2b_state_res.s \
	$(DISC_PATH)/ipx.mmd

## Stage 3A: real .mc4 save-state ice castle
$(DISC_PATH)/stage3a.mmd: \
	shared_mmd_layout.s \
	std_init.s \
	stage3a_state.c \
	stage3a_state_res.s \
	$(DISC_PATH)/ipx.mmd

## Stage 2C: real .mc2 save-state blue brick dungeon
$(DISC_PATH)/stage2c.mmd: \
	shared_mmd_layout.s \
	std_init.s \
	stage2c_state.c \
	stage2c_state_res.s \
	$(DISC_PATH)/ipx.mmd

## Stage 2C green room: one wrapped 32x24 window from the .mc3 capture
$(DISC_PATH)/stage2cg.mmd: \
	shared_mmd_layout.s \
	std_init.s \
	stage2c_green_state.c \
	stage2c_green_state_res.s \
	$(DISC_PATH)/ipx.mmd

## Stage 2C castle corridor: one window from the root .mc3 capture
$(DISC_PATH)/stage2cb.mmd: \
	shared_mmd_layout.s \
	std_init.s \
	stage2c_b_state.c \
	stage2c_b_state_res.s \
	$(DISC_PATH)/ipx.mmd

## Stage 2A room 2: real .mc1 save-state seaside cliffs
$(DISC_PATH)/stage2a2.mmd: \
	shared_mmd_layout.s \
	std_init.s \
	stage2a2_state.c \
	stage2a2_state_res.s \
	$(DISC_PATH)/ipx.mmd

## STG4A captured cemetery window
$(DISC_PATH)/stage4a.mmd: \
	shared_mmd_layout.s \
	std_init.s \
	stage4a_capture.c \
	stage4a_capture_res.s \
	$(DISC_PATH)/ipx.mmd

$(DISC_PATH)/stage1a.mmd: \
	shared_mmd_layout.s \
	std_init.s \
	stage1a_state.c \
	stage1a_state_res.s \
	$(DISC_PATH)/ipx.mmd

$(DISC_PATH)/stage4ax.mmd: \
	shared_mmd_layout.s \
	std_init.s \
	stage4a_state.c \
	stage4a_state_res.s \
	$(DISC_PATH)/ipx.mmd
