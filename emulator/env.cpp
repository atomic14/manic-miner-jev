// ZX Spectrum emulator without a display, for use from Python.
// It can run frames, read and write memory, decode the screen, and save
// and load the machine state in memory.
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <array>
#include <cstring>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

#include "spectrum.h"
#include "snaps.h"

namespace py = pybind11;

// Standard ZX Spectrum palette: 0-7 normal, 8-15 bright.
static const uint8_t PALETTE[16][3] = {
    {0x00, 0x00, 0x00}, {0x00, 0x00, 0xD7}, {0xD7, 0x00, 0x00}, {0xD7, 0x00, 0xD7},
    {0x00, 0xD7, 0x00}, {0x00, 0xD7, 0xD7}, {0xD7, 0xD7, 0x00}, {0xD7, 0xD7, 0xD7},
    {0x00, 0x00, 0x00}, {0x00, 0x00, 0xFF}, {0xFF, 0x00, 0x00}, {0xFF, 0x00, 0xFF},
    {0x00, 0xFF, 0x00}, {0x00, 0xFF, 0xFF}, {0xFF, 0xFF, 0x00}, {0xFF, 0xFF, 0xFF}};

struct SavedState
{
  Z80Regs regs;
  // The saved banks, 16 KB each, in the order of `savedBanks` below: three
  // for a 48K machine, eight for a 128K one.
  std::vector<uint8_t> banks;
  uint8_t hwBank;
  tipo_hwopt hwopt;
  std::array<uint8_t, 8> keys;
  uint8_t kempston;
  bool mic;
  uint64_t frameCount;
  int line;
  int lineCycles;
  uint64_t totalCycles;
};

class RLSpectrum
{
public:
  ZXSpectrum *machine;
  uint64_t frameCount = 0;
  std::map<int, SavedState> slots;
  // A 48K machine maps banks 5, 2 and 0 only. Saving the other five copies
  // 80 KB of memory the game never touches, and a search keeps hundreds of
  // thousands of saved states.
  bool is128k;
  std::vector<int> savedBanks;

  explicit RLSpectrum(bool is128k = false) : is128k(is128k)
  {
    if (is128k)
    {
      savedBanks = {0, 1, 2, 3, 4, 5, 6, 7};
    }
    else
    {
      savedBanks = {0, 2, 5};
    }
    machine = new ZXSpectrum();
    machine->reset();
    machine->init_spectrum(is128k ? SPECMDL_128K : SPECMDL_48K);
    machine->reset_spectrum(machine->z80Regs);
  }

  ~RLSpectrum()
  {
    stopAudioCapture();
    delete machine;
  }

  bool loadZ80(const std::string &path)
  {
    return Load(machine, path.c_str());
  }

  bool saveZ80(const std::string &path)
  {
    Z80FileWriter writer(machine, path.c_str());
    return writer.saveZ80();
  }

  // Audio capture: the emulator core writes 312 raw 8-bit samples per frame
  // (15600 Hz mono) to a FILE* when given one - we normally discard it.
  FILE *audioFile = nullptr;

  bool startAudioCapture(const std::string &path)
  {
    stopAudioCapture();
    audioFile = fopen(path.c_str(), "wb");
    return audioFile != nullptr;
  }

  void stopAudioCapture()
  {
    if (audioFile)
    {
      fclose(audioFile);
      audioFile = nullptr;
    }
  }

  // The scanline the machine is on inside the current frame, 0 to 311.
  // Frame-based callers always see 0. Tick stepping leaves the machine
  // part way through a frame, and the next frame call finishes that frame
  // line by line before it uses the whole-frame path again.
  int line = 0;
  // T-states run into the current line by instruction stepping, 0 to 223.
  int lineCycles = 0;
  // T-states run in total, for an exact frame count: 69,888 per frame.
  uint64_t totalCycles = 0;
  // Speaker T-states run into the current line. `runForFrame` writes one
  // audio sample per line, taken from the same count, and a recording
  // needs one sample per line whichever path ran it.
  int lineMic = 0;

  // One audio sample for the line that just ended. The divide by 4 and the
  // clamp match `ZXSpectrum::runForFrame`, so both paths write the same
  // shape of sample and a recording that mixes them holds one level.
  void writeSample()
  {
    if (audioFile)
    {
      int value = lineMic / 4;
      if (value > 255)
      {
        value = 255;
      }
      uint8_t sample = (uint8_t)value;
      fwrite(&sample, 1, 1, audioFile);
    }
    lineMic = 0;
  }

  void setPortFF()
  {
    // The same border and attribute handling as runForFrame, one line.
    uint8_t *attrBase = machine->mem.currentScreen->data + 0x1800;
    if (line < 64 || line >= 192 + 64)
    {
      machine->hwopt.portFF = 0xFF;
    }
    else
    {
      machine->hwopt.portFF = *(attrBase + 32 * (line - 64) / 8);
    }
  }

  void endLine()
  {
    line++;
    if (line == 312)
    {
      machine->interrupt();
      line = 0;
      frameCount++;
    }
  }

  void runLine()
  {
    setPortFF();
    lineMic += machine->runForCycles(224 - lineCycles);
    totalCycles += 224 - lineCycles;
    lineCycles = 0;
    writeSample();
    endLine();
  }

  void runFrames(int n)
  {
    for (int i = 0; i < n; i++)
    {
      if (line != 0 || lineCycles != 0)
      {
        // Finish the partial frame a tick step left behind. `runLine`
        // writes one audio sample per line, the same as the whole-frame
        // path, so a recording that steps by ticks stays in step.
        while (line != 0 || lineCycles != 0)
        {
          runLine();
        }
        continue;
      }
      machine->runForFrame(nullptr, audioFile);
      frameCount++;
      totalCycles += 312 * 224;
    }
  }

  // Run instruction by instruction until the program counter reaches
  // `address`, and return the T-states that took. At least one instruction
  // runs. The game's main loop is not locked to the frame, so this is how
  // the game is stepped by its own tick: `address` is the main loop's call
  // to the air routine, 34795, which runs once per pass. The clock byte is
  // not a safe marker, because the light beam in cavern 18 calls the same
  // routine up to four more times in one pass. Interrupts are disabled in
  // the game, so the frame boundary's exact instruction does not matter.
  uint64_t runUntilPc(uint16_t address, uint64_t maxCycles)
  {
    Z80Regs *regs = machine->z80Regs;
    uint64_t spent = 0;
    do
    {
      lineMic += Z80Run(regs, 1);
      int cost = 1 - regs->cycles;
      spent += cost;
      totalCycles += cost;
      lineCycles += cost;
      while (lineCycles >= 224)
      {
        lineCycles -= 224;
        writeSample();
        endLine();
        setPortFF();
      }
    } while (regs->PC.W != address && spent < maxCycles);
    return spent;
  }

  // The program counter at the frame boundary. The game's main loop is not
  // locked to the emulator frame, so two machines with identical RAM can be
  // at different points in that loop; this is what tells them apart.
  uint16_t pc() const { return machine->z80Regs->PC.W; }

  // Every CPU register and the cycle counter, as bytes. Together with the
  // RAM this is the whole machine state; a search key that includes it
  // never merges two states with different futures.
  py::bytes cpuState() const
  {
    const Z80Regs *r = machine->z80Regs;
    const uint16_t words[] = {r->AF.W, r->BC.W, r->DE.W, r->HL.W, r->IX.W,
                              r->IY.W, r->PC.W, r->SP.W, r->R.W, r->AFs.W,
                              r->BCs.W, r->DEs.W, r->HLs.W, r->IRequest};
    std::string out(reinterpret_cast<const char *>(words), sizeof(words));
    const uint8_t bytes[] = {r->IFF1, r->IFF2, r->I, r->halted,
                             static_cast<uint8_t>(r->IM)};
    out.append(reinterpret_cast<const char *>(bytes), sizeof(bytes));
    const int32_t ints[] = {r->we_are_on_ddfd, r->cycles};
    out.append(reinterpret_cast<const char *>(ints), sizeof(ints));
    return py::bytes(out);
  }

  // Kempston joystick bits: 1=right, 2=left, 4=down, 8=up, 16=fire.
  void setJoystick(uint8_t bits) { machine->kempston_port = bits; }
  uint8_t getJoystick() const { return machine->kempston_port; }

  void setKey(int key, bool down)
  {
    machine->updateKey((SpecKeys)key, down ? 1 : 0);
  }

  int peek(int address) { return machine->z80_peek((uint16_t)address); }
  void poke(int address, int value) { machine->z80_poke((uint16_t)address, (uint8_t)value); }

  py::bytes peekRange(int address, int length)
  {
    std::string out;
    out.reserve(length);
    for (int i = 0; i < length; i++)
    {
      out.push_back((char)machine->z80_peek((uint16_t)(address + i)));
    }
    return py::bytes(out);
  }

  // Raw display file: 6144 bytes of bitmap + 768 bytes of attributes.
  py::array_t<uint8_t> getScreenRaw()
  {
    auto result = py::array_t<uint8_t>(6912);
    std::memcpy(result.mutable_data(), machine->mem.currentScreen->data, 6912);
    return result;
  }

  // Decoded 192x256x3 RGB image of the screen area (no border).
  py::array_t<uint8_t> getScreenRGB()
  {
    auto result = py::array_t<uint8_t>({192, 256, 3});
    uint8_t *rgb = result.mutable_data();
    const uint8_t *screen = machine->mem.currentScreen->data;
    const uint8_t *attrBase = screen + 0x1800;
    bool flashPhase = ((frameCount >> 4) & 1) != 0;
    for (int y = 0; y < 192; y++)
    {
      // ZX screen memory layout: interleaved scanline addressing
      int scan = (y & 0b11000000) + ((y & 0b111) << 3) + ((y & 0b111000) >> 3);
      const uint8_t *pixelRow = screen + 32 * scan;
      const uint8_t *attrRow = attrBase + 32 * (y / 8);
      uint8_t *out = rgb + y * 256 * 3;
      for (int col = 0; col < 32; col++)
      {
        uint8_t attr = attrRow[col];
        uint8_t ink = attr & 0x07;
        uint8_t paper = (attr >> 3) & 0x07;
        if ((attr & 0x80) && flashPhase)
        {
          uint8_t tmp = ink;
          ink = paper;
          paper = tmp;
        }
        if (attr & 0x40)
        {
          ink += 8;
          paper += 8;
        }
        uint8_t bits = pixelRow[col];
        for (int x = 0; x < 8; x++)
        {
          const uint8_t *color = PALETTE[(bits & 0x80) ? ink : paper];
          out[0] = color[0];
          out[1] = color[1];
          out[2] = color[2];
          out += 3;
          bits <<= 1;
        }
      }
    }
    return result;
  }

  void saveState(int slot)
  {
    SavedState &s = slots[slot];
    s.regs = *machine->z80Regs;
    s.banks.resize(savedBanks.size() * 0x4000);
    for (size_t i = 0; i < savedBanks.size(); i++)
    {
      std::memcpy(s.banks.data() + i * 0x4000,
                  machine->mem.banks[savedBanks[i]]->data, 0x4000);
    }
    s.hwBank = machine->mem.hwBank;
    s.hwopt = machine->hwopt;
    std::memcpy(s.keys.data(), speckey, 8);
    s.kempston = machine->kempston_port;
    s.mic = machine->micLevel;
    s.frameCount = frameCount;
    s.line = line;
    s.lineCycles = lineCycles;
    s.totalCycles = totalCycles;
  }

  void loadState(int slot)
  {
    auto it = slots.find(slot);
    if (it == slots.end())
    {
      throw std::runtime_error("no saved state in slot " + std::to_string(slot));
    }
    SavedState &s = it->second;
    // z80Regs->userInfo points back at the machine - keep it intact
    void *userInfo = machine->z80Regs->userInfo;
    *machine->z80Regs = s.regs;
    machine->z80Regs->userInfo = userInfo;
    for (size_t i = 0; i < savedBanks.size(); i++)
    {
      std::memcpy(machine->mem.banks[savedBanks[i]]->data,
                  s.banks.data() + i * 0x4000, 0x4000);
    }
    machine->hwopt = s.hwopt;
    machine->mem.page(s.hwBank, true);
    std::memcpy(speckey, s.keys.data(), 8);
    machine->kempston_port = s.kempston;
    machine->micLevel = s.mic;
    frameCount = s.frameCount;
    line = s.line;
    lineCycles = s.lineCycles;
    totalCycles = s.totalCycles;
  }

  bool hasState(int slot) const { return slots.count(slot) != 0; }

  void dropState(int slot) { slots.erase(slot); }

  void clearStates(int minSlot)
  {
    for (auto it = slots.begin(); it != slots.end();)
    {
      if (it->first >= minSlot)
      {
        it = slots.erase(it);
      }
      else
      {
        ++it;
      }
    }
  }
};

PYBIND11_MODULE(zxspec, m)
{
  m.doc() = "ZX Spectrum emulator without a display, for use from Python";
  py::class_<RLSpectrum>(m, "RLSpectrum")
      .def(py::init<bool>(), py::arg("is128k") = false)
      .def("load_z80", &RLSpectrum::loadZ80, py::arg("path"))
      .def("save_z80", &RLSpectrum::saveZ80, py::arg("path"))
      .def("run_frames", &RLSpectrum::runFrames, py::arg("n") = 1)
      .def("set_joystick", &RLSpectrum::setJoystick, py::arg("bits"))
      .def("get_joystick", &RLSpectrum::getJoystick)
      .def("set_key", &RLSpectrum::setKey, py::arg("key"), py::arg("down"))
      .def("peek", &RLSpectrum::peek, py::arg("address"))
      .def("poke", &RLSpectrum::poke, py::arg("address"), py::arg("value"))
      .def("peek_range", &RLSpectrum::peekRange, py::arg("address"), py::arg("length"))
      .def("get_screen_raw", &RLSpectrum::getScreenRaw)
      .def("get_screen_rgb", &RLSpectrum::getScreenRGB)
      .def("save_state", &RLSpectrum::saveState, py::arg("slot") = 0)
      .def("load_state", &RLSpectrum::loadState, py::arg("slot") = 0)
      .def("has_state", &RLSpectrum::hasState, py::arg("slot") = 0)
      .def("clear_states", &RLSpectrum::clearStates, py::arg("min_slot"))
      .def("drop_state", &RLSpectrum::dropState, py::arg("slot"))
      .def("start_audio_capture", &RLSpectrum::startAudioCapture, py::arg("path"))
      .def("stop_audio_capture", &RLSpectrum::stopAudioCapture)
      .def("run_until_tick", &RLSpectrum::runUntilPc,
           py::arg("address") = 34795, py::arg("max_cycles") = 2000000)
      .def_readonly("scanline", &RLSpectrum::line)
      .def_readonly("total_cycles", &RLSpectrum::totalCycles)
      .def("pc", &RLSpectrum::pc)
      .def("cpu_state", &RLSpectrum::cpuState)
      .def_readonly("frame_count", &RLSpectrum::frameCount);
}
