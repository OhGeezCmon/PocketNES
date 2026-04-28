#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <string_view>
#include <vector>

namespace fs = std::filesystem;

struct RomHeader {
  char name[32];
  std::uint32_t filesize;
  std::uint32_t flags;
  std::uint32_t spritefollow;
  std::uint32_t reserved;
};

static_assert(sizeof(RomHeader) == 48, "RomHeader must be 48 bytes");

static void die(const std::string& msg) {
  std::cerr << "error: " << msg << "\n";
  std::exit(2);
}

static void usage(const char* argv0) {
  std::cerr
      << "PocketNES packer\n\n"
      << "Usage:\n"
      << "  " << argv0
      << " --emu pocketnes.gba --out PocketNESMenu.gba --rom game1.nes [--rom game2.nes ...]\n";
}

static std::vector<std::uint8_t> read_file(const fs::path& p) {
  std::ifstream f(p, std::ios::binary);
  if (!f) die("failed to open: " + p.string());
  f.seekg(0, std::ios::end);
  std::streamoff size = f.tellg();
  if (size < 0) die("failed to stat: " + p.string());
  f.seekg(0, std::ios::beg);

  std::vector<std::uint8_t> buf(static_cast<std::size_t>(size));
  if (!buf.empty() && !f.read(reinterpret_cast<char*>(buf.data()), size)) {
    die("failed to read: " + p.string());
  }
  return buf;
}

static void write_u32_le(std::ostream& out, std::uint32_t v) {
  std::uint8_t b[4] = {
      static_cast<std::uint8_t>(v & 0xFF),
      static_cast<std::uint8_t>((v >> 8) & 0xFF),
      static_cast<std::uint8_t>((v >> 16) & 0xFF),
      static_cast<std::uint8_t>((v >> 24) & 0xFF),
  };
  out.write(reinterpret_cast<const char*>(b), 4);
}

static void write_romheader(std::ostream& out, const RomHeader& h) {
  out.write(h.name, 32);
  write_u32_le(out, h.filesize);
  write_u32_le(out, h.flags);
  write_u32_le(out, h.spritefollow);
  write_u32_le(out, h.reserved);
}

static std::string basename_no_ext(const fs::path& p) {
  std::string s = p.filename().string();
  auto dot = s.find_last_of('.');
  if (dot != std::string::npos) s.resize(dot);
  return s;
}

static bool looks_like_ines(const std::vector<std::uint8_t>& nes) {
  return nes.size() >= 16 && nes[0] == 'N' && nes[1] == 'E' && nes[2] == 'S' && nes[3] == 0x1A;
}

int main(int argc, char** argv) {
  fs::path emu;
  fs::path out;
  std::vector<fs::path> roms;

  for (int i = 1; i < argc; i++) {
    std::string_view a(argv[i]);
    if (a == "--help" || a == "-h") {
      usage(argv[0]);
      return 0;
    }
    if (a == "--emu" && i + 1 < argc) {
      emu = argv[++i];
      continue;
    }
    if (a == "--out" && i + 1 < argc) {
      out = argv[++i];
      continue;
    }
    if (a == "--rom" && i + 1 < argc) {
      roms.emplace_back(argv[++i]);
      continue;
    }
    usage(argv[0]);
    die(std::string("unknown/invalid argument: ") + std::string(a));
  }

  if (emu.empty() || out.empty() || roms.empty()) {
    usage(argv[0]);
    die("missing required arguments");
  }

  auto emu_bytes = read_file(emu);
  if (emu_bytes.size() < 192) {
    die("base emulator file is unexpectedly small: " + emu.string());
  }

  std::ofstream o(out, std::ios::binary | std::ios::trunc);
  if (!o) die("failed to open for write: " + out.string());

  // Base .gba image.
  o.write(reinterpret_cast<const char*>(emu_bytes.data()),
          static_cast<std::streamsize>(emu_bytes.size()));

  // Append ROM entries: [romheader (48 bytes)] + [raw .nes bytes]
  for (const auto& rp : roms) {
    auto nes = read_file(rp);
    if (!looks_like_ines(nes)) {
      die("not a raw iNES .nes file (missing NES<1A> header): " + rp.string());
    }

    RomHeader h{};
    const std::string name = basename_no_ext(rp);
    for (std::size_t i = 0; i < sizeof(h.name); i++) {
      h.name[i] = 0;
    }
    for (std::size_t i = 0; i < sizeof(h.name) - 1 && i < name.size(); i++) {
      h.name[i] = name[i];
    }
    h.filesize = static_cast<std::uint32_t>(nes.size());
    h.flags = 0;
    h.spritefollow = 0;
    h.reserved = 0;

    write_romheader(o, h);
    o.write(reinterpret_cast<const char*>(nes.data()),
            static_cast<std::streamsize>(nes.size()));
  }

  if (!o) die("write failed: " + out.string());

  std::cout << "wrote " << out.string() << "\n";
  std::cout << "roms: " << roms.size() << "\n";
  return 0;
}

