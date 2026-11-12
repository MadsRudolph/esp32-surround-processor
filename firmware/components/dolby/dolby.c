#include <string.h>
#include "dolby.h"      /* brings stdint.h, which a52.h needs first */
#include "a52.h"

#define LFE_GAIN 1.0f                /* LFE into each front: the sub is fed from the fronts */

/* ---------------------------------------------------------------- burst parser */

enum { S_SEARCH, S_PC, S_PD, S_PAYLOAD, S_SKIP };

static void word(dd_parser_t *p, uint32_t slot, dd_frame_cb cb, void *ctx, int *found)
{
    if (p->state == S_SEARCH) {
        /* the 16 data bits sit at the top of the slot (or 8 bits lower on some sources) */
        for (int k = 0; k < 2; k++) {
            uint16_t w = slot >> (k ? 8 : 16);
            if (p->prev[k] == 0xF872 && w == 0x4E1F) {
                p->shift = k ? 8 : 16;
                p->state = S_PC;
                p->bursts++;
                (*found)++;
                p->prev[0] = p->prev[1] = 0;
                return;
            }
            p->prev[k] = w;
        }
        return;
    }
    uint16_t w = slot >> p->shift;
    switch (p->state) {
    case S_PC:
        p->type = w & 0x1F;
        p->state = S_PD;
        break;
    case S_PD:
        p->len = (w + 7) / 8;                        /* length is in bits */
        p->words_left = (w + 15) / 16;
        p->pos = 0;
        if (p->type == 1 && p->len >= 64 && p->len <= DD_FRAME_MAX) {
            p->state = S_PAYLOAD;
        } else {
            if (p->type != 0 && p->type != 3) p->other++;   /* 0 = null data, 3 = pause */
            p->state = p->words_left ? S_SKIP : S_SEARCH;
        }
        break;
    case S_PAYLOAD:
        p->buf[p->pos++] = w >> 8;
        p->buf[p->pos++] = w & 0xFF;
        if (--p->words_left == 0) {
            if (p->buf[0] == 0x77 && p->buf[1] == 0x0B)      /* byte-swapped source */
                for (int i = 0; i + 1 < p->pos; i += 2) {
                    uint8_t t = p->buf[i]; p->buf[i] = p->buf[i + 1]; p->buf[i + 1] = t;
                }
            if (p->buf[0] == 0x0B && p->buf[1] == 0x77) {
                p->ac3_frames++;
                cb(p->buf, p->len, ctx);
            }
            p->state = S_SEARCH;
        }
        break;
    case S_SKIP:
        if (--p->words_left == 0) p->state = S_SEARCH;
        break;
    }
}

int dd_parse(dd_parser_t *p, const int32_t *in, int nframes, dd_frame_cb cb, void *ctx)
{
    int found = 0;
    for (int i = 0; i < 2 * nframes; i++) word(p, (uint32_t)in[i], cb, ctx, &found);
    return found;
}

/* ---------------------------------------------------------------- decoder */

static a52_state_t *st;

static inline int32_t to_i32(float x)
{
    if (x > 0.999999f) x = 0.999999f;
    if (x < -0.999999f) x = -0.999999f;
    return (int32_t)(x * 2147483648.0f);
}

int dd_decode(const uint8_t *frame, int len, dd_block_cb cb, void *ctx, dd_info_t *info)
{
    if (!st && !(st = a52_init(0))) return -1;

    int flags, rate, bitrate;
    int flen = a52_syncinfo((uint8_t *)frame, &flags, &rate, &bitrate);
    if (flen <= 0 || flen > len) return -1;

    static const uint8_t NFRONT[] = { 2, 1, 2, 3, 2, 3, 2, 3 }, NREAR[] = { 0, 0, 0, 0, 1, 1, 2, 2 };
    int acmod = flags & A52_CHANNEL_MASK;
    if (info) {
        info->sample_rate = rate; info->bitrate = bitrate;
        info->front = acmod <= 7 ? NFRONT[acmod] : 2;
        info->rear = acmod <= 7 ? NREAR[acmod] : 0;
        info->lfe = flags & A52_LFE ? 1 : 0;
    }

    /* ask for two fronts and two rears: the decoder folds the centre into the fronts */
    sample_t level = 1, bias = 0;
    flags = A52_2F2R | A52_LFE | A52_ADJUST_LEVEL;
    if (a52_frame(st, (uint8_t *)frame, &flags, &level, bias)) return -1;

    int got = flags & A52_CHANNEL_MASK;
    bool lfe = flags & A52_LFE;
    if (info) info->has_surround = got == A52_2F2R || got == A52_2F1R;

    for (int b = 0; b < 6; b++) {
        if (a52_block(st)) return -1;
        sample_t *s = a52_samples(st);
        sample_t *sub = lfe ? s : NULL, *c = lfe ? s + 256 : s;      /* LFE comes first */
        static int32_t o[DD_BLOCK * 4];
        for (int i = 0; i < 256; i++) {
            float l, r, sl = 0, sr = 0;
            switch (got) {
            case A52_2F2R: l = c[i]; r = c[256 + i]; sl = c[512 + i]; sr = c[768 + i]; break;
            case A52_2F1R: l = c[i]; r = c[256 + i]; sl = sr = c[512 + i] * 0.7071f; break;
            case A52_MONO: l = r = c[i] * 0.7071f; break;
            default:       l = c[i]; r = c[256 + i]; break;           /* stereo, Dolby Surround */
            }
            if (sub) { l += LFE_GAIN * sub[i]; r += LFE_GAIN * sub[i]; }
            o[4 * i] = to_i32(l); o[4 * i + 1] = to_i32(r); o[4 * i + 2] = to_i32(sl); o[4 * i + 3] = to_i32(sr);
        }
        cb(o, ctx);
    }
    return 0;
}
