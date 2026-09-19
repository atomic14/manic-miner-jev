# This file builds the zxspec Python module (the ZX Spectrum emulator).
# Run it from the project root:  uv run make -C emulator
PYTHON ?= python3

CXX = clang++
CXXFLAGS = \
	-O3 \
	-Wall \
	-std=c++17 \
	-fPIC \
	-IEmulator \
	-IEmulator/z80 \
	-IAudioOutput \
	-I. \
	-D__DESKTOP__ \
	$(shell $(PYTHON) -m pybind11 --includes)

LDFLAGS = -shared -undefined dynamic_lookup

SUFFIX = $(shell $(PYTHON) -c "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX'))")
# The module goes into the Python package, so that "import zxspec" works there.
TARGET = ../jevmanic/zxspec$(SUFFIX)

SRCS = \
	env.cpp \
	Emulator/128k_rom.cpp \
	Emulator/48k_rom.cpp \
	Emulator/spectrum.cpp \
	Emulator/z80/z80.cpp \
	Emulator/snaps.cpp \
	AYSound/AySound.cpp

OBJS = $(SRCS:.cpp=.o)

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $(TARGET) $(OBJS)

%.o: %.cpp Makefile
	$(CXX) $(CXXFLAGS) -MMD -c $< -o $@

-include $(OBJS:.o=.d)

clean:
	rm -f $(OBJS) $(OBJS:.o=.d) ../jevmanic/zxspec*.so

.PHONY: all clean
