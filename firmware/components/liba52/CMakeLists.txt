# liba52 0.7.4 (a52dec), the AC-3 / Dolby Digital decoder. GPL-2.0-or-later, see COPYING.
# Sources from a52dec-0.7.4.tar.gz. config.h is ours, and there is ONE change to the
# original code: in src/imdct.c the FFT temporaries (lines 78, 90, 172, 186) are sample_t
# instead of double. The ESP32 has no double-precision FPU, and with doubles there the
# transform took 0.6 ms per channel per block, most of the decode time.
idf_component_register(SRCS "src/bit_allocate.c" "src/bitstream.c" "src/downmix.c" "src/imdct.c" "src/parse.c"
                       INCLUDE_DIRS "include" PRIV_INCLUDE_DIRS "src" LDFRAGMENTS "linker.lf")
# The ESP32's FPU is single precision only: keep every constant a float so the decoder
# never falls into software double arithmetic. The warnings are from 2002-era C.
target_compile_options(${COMPONENT_LIB} PRIVATE -O3 -ffast-math -fsingle-precision-constant -Wno-error -w)
