/* Host test for firmware/components/dolby: feed an IEC 61937 stream (as ffmpeg -f spdif
 * writes it: 16-bit little-endian stereo words) through the same parser and decoder the
 * board uses, in 240-frame blocks like the firmware, and print the level of each of the
 * four outputs per second.   Build and run: tools/dolby_test.sh <video or audio file>  */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "dolby.h"

static double acc[4]; static long nacc, sec, frames, bad;
static dd_info_t info;
static double dec_s;

static void on_block(const int32_t *pcm, void *ctx)
{
    if (!info.sample_rate) return;
    for (int i = 0; i < DD_BLOCK; i++) {
        for (int c = 0; c < 4; c++) { double v = pcm[4 * i + c] / 2147483648.0; acc[c] += v * v; }
        if (++nacc == info.sample_rate) {
            printf("t=%3lds  FL %6.1f  FR %6.1f  SL %6.1f  SR %6.1f dB\n", sec++,
                   10 * log10(acc[0] / nacc + 1e-14), 10 * log10(acc[1] / nacc + 1e-14),
                   10 * log10(acc[2] / nacc + 1e-14), 10 * log10(acc[3] / nacc + 1e-14));
            acc[0] = acc[1] = acc[2] = acc[3] = 0; nacc = 0;
        }
    }
}

static void on_frame(const uint8_t *f, int len, void *ctx)
{
    clock_t t = clock();
    int r = dd_decode(f, len, on_block, NULL, &info);
    dec_s += (double)(clock() - t) / CLOCKS_PER_SEC;
    frames++;
    if (r) bad++;
}

int main(int argc, char **argv)
{
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 1;
    static dd_parser_t p;
    int16_t w[480]; int32_t in[480]; size_t n;
    while ((n = fread(w, 2, 480, f)) > 0) {
        for (size_t i = 0; i < n; i++) in[i] = (int32_t)((uint32_t)(uint16_t)w[i] << 16);
        dd_parse(&p, in, n / 2, on_frame, NULL);
    }
    printf("bursts %u, AC-3 frames %u, undecodable %ld, other types %u\n", p.bursts, p.ac3_frames, bad, p.other);
    printf("source %d/%d.%d, %d Hz, %d kbit/s, surround %s, decode %.3f ms per frame on this PC\n",
           info.front, info.rear, info.lfe, info.sample_rate, info.bitrate / 1000,
           info.has_surround ? "yes" : "no", 1000 * dec_s / (frames ? frames : 1));
    return 0;
}
