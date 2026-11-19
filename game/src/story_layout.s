#include "macros.s"

/* The resident IPX occupies the bottom of main RAM. Run the movie player
 * above it so the Sub CPU can refill Word RAM without interrupting CD-DA. */
GLOBAL MMD_DEST 0xff1000
GLOBAL MODULE_ROM_ORIGIN 0xff1000
GLOBAL MODULE_ROM_LENGTH 0x1f00
GLOBAL MODULE_RAM_ORIGIN 0xff3000
GLOBAL MODULE_RAM_LENGTH 0xfff500 - MODULE_RAM_ORIGIN
