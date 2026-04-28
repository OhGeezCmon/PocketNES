# PocketNES packer (host tool)

Creates a **PocketNES “compilation” `.gba`** by appending one or more raw `.nes` files to a base `pocketnes.gba`.

PocketNES expects each embedded ROM entry to be:

- `romheader` (48 bytes)
- followed immediately by the `.nes` file bytes (starting with the 16-byte iNES header)

## Build (MSYS2 MinGW64)

From a **MinGW64** shell:

```bash
cd /c/Users/benedict/Documents/GitHub/PocketNES/tools/pocketnes_packer
make
```

This produces `pocketnes-pack.exe`.

## Usage

```bash
./pocketnes-pack.exe --emu /path/to/pocketnes.gba --out /path/to/PocketNESMenu.gba --rom /path/to/game1.nes --rom /path/to/game2.nes
```

Notes:
- Only raw `.nes` is supported (no `.zip`) for now.
- `--rom` can be repeated.

