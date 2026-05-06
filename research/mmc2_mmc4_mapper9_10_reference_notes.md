# MMC2 / MMC4 (iNES mapper 9 / 10) — reference notes for PocketNES work

This file is **research scaffolding**: it points at authoritative hardware descriptions and at **mature OSS emulator implementations** that already solved MMC2/MMC4 latch behavior. The immediate PocketNES motivator is **`mtpo.nes` (mapper 9 / MMC2)**.

## Hardware / specs (start here)

- NESdev Wiki — **MMC2**: https://www.nesdev.org/wiki/MMC2  
  Focus areas for emulator implementation:
  - CHR latch triggers occur due to **PPU pattern table fetches** while rendering (not CPU writes to CHR-RAM).
  - Two independent “half-table” regions: **$0000–$0FFF** vs **$1000–$1FFF**.
  - Within each 4KB half, the latch selects between **two** CHR banks depending on whether the last triggering fetch class was **FD** vs **FE**.

## What “correct” generally looks like in reference emulators

Across Mesen2 / FCEUX / Nestopia, the common model is:

1. **Mapper registers**
   - MMC2 / MMC4 expose CHR banking registers that correspond to the **FD** slot and **FE** slot for each pattern-table half.
   - Writes to those registers update stored bank numbers and then **re-apply** `SelectChrPage` / `SwapBank` using the **currently latched** slot (Mesen2 does this directly in `WriteRegister`; Nestopia does `SwapBanks` using `banks[selector[*]]`; FCEUX calls `Sync()`).

2. **Latch updates happen on PPU VRAM/PPU-read timing**
   - Mesen2 implements this as `NotifyVramAddressChange(uint16_t addr)` on the mapper side (`EnableVramAddressHook()`), driven by the core’s PPU read stream.

3. **MMC2 vs MMC4 differs mainly in PRG banking + sometimes latch-address decoding width**
   - **MMC4** tends to treat *left-table* latch addresses as **ranges** (see Mesen2 `MMC4.h`), whereas **MMC2** often uses **exact** addresses for the left table (see Mesen2 `MMC2.h`).
   - PRG sizes differ: MMC2 typically uses **8KB switchable + fixed tail**, MMC4 uses **16KB switchable** (see Mesen2 `MMC2.h` vs `MMC4::InitMapper()`).

## OSS references (high-signal source locations)

### Mesen2 (recommended primary reference — clean separation of MMC2 vs MMC4)

Repository: https://github.com/SourMesen/Mesen2

- `Core/NES/Mappers/Nintendo/MMC2.h`  
  Raw: https://raw.githubusercontent.com/SourMesen/Mesen2/master/Core/NES/Mappers/Nintendo/MMC2.h  

Key items to mirror when auditing PocketNES:

- **Initialization defaults**: `_leftLatch` / `_rightLatch` start at **1** (Mesen’s convention maps latch state to **which CHR register slot is active**).
- **`WriteRegister`**: each CHR register write updates one slot, then immediately selects CHR using `_leftChrPage[_leftLatch]` / `_rightChrPage[_rightLatch]` (no “only sometimes apply CHR” behavior).
- **`NotifyVramAddressChange`**:
  - MMC2 left side uses **exact** compares for `0x0FD8` and `0x0FE8`.
  - MMC2 right side uses **ranges** `0x1FD8–0x1FDF` and `0x1FE8–0x1FEF`.
  - After latch changes, Mesen2 applies CHR updates on the **next** VRAM hook (`_needChrUpdate` deferral pattern).

- `Core/NES/Mappers/Nintendo/MMC4.h`  
  Raw: https://raw.githubusercontent.com/SourMesen/Mesen2/master/Core/NES/Mappers/Nintendo/MMC4.h  

MMC4 overrides `NotifyVramAddressChange` to widen left-side matching to **ranges** (`0x0FD8–0x0FDF`, `0x0FE8–0x0FEF`), matching the common “MMC4 differs from MMC2” hardware notes.

### Mesen (original Mesen)

Repository: https://github.com/SourMesen/Mesen

Mesen classic also carried an MMC2 implementation under roughly:

- `Core/MMC2.h` (same conceptual structure as Mesen2; useful if you want to compare older naming / edge cases).

### FCEUX — mapper 9 + 10 share one implementation

Repository: https://github.com/TASVideos/fceux

- `src/boards/mmc2and4.cpp`  
  Raw: https://raw.githubusercontent.com/TASVideos/fceux/master/src/boards/mmc2and4.cpp  

Notable details:

- `Mapper9_Init` vs `Mapper10_Init` flip `is10` (MMC4 behavior includes WRAM setup).
- `MMC2and4PPUHook(uint32 A)` shows the **address-bit decode** approach used by FCEUX:
  - Filters to pattern table fetches
  - Uses low nybble patterns `0xD0` / `0xE0` for FD vs FE classes (equivalent to Mesen2’s `…FD8` / `…FE8` alignment assumptions, expressed differently).

### Nestopia — MMC2 CHR accessor hook is extremely explicit

Repository: https://github.com/0ldsk00l/nestopia

- `source/core/board/NstBoardMmc2.cpp`  
  Raw: https://raw.githubusercontent.com/0ldsk00l/nestopia/master/source/core/board/NstBoardMmc2.cpp  

This is useful because it shows the latch trigger directly on **CHR read paths**:

- `Access_Chr` switches on `address & 0xFF8` with cases `0xFD8` / `0xFE8`, updates `selector[...]`, then calls `chr.SwapBank(...)`.

MMC4 in Nestopia is mostly **PRG mapping** differences (`NstBoardMmc4.cpp` delegates to `Mmc2::SubReset`).

## PocketNES-specific audit anchors (what to compare against references)

### Mapper assembly

File: `src/mappers/map9.s`

- Export/hooks: `mapper9init`, `mapper10init`, `mapper9_latch`, plus CHR writers (`b000`/`c000`/…).

### PPU-side latch injection sites

File: `src/ppu.s`

There are multiple call sites to `mapper9_latch` including:

- Background decode path that triggers off **tile indices** `0xFD/0xFE` / `0x1FD/0x1FE` with explicit effective addresses `0x0FD8`, `0x0FE8`, `0x1FD8`, `0x1FE8`.
- Sprite paths construct addresses like `0x0FD8` vs `0x0FE8` (and adjust by `+0x1000` when sprites use the upper pattern table via `PPUCTRL`).

When reconciling against Mesen2/Nestopia, verify:

- **Mapper 9 vs mapper 10** differences for left-table latch decoding (**exact address** vs **range**) match Mesen2’s split (`MMC2.h` vs `MMC4.h`).
- PocketNES’s internal latch numbering matches how CHR registers are selected on writes (avoid accidental swaps between **FD slot** vs **FE slot**).

### Git history signal (why this keeps resurfacing)

`src/mappers/map9.s` history includes an MMC2 attempt explicitly marked **still broken** in commit message (`a05bf7a` in this repo’s history), plus a later Thumb interworking tweak (`cca80ee`). Treat those commits as archaeology, not ground truth.

## Practical “definition of done” for Punch-Out (`mtpo.nes`)

Minimum acceptance criteria:

- No crashes in sprite fetch paths tied to mapper CHR switching (historical crash PCs pointed into `need_to_fetch_sprite_data` / sprite pipeline in `ppu.s`).
- Visual correctness on screens that rely on FD/FE latch transitions (intro/story sequences are typical stress tests).

## How future agents should use this doc

1. Read Mesen2 `MMC2.h` + `MMC4.h` until the latch + register-write semantics are intuitive.
2. Compare directly against PocketNES `map9.s` + `mapper9_latch` call sites in `ppu.s`.
3. When behavior differs, prefer aligning PocketNES to Mesen2/Nestopia **event timing + banking apply rules**, not to PocketNES’s prior assumptions.
