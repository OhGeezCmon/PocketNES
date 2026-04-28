#include "../equates.h"
#include "../6502mac.h"

MAPPER_OVERLAY_TEXT(4)

	global_func mapper9init
	global_func mapper10init
	global_func mapper9BGcheck
	global_func mapper9_latch
@	global_func mapper_9_hook

 reg0 = mapperdata+0
 reg1 = mapperdata+1
 reg2 = mapperdata+2
 reg3 = mapperdata+3
 lolatch = mapperdata+4 @0=FD, 1=FE (PPU $0000-$0FFF)
 hilatch = mapperdata+5 @0=FD, 1=FE (PPU $1000-$1FFF)
 prgsel  = mapperdata+6 @PRG bank select ($A000-$AFFF), 8KB units (mask differs for 9 vs 10)
@----------------------------------------------------------------------------
mapper9init:	@MMC2 (iNES mapper 9)
@----------------------------------------------------------------------------
	.word empty_W,a000_9,c000,e000
map10start:
	stmfd sp!,{lr}
	ldrb_ r0,cartflags
	bic r0,r0,#SCREEN4	@(many punchout roms have bad headers)
	strb_ r0,cartflags

@	ldr r0,=mapper_9_hook
@	str_ r0,scanlinehook

	@ Default latches = FD
	mov r0,#0
	strb_ r0,lolatch
	strb_ r0,hilatch

	@ Default PRG select = 0
	strb_ r0,prgsel

	@ PRG layout (MMC2 / mapper 9): $8000 switchable 8KB, $A000-$FFFF fixed to last 3 banks.
	@ Deterministically compute last bank index from rommask (do not use negative indices).
	mov r0,#0
	bl_long map89_      @ $8000-$9FFF = bank 0 (8KB)

	ldr_ r1,rommask
	mov r3,r1,lsr#SHIFT_8K   @ r3 = last 8KB bank index (keep across map**_ calls)
	@ last-3
	sub r0,r3,#2
	bl_long mapAB_
	@ last-2
	sub r0,r3,#1
	bl_long mapCD_
	@ last-1
	mov r0,r3
	bl_long mapEF_
	ldmfd sp!,{pc}
@----------------------------------------------------------------------------
mapper10init:
@----------------------------------------------------------------------------
	.word empty_W,a000_10,c000,e000
	b_long map10start
@----------------------------------------------------------------------------
@ .align
@ .pool
@ .section .iwram, "ax", %progbits
@ .subsection 7
@ .align
@ .pool
@----------------------------------------------------------------------------
@------------------------------
a000_10:
	tst addy,#0x1000
	beq_long a000_prg_10
	b b000
@------------------------------
a000_9:
	tst addy,#0x1000
	beq_long a000_prg_9
b000: @-------------------------
	and r0,r0,#0x1F
	strb_ r0,reg0
	ldrb_ r1,lolatch
	tst r1,#0xFF
	bne 0f
	stmfd sp!,{lr}
	bl_long chr0123_
	ldmfd sp!,{pc}
0:
	mov pc,lr
c000: @-------------------------
	tst addy,#0x1000
	bne d000

	and r0,r0,#0x1F
	strb_ r0,reg1
	ldrb_ r1,lolatch
	tst r1,#0xFF
	beq 0f
	stmfd sp!,{lr}
	bl_long chr0123_
	ldmfd sp!,{pc}
0:
	mov pc,lr
	@mov pc,lr
d000: @-------------------------
	and r0,r0,#0x1F
	strb_ r0,reg2
	ldrb_ r1,hilatch
	tst r1,#0xFF
	bne 0f
	stmfd sp!,{lr}
	bl_long chr4567_
	ldmfd sp!,{pc}
0:
	mov pc,lr
e000: @-------------------------
	tst addy,#0x1000
	bne f000

	and r0,r0,#0x1F
	strb_ r0,reg3
	ldrb_ r1,hilatch
	tst r1,#0xFF
	beq 0f
	stmfd sp!,{lr}
	bl_long chr4567_
	ldmfd sp!,{pc}
0:
	mov pc,lr
f000: @-------------------------
	tst r0,#1
	b_long mirror2V_

@----------------------------------------------------------------------------
@ $A000-$AFFF: PRG select (mapper 9: 8KB at $8000)
@----------------------------------------------------------------------------
a000_prg_9:
	and r0,r0,#0x0F
	strb_ r0,prgsel
	b_long map89_

@----------------------------------------------------------------------------
@ $A000-$AFFF: PRG select (mapper 10/MMC4: 16KB at $8000-$BFFF)
@----------------------------------------------------------------------------
a000_prg_10:
	and r0,r0,#0x0F
	strb_ r0,prgsel
	b_long map89AB_

@----------------------------------------------------------------------------
@ mapper9_latch: update MMC2 latches on PPU CHR reads
@ in: r0 = PPU address (0x0000-0x1FFF)
@----------------------------------------------------------------------------
mapper9_latch:
	stmfd sp!,{lr}
	@ Low table latch triggers:
	@  $0FD8 -> FD (0)
	@  $0FE8 -> FE (1)
	cmp r0,#0x1000
	bge 1f
	ldr r2,=0x0FD8
	cmp r0,r2
	beq 2f
	ldr r2,=0x0FE8
	cmp r0,r2
	beq 3f
	ldmfd sp!,{pc}
2:	@ set lo latch = FD
	ldrb_ r1,lolatch
	cmp r1,#0
	ldmeqfd sp!,{pc}
	mov r1,#0
	strb_ r1,lolatch
	bl_long init_sprite_cache
	ldrb_ r0,reg0
	bl_long chr0123_
	ldmfd sp!,{pc}
3:	@ set lo latch = FE
	ldrb_ r1,lolatch
	cmp r1,#1
	ldmeqfd sp!,{pc}
	mov r1,#1
	strb_ r1,lolatch
	bl_long init_sprite_cache
	ldrb_ r0,reg1
	bl_long chr0123_
	ldmfd sp!,{pc}
1:
	@ High table latch triggers:
	@  $1FD8-$1FDF -> FD (0)
	@  $1FE8-$1FEF -> FE (1)
	ldr r2,=0x1FD8
	cmp r0,r2
	blt 4f
	ldr r2,=0x1FDF
	cmp r0,r2
	ble 5f
4:
	ldr r2,=0x1FE8
	cmp r0,r2
	blt 6f
	ldr r2,=0x1FEF
	cmp r0,r2
	ble 7f
6:
	ldmfd sp!,{pc}
5:	@ set hi latch = FD
	ldrb_ r1,hilatch
	cmp r1,#0
	ldmeqfd sp!,{pc}
	mov r1,#0
	strb_ r1,hilatch
	bl_long init_sprite_cache
	ldrb_ r0,reg2
	bl_long chr4567_
	ldmfd sp!,{pc}
7:	@ set hi latch = FE
	ldrb_ r1,hilatch
	cmp r1,#1
	ldmeqfd sp!,{pc}
	mov r1,#1
	strb_ r1,hilatch
	bl_long init_sprite_cache
	ldrb_ r0,reg3
	bl_long chr4567_
	ldmfd sp!,{pc}
@@------------------------------
@mapper_9_hook:
@@------------------------------
@	ldr_ r0,scanline
@	sub r0,r0,#1
@	tst r0,#7
@	ble h9
@	cmp r0,#239
@	bhi h9
@
@	ldr r2,=latchtbl
@	ldrb r0,[r2,r0,lsr#3]
@
@	cmp r0,#0xfd
@	ldreqb_ r0,reg2
@	ldrneb_ r0,reg3
@	bl_long chr4567_
@h9:
@	fetch 0

@------------------------------
mapper9BGcheck: @called from PPU.s, r0=FD-FF
@------------------------------
	cmp r0,#0xff
	moveq pc,lr

	ldr r1,=latchtbl
	and r2,addy,#0x3f
	cmp r2,#0x10
	strlob r0,[r1,addy,lsr#6]

	mov pc,lr
MAPPER_OVERLAY(4)

latchtbl: .skip 32
@----------------------------------------------------------------------------
	@.end
