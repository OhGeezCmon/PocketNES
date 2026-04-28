SHELL := /usr/bin/bash

CXX ?= g++
CXXFLAGS ?= -O2 -std=c++17 -Wall -Wextra -Wpedantic

TARGET := pocketnes-pack
SRC := src/main.cpp

.PHONY: all clean

all: $(TARGET).exe

$(TARGET).exe: $(SRC)
	$(CXX) $(CXXFLAGS) -o $@ $^

clean:
	rm -f $(TARGET).exe
