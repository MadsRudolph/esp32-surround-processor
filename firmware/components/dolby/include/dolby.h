#pragma once
#include <stdbool.h>
#include <stdint.h>

/* Dolby Digital (AC-3) from an S/PDIF stream, for a 4.0 speaker layout.
 *
 * A TV set to "bitstream" sends AC-3 frames wrapped in IEC 61937 data bursts: the
 * 16-bit words F872 4E1F, a type word, a length word, then the frame. dd_parse()
 * finds the bursts in the I2S samples and hands out complete AC-3 frames;
 * dd_decode() turns one frame into 1536 samples for four speakers.
 *
 * Plain C with no ESP-IDF calls, so the same code runs in tools/dolby_test.c on a PC.
 */

#define DD_FRAME_MAX   3840          /* largest AC-3 frame, bytes (640 kbit/s at 32 kHz) */
#define DD_SAMPLES     1536          /* samples per channel in every AC-3 frame */

typedef struct {
    int state, shift, type, words_left, len, pos;
    uint16_t prev[2];
    uint32_t bursts;                 /* every data burst seen, any type */
    uint32_t ac3_frames;             /* complete AC-3 frames handed out */
    uint32_t other;                  /* bursts of a type this code cannot decode (DTS, E-AC-3...) */
    uint8_t buf[DD_FRAME_MAX];
} dd_parser_t;

typedef void (*dd_frame_cb)(const uint8_t *frame, int len, void *ctx);

/* Feed stereo frames (32-bit slots, as read from I2S). Calls cb for each complete AC-3
   frame. Returns the number of burst preambles found in this block. */
int dd_parse(dd_parser_t *p, const int32_t *in, int nframes, dd_frame_cb cb, void *ctx);

typedef struct {
    int sample_rate, bitrate;        /* Hz, bit/s */
    int front, rear, lfe;            /* source layout, e.g. 3, 2, 1 for 5.1 */
    bool has_surround;               /* false: the frame was mono or stereo, out[] has fronts only */
} dd_info_t;

#define DD_BLOCK       256           /* an AC-3 frame is 6 blocks of 256 samples */
typedef void (*dd_block_cb)(const int32_t *frames, void *ctx);

/* Decode one AC-3 frame. cb is called 6 times, each with DD_BLOCK frames of
   FL, FR, SL, SR (interleaved, full scale = +-2^31). Centre is folded into the fronts
   by the decoder; the LFE channel is added to both fronts. Returns 0, or -1 if the
   frame is damaged (cb may already have been called for the blocks before the damage). */
int dd_decode(const uint8_t *frame, int len, dd_block_cb cb, void *ctx, dd_info_t *info);
