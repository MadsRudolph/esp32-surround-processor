/* 4.0 surround from a stereo PCM input (matrix decode).
 *
 * The DIR9001 makes BCK and LRCK; both I2S ports are slaves on those pins.
 *
 *   front L, R : the input, untouched apart from the volume
 *   surround   : S = 0.5 * (L - R)
 *                -> high-pass 100 Hz (2nd order)
 *                -> low-pass 7 kHz (4th order Butterworth)
 *                -> 20 ms delay, so the fronts always arrive first
 *                the same S goes to surround left and right
 *
 *   USER press : mute / unmute (XSMT)
 *   BOOT press : next mode: surround -> stereo on all four -> front only
 *   pot (J7)   : volume for all four outputs
 *   status LED : on while samples arrive, fast blink with no clock, slow blink when muted
 *
 * GET /status reports the sample rate, the mode and the peak levels.
 */
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "driver/i2s_std.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_http_server.h"
#include "netota.h"
#include "dolby.h"
#include "freertos/queue.h"

#define PIN_BCK       14
#define PIN_LRCK      26
#define PIN_DIR_DATA  35
#define PIN_DIN_FRONT 2
#define PIN_DIN_SURR  13
#define PIN_XSMT      21
#define PIN_LED       17
#define PIN_BOOT      0
#define PIN_USER      15
#define POT_CHANNEL   ADC_CHANNEL_5          /* IO33 */

#define FRAMES     240
#define HPF_HZ     100.0f
#define LPF_HZ     7000.0f
#define DELAY_MS   20
#define DELAY_MAX  (96000 * DELAY_MS / 1000 + 8)

enum { MODE_SURROUND, MODE_STEREO_ALL, MODE_FRONT_ONLY, MODE_COUNT };
static const char *MODE_NAMES[] = { "surround", "stereo on all four", "front only" };

/* speaker test from the debug page: a soft chime on one output, the input ignored */
enum { TEST_OFF, TEST_FL, TEST_FR, TEST_SL, TEST_SR, TEST_ALL, TEST_COUNT };
static const char *TEST_NAMES[] = { "off", "fl", "fr", "sl", "sr", "all" };
static volatile int test = TEST_OFF;
static volatile int sound;                       /* speaker test sound: 0 = chime, 1 = slow sine sweep */
static volatile float sweep_hz;                  /* where the sweep is right now */
static volatile int drive = 0;                   /* strength of the two data outputs to the DACs, 0 weakest .. 3 */
static bool muted = true;                        /* starts muted: press USER to hear it */

/* ---- Dolby Digital path: parser in the audio task, decoder in its own task, a ring between them */
#define RING_FRAMES 2560                         /* one AC-3 frame (1536) plus start margin and slack */
#define DD_START_BLOCKS 3                        /* wait this many 5 ms blocks after the first frame: decode-time margin */
static int32_t ring[RING_FRAMES * 4];            /* FL FR SL SR */
static volatile uint32_t ring_wr, ring_rd;       /* frame counters; fill = wr - rd */
static uint8_t dd_slot[2][DD_FRAME_MAX];
static volatile int dd_decoding = -1;            /* slot the decoder is reading, -1 = idle */
static QueueHandle_t dd_q;
typedef struct { int slot, len; } dd_msg_t;
static volatile bool dd_has_surr;
static volatile uint32_t dd_frames, dd_errors, dd_dropped, dd_underrun, dd_dec_us_max, dd_dec_us_sum, dd_dec_n;
static volatile int dd_front, dd_rear, dd_lfe, dd_kbps;
static dd_parser_t parser;

static const char *TAG = "surround";

static i2s_chan_handle_t tx_front, rx_dir, tx_surr;
static volatile float gain = 0.0f;
static volatile int mode = MODE_SURROUND;
static volatile uint32_t fs_nominal = 48000;     /* set by the main loop from the measured rate */

/* written by the audio task, read once a second by the main loop */
static volatile uint32_t frames_in, read_timeouts, write_errors;
static volatile int32_t peak[2];
static volatile uint32_t tx_underrun[2], rx_overrun, loop_max_us, dsp_max_us, wr_max_us;   /* dropout hunting */
static volatile uint32_t ev_skip[3];              /* front TX, surround TX, RX: events never delivered */
static volatile uint32_t ev_txf, ev_txs, ev_rx;    /* DMA buffers finished per port */
static volatile uint32_t bursts;                 /* IEC 61937 data bursts seen (Dolby Digital, DTS) */
static volatile bool bitstream;                  /* input is compressed data, not PCM: outputs held silent */
static volatile float peak_s;                    /* surround signal, full scale = 1.0 */

/* published once a second */
static uint32_t fs_meas;
static float peak_db[3];
static int pot_raw;
static char info[1024];
static bool dd_frames_recent;                    /* Dolby Digital frames decoded in the last second */
static float dd_ms_avg;

const char *netota_app_info(void)
{
    snprintf(info, sizeof info,
             "{\"drive\":%d,\"sound\":\"%s\",\"sweep_hz\":%.0f,\"test\":\"%s\",\"format\":\"%s\",\"fs\":%lu,\"peak_l_db\":%.1f,\"peak_r_db\":%.1f,\"peak_s_db\":%.1f,\"mode\":\"%s\","
             "\"delay_ms\":%d,\"muted\":%s,\"pot\":%d,\"gain\":%.3f,\"read_timeouts\":%lu,\"write_errors\":%lu,"
             "\"tx_underrun_front\":%lu,\"tx_underrun_surr\":%lu,\"rx_overrun\":%lu,\"loop_max_ms\":%.1f,\"dsp_max_ms\":%.2f,\"write_max_ms\":%.1f,\"ev\":[%lu,%lu,%lu,%lu],\"skip\":[%lu,%lu,%lu],"
             "\"dd\":{\"layout\":\"%d/%d.%d\",\"kbps\":%d,\"frames\":%lu,\"errors\":%lu,\"dropped\":%lu,"
             "\"underruns\":%lu,\"decode_ms_avg\":%.1f,\"decode_ms_max\":%.1f,\"ring\":%lu,\"other\":%lu}}",
             drive, sound ? "sweep" : "chime", sweep_hz, TEST_NAMES[test],
             !bitstream ? "pcm" : dd_frames_recent ? "dolby digital" : "bitstream", (unsigned long)fs_meas, peak_db[0], peak_db[1], peak_db[2], MODE_NAMES[mode], DELAY_MS,
             muted ? "true" : "false", pot_raw, gain, (unsigned long)read_timeouts, (unsigned long)write_errors,
             (unsigned long)tx_underrun[0], (unsigned long)tx_underrun[1], (unsigned long)rx_overrun,
             loop_max_us / 1000.0f, dsp_max_us / 1000.0f, wr_max_us / 1000.0f,
             (unsigned long)ev_rx, (unsigned long)ev_txf, (unsigned long)ev_txs, (unsigned long)(frames_in / FRAMES),
             (unsigned long)ev_skip[0], (unsigned long)ev_skip[1], (unsigned long)ev_skip[2],
             dd_front, dd_rear, dd_lfe, dd_kbps, (unsigned long)dd_frames, (unsigned long)dd_errors,
             (unsigned long)dd_dropped, (unsigned long)dd_underrun, dd_ms_avg, dd_dec_us_max / 1000.0f,
             (unsigned long)(ring_wr - ring_rd), (unsigned long)parser.other);
    return info;
}

static bool IRAM_ATTR on_tx_ovf(i2s_chan_handle_t h, i2s_event_data_t *e, void *ctx)
{
    tx_underrun[(int)ctx]++;                 /* the DAC ran out of fresh samples */
    return false;
}
/* Each port's DMA runs round a ring of 6 buffers. Learn the ring order from the first
   events, then count every event whose buffer is not the next one in the ring: that is
   a "buffer finished" event the driver never delivered. */
static void IRAM_ATTR ring_check(int k, void *buf)
{
    static void *ring[3][6];
    static int seen[3], at[3];
    if (seen[k] < 6) { ring[k][seen[k]++] = buf; at[k] = seen[k] % 6; return; }
    if (ring[k][at[k]] != buf) {
        ev_skip[k]++;
        for (int i = 0; i < 6; i++) if (ring[k][i] == buf) at[k] = i;
    }
    at[k] = (at[k] + 1) % 6;
}
static bool IRAM_ATTR on_tx_done(i2s_chan_handle_t h, i2s_event_data_t *e, void *ctx)
{
    if (ctx) { ev_txs++; ring_check(1, e->dma_buf); } else { ev_txf++; ring_check(0, e->dma_buf); }
    return false;
}
static bool IRAM_ATTR on_rx_done(i2s_chan_handle_t h, i2s_event_data_t *e, void *ctx) { ev_rx++; ring_check(2, e->dma_buf); return false; }
static bool IRAM_ATTR on_rx_ovf(i2s_chan_handle_t h, i2s_event_data_t *e, void *ctx)
{
    rx_overrun++;                            /* input samples were dropped */
    return false;
}

void netota_app_set(const char *q)
{
    char v[16];
    if (httpd_query_key_value(q, "test", v, sizeof v) == ESP_OK)
        for (int i = 0; i < TEST_COUNT; i++) if (!strcmp(v, TEST_NAMES[i])) test = i;
    if (httpd_query_key_value(q, "mode", v, sizeof v) == ESP_OK && v[0] >= '0' && v[0] < '0' + MODE_COUNT)
        mode = v[0] - '0';
    if (httpd_query_key_value(q, "mute", v, sizeof v) == ESP_OK) muted = v[0] == '1';
    if (httpd_query_key_value(q, "sound", v, sizeof v) == ESP_OK) sound = !strcmp(v, "sweep");
    if (httpd_query_key_value(q, "drive", v, sizeof v) == ESP_OK && v[0] >= '0' && v[0] <= '3') {
        drive = v[0] - '0';
        gpio_set_drive_capability(PIN_DIN_FRONT, (gpio_drive_cap_t)drive);
        gpio_set_drive_capability(PIN_DIN_SURR, (gpio_drive_cap_t)drive);
    }
}

static void dd_on_block(const int32_t *frames, void *ctx)
{
    uint32_t wr = ring_wr;
    if (RING_FRAMES - (wr - ring_rd) < DD_BLOCK) { dd_dropped++; return; }    /* ring full */
    for (int i = 0; i < DD_BLOCK; i++, wr++)
        memcpy(&ring[(wr % RING_FRAMES) * 4], &frames[4 * i], 16);
    ring_wr = wr;
}

static void dd_task(void *arg)
{
    dd_msg_t m;
    dd_info_t info;
    for (;;) {
        xQueueReceive(dd_q, &m, portMAX_DELAY);
        dd_decoding = m.slot;
        int64_t t = esp_timer_get_time();
        int r = dd_decode(dd_slot[m.slot], m.len, dd_on_block, NULL, &info);
        uint32_t us = esp_timer_get_time() - t;
        dd_decoding = -1;
        if (r) { dd_errors++; continue; }
        dd_frames++;
        if (us > dd_dec_us_max) dd_dec_us_max = us;
        dd_dec_us_sum += us; dd_dec_n++;
        dd_has_surr = info.has_surround;
        dd_front = info.front; dd_rear = info.rear; dd_lfe = info.lfe; dd_kbps = info.bitrate / 1000;
    }
}

/* called by the parser, in the audio task, for each complete AC-3 frame */
static void dd_on_frame(const uint8_t *frame, int len, void *ctx)
{
    static int next;
    if (next == dd_decoding || uxQueueSpacesAvailable(dd_q) == 0) { dd_dropped++; return; }
    memcpy(dd_slot[next], frame, len);
    dd_msg_t m = { next, len };
    xQueueSend(dd_q, &m, 0);
    next ^= 1;
}

/* ---- biquads, transposed direct form II ---- */
typedef struct { float b0, b1, b2, a1, a2, z1, z2; } biquad_t;

static void biquad_set(biquad_t *q, bool highpass, float f, float Q, float fs)
{
    float w = 2.0f * (float)M_PI * f / fs, c = cosf(w), alpha = sinf(w) / (2.0f * Q), a0 = 1.0f + alpha;
    if (highpass) { q->b0 = (1 + c) / 2 / a0; q->b1 = -(1 + c) / a0; q->b2 = q->b0; }
    else          { q->b0 = (1 - c) / 2 / a0; q->b1 = (1 - c) / a0;  q->b2 = q->b0; }
    q->a1 = -2 * c / a0; q->a2 = (1 - alpha) / a0;
    q->z1 = q->z2 = 0;
}

static inline float biquad_run(biquad_t *q, float x)
{
    float y = q->b0 * x + q->z1;
    q->z1 = q->b1 * x - q->a1 * y + q->z2;
    q->z2 = q->b2 * x - q->a2 * y;
    return y;
}

static void audio_task(void *arg)
{
    static int32_t in[FRAMES * 2], front[FRAMES * 2], surr[FRAMES * 2];
    static float delay[DELAY_MAX];
    biquad_t hp, lp1, lp2;
    uint32_t fs_cfg = 0;
    int dlen = 1, dpos = 0;
    size_t got, done;

    int64_t t_prev = esp_timer_get_time();
    for (;;) {
        int64_t t_now = esp_timer_get_time();
        if (t_now - t_prev > loop_max_us) loop_max_us = t_now - t_prev;
        t_prev = t_now;
        if (i2s_channel_read(rx_dir, in, sizeof in, &got, pdMS_TO_TICKS(100)) != ESP_OK) {
            read_timeouts++;
            continue;
        }
        if (fs_cfg != fs_nominal) {                 /* rate changed: new filters, empty delay */
            fs_cfg = fs_nominal;
            biquad_set(&hp, true, HPF_HZ, 0.7071f, fs_cfg);
            biquad_set(&lp1, false, LPF_HZ, 0.5412f, fs_cfg);
            biquad_set(&lp2, false, LPF_HZ, 1.3066f, fs_cfg);
            dlen = fs_cfg * DELAY_MS / 1000;
            memset(delay, 0, sizeof delay);
            dpos = 0;
        }
        int64_t t_dsp = esp_timer_get_time();
        int n = got / 8, m = mode;

        /* Compressed surround (Dolby Digital, DTS) arrives as data bursts that start
           with the words F872 4E1F. Played as PCM it is full-level noise. The parser
           finds the bursts and passes Dolby Digital frames to the decoder task; while
           bursts keep coming (and for a quarter second after) the input is treated as
           data, never as audio, and the outputs play what the decoder has produced. */
        static int hold, dd_wait;
        static bool dd_playing;
        static int32_t dd4[FRAMES * 4];
        int found = dd_parse(&parser, in, n, dd_on_frame, NULL);
        if (found) { bursts += found; hold = fs_cfg / 4; }
        bool bs = hold > 0, direct = false;
        bitstream = bs;
        if (bs) {
            hold -= n;
            uint32_t fill = ring_wr - ring_rd;
            if (!dd_playing && fill >= DD_SAMPLES && ++dd_wait >= DD_START_BLOCKS) dd_playing = true;
            if (dd_playing && fill >= (uint32_t)n) {
                uint32_t rd = ring_rd;
                for (int i = 0; i < n; i++, rd++) memcpy(&dd4[4 * i], &ring[(rd % RING_FRAMES) * 4], 16);
                ring_rd = rd;
                direct = dd_has_surr;
            } else {
                if (dd_playing) { dd_underrun++; dd_playing = false; dd_wait = 0; }
                memset(dd4, 0, sizeof dd4);
            }
            for (int i = 0; i < n; i++) { in[2 * i] = dd4[4 * i]; in[2 * i + 1] = dd4[4 * i + 1]; }
        } else if (dd_playing || ring_wr != ring_rd) {
            dd_playing = false; dd_wait = 0;
            ring_rd = ring_wr;                      /* back to PCM: drop what is left */
        }
        static float g = 0;                         /* glides to the pot's value: no zipper noise */
        float g_target = gain;
        int32_t pl = peak[0], pr = peak[1];
        float ps = peak_s;
        for (int i = 0; i < n; i++) {
            int32_t l = in[2 * i], r = in[2 * i + 1];
            int32_t al = l < 0 ? -(l + 1) : l, ar = r < 0 ? -(r + 1) : r;
            if (al > pl) pl = al;
            if (ar > pr) pr = ar;
            g += (g_target - g) * 0.0005f;
            front[2 * i]     = (int32_t)(l * g);
            front[2 * i + 1] = (int32_t)(r * g);

            /* the matrix chain runs on every stereo source, in every mode, so switching
               modes does not click; with real rear channels it is skipped to leave the
               processor to the Dolby decoder */
            float d = 0;
            if (!direct) {
                float s = ((float)l - (float)r) * (0.5f / 2147483648.0f);
                s = biquad_run(&lp2, biquad_run(&lp1, biquad_run(&hp, s)));
                d = delay[dpos];
                delay[dpos] = s;
                if (++dpos >= dlen) dpos = 0;
            }
            float ad = fabsf(d);

            if (m == MODE_SURROUND && direct) {
                /* Dolby Digital with real rear channels: straight to the rear speakers */
                int32_t sl = dd4[4 * i + 2], sr = dd4[4 * i + 3];
                float asl = fabsf(sl * (1.0f / 2147483648.0f)), asr = fabsf(sr * (1.0f / 2147483648.0f));
                if (asl > ps) ps = asl;
                if (asr > ps) ps = asr;
                surr[2 * i] = (int32_t)(sl * g); surr[2 * i + 1] = (int32_t)(sr * g);
            } else if (m == MODE_SURROUND) {
                if (ad > ps) ps = ad;
                float o = d * g;
                o = o > 0.999f ? 0.999f : o < -0.999f ? -0.999f : o;
                surr[2 * i] = surr[2 * i + 1] = (int32_t)(o * 2147483648.0f);
            } else if (m == MODE_STEREO_ALL) {
                surr[2 * i] = front[2 * i]; surr[2 * i + 1] = front[2 * i + 1];
            } else {
                surr[2 * i] = surr[2 * i + 1] = 0;
            }
        }
        static int prev_test = TEST_OFF;
        if (test != TEST_OFF) {
            /* soft two-note chime, repeating every 1.2 s: 440 Hz at 0 s, 660 Hz at 0.3 s,
               then silence. Each note is a sine plus a quieter second harmonic, with a 5 ms
               attack and an exponential decay (time constant 0.15 s). Peak is -10 dBFS
               times the volume, on the chosen output only. The pattern restarts at the
               first note whenever a new test starts. */
            static float sine[256];
            static bool sine_ready;
            if (!sine_ready) {
                for (int k = 0; k < 256; k++) sine[k] = sinf(6.2831853f * k / 256.0f);
                sine_ready = true;
            }
            static const float freq[2] = { 440.0f, 660.0f };
            static const float start_s[2] = { 0.0f, 0.3f };
            static uint32_t pos, phase[2], inc[2], start_at[2], age[2];
            static float env[2], decay[2];
            static uint32_t period, att;
            int tsel = test;
            if (test != prev_test || period == 0) {
                prev_test = test;
                pos = 0;
                env[0] = env[1] = 0;
                period = (uint32_t)(1.2f * fs_cfg);
                att = (uint32_t)(0.005f * fs_cfg); if (att < 1) att = 1;
                for (int k = 0; k < 2; k++) {
                    inc[k] = (uint32_t)(freq[k] * (4294967296.0f / fs_cfg));
                    start_at[k] = (uint32_t)(start_s[k] * fs_cfg);
                    decay[k] = expf(-1.0f / (0.15f * fs_cfg));
                }
            }
            if (sound) {
                /* slow sine sweep, 100 Hz to 10 kHz in 20 s and round again, at a low
                   level (-26 dBFS times the volume): a damaged driver buzzes or rattles
                   at particular frequencies even when quiet. /status reports the
                   frequency, so the debug page can show where the sweep is. */
                static float f, ratio;
                static uint32_t ph, sw_fs;
                static int sw_test;
                if (sw_test != tsel || sw_fs != fs_cfg || f < 100.0f) {
                    sw_test = tsel; sw_fs = fs_cfg; f = 100.0f; ph = 0;
                    ratio = powf(100.0f, 1.0f / (20.0f * fs_cfg));
                }
                uint32_t inc_s = (uint32_t)(f * (4294967296.0f / fs_cfg));
                for (int i = 0; i < n; i++) {
                    if ((i & 15) == 0) inc_s = (uint32_t)(f * (4294967296.0f / fs_cfg));
                    uint32_t ix = ph >> 24;
                    float fr = (ph & 0xFFFFFF) * (1.0f / 16777216.0f);
                    float sv = sine[ix] + (sine[(ix + 1) & 255] - sine[ix]) * fr;
                    ph += inc_s;
                    f *= ratio;
                    if (f > 10000.0f) f = 100.0f;
                    int32_t v = (int32_t)(sv * 0.05f * g * 2147483648.0f);
                    front[2 * i]     = (tsel == TEST_FL || tsel == TEST_ALL) ? v : 0;
                    front[2 * i + 1] = (tsel == TEST_FR || tsel == TEST_ALL) ? v : 0;
                    surr[2 * i]      = (tsel == TEST_SL || tsel == TEST_ALL) ? v : 0;
                    surr[2 * i + 1]  = (tsel == TEST_SR || tsel == TEST_ALL) ? v : 0;
                }
                sweep_hz = f;
            } else
            for (int i = 0; i < n; i++) {
                float sample = 0;
                for (int k = 0; k < 2; k++) {
                    if (pos == start_at[k]) { env[k] = 1.0f; phase[k] = 0; age[k] = 0; }
                    if (env[k] > 0.0001f) {
                        float a = age[k] < att ? (float)age[k] / (float)att : 1.0f;
                        float tone = sine[phase[k] >> 24] + 0.2f * sine[(phase[k] * 2) >> 24];
                        sample += tone * env[k] * a * (1.0f / 1.2f);
                        env[k] *= decay[k];
                        phase[k] += inc[k];
                        age[k]++;
                    }
                }
                if (++pos >= period) pos = 0;
                int32_t v = (int32_t)(sample * 0.3f * g * 2147483648.0f);
                front[2 * i]     = (tsel == TEST_FL || tsel == TEST_ALL) ? v : 0;
                front[2 * i + 1] = (tsel == TEST_FR || tsel == TEST_ALL) ? v : 0;
                surr[2 * i]      = (tsel == TEST_SL || tsel == TEST_ALL) ? v : 0;
                surr[2 * i + 1]  = (tsel == TEST_SR || tsel == TEST_ALL) ? v : 0;
            }
        } else {
            prev_test = TEST_OFF;
        }
        peak[0] = pl; peak[1] = pr; peak_s = ps;
        frames_in += n;
        int64_t t_wr = esp_timer_get_time();
        if (t_wr - t_dsp > dsp_max_us) dsp_max_us = t_wr - t_dsp;
        if (i2s_channel_write(tx_front, front, n * 8, &done, pdMS_TO_TICKS(100)) != ESP_OK) write_errors++;
        if (i2s_channel_write(tx_surr, surr, n * 8, &done, pdMS_TO_TICKS(100)) != ESP_OK) write_errors++;
        t_wr = esp_timer_get_time() - t_wr;
        if (t_wr > wr_max_us) wr_max_us = t_wr;
    }
}

static void i2s_start(void)
{
    i2s_std_config_t std = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(48000),      /* nominal: the DIR9001 sets the real rate */
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = { .mclk = I2S_GPIO_UNUSED, .bclk = PIN_BCK, .ws = PIN_LRCK,
                      .dout = PIN_DIN_FRONT, .din = PIN_DIR_DATA },
    };
    i2s_chan_config_t c0 = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_SLAVE);
    c0.auto_clear = true;
    ESP_ERROR_CHECK(i2s_new_channel(&c0, &tx_front, &rx_dir));
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(tx_front, &std));
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(rx_dir, &std));

    i2s_chan_config_t c1 = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_1, I2S_ROLE_SLAVE);
    c1.auto_clear = true;
    std.gpio_cfg.dout = PIN_DIN_SURR;
    std.gpio_cfg.din = I2S_GPIO_UNUSED;
    ESP_ERROR_CHECK(i2s_new_channel(&c1, &tx_surr, NULL));
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(tx_surr, &std));

    i2s_event_callbacks_t txcb = { .on_send_q_ovf = on_tx_ovf, .on_sent = on_tx_done }, rxcb = { .on_recv_q_ovf = on_rx_ovf, .on_recv = on_rx_done };
    i2s_channel_register_event_callback(tx_front, &txcb, (void *)0);
    i2s_channel_register_event_callback(tx_surr, &txcb, (void *)1);
    i2s_channel_register_event_callback(rx_dir, &rxcb, NULL);

    /* both ports listen on the same two clock pins; make sure nothing drives them */
    gpio_set_direction(PIN_BCK, GPIO_MODE_INPUT);
    gpio_set_direction(PIN_LRCK, GPIO_MODE_INPUT);

    /* Weakest drive on the two data lines: slower edges, so they disturb the shared
       clock lines less. They only have to drive one DAC input each. */
    gpio_set_drive_capability(PIN_DIN_FRONT, (gpio_drive_cap_t)drive);
    gpio_set_drive_capability(PIN_DIN_SURR, (gpio_drive_cap_t)drive);

    ESP_ERROR_CHECK(i2s_channel_enable(tx_surr));
    ESP_ERROR_CHECK(i2s_channel_enable(tx_front));
    ESP_ERROR_CHECK(i2s_channel_enable(rx_dir));
}

static float to_db(float x)
{
    return x > 1e-7f ? 20.0f * log10f(x) : -140.0f;
}

void app_main(void)
{
    gpio_config_t out = { .pin_bit_mask = (1ULL << PIN_LED) | (1ULL << PIN_XSMT), .mode = GPIO_MODE_OUTPUT };
    gpio_config(&out);
    gpio_set_level(PIN_XSMT, 0);
    gpio_config_t in = { .pin_bit_mask = (1ULL << PIN_BOOT) | (1ULL << PIN_USER),
                         .mode = GPIO_MODE_INPUT, .pull_up_en = GPIO_PULLUP_ENABLE };
    gpio_config(&in);

    adc_oneshot_unit_handle_t adc;
    adc_oneshot_unit_init_cfg_t ucfg = { .unit_id = ADC_UNIT_1 };
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&ucfg, &adc));
    adc_oneshot_chan_cfg_t ccfg = { .atten = ADC_ATTEN_DB_12, .bitwidth = ADC_BITWIDTH_12 };
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc, POT_CHANNEL, &ccfg));

    i2s_start();
    netota_start();
    dd_q = xQueueCreate(1, sizeof(dd_msg_t));
    /* the Dolby decoder alone on core 1 */
    xTaskCreatePinnedToCore(dd_task, "dolby", 8192, NULL, 9, NULL, 1);
    /* audio in and out on core 0 (5 ms blocks, light), so the decoder has core 1 to itself */
    xTaskCreatePinnedToCore(audio_task, "audio", 4096, NULL, 10, NULL, 0);
    ESP_LOGI(TAG, "surround running: clocks from the DIR9001 on BCK %d LRCK %d, data in %d",
             PIN_BCK, PIN_LRCK, PIN_DIR_DATA);

    static const uint32_t RATES[] = { 32000, 44100, 48000, 88200, 96000 };
    bool user_was = false, boot_was = false;
    uint32_t f0 = 0;
    int64_t t0 = esp_timer_get_time();
    for (int ticks = 0;; ticks++) {
        bool boot = !gpio_get_level(PIN_BOOT), user = !gpio_get_level(PIN_USER);
        if (user && !user_was) muted = !muted;
        if (boot && !boot_was) mode = (mode + 1) % MODE_COUNT;
        user_was = user; boot_was = boot;

        adc_oneshot_read(adc, POT_CHANNEL, &pot_raw);
        /* pot on J7: smoothed, square law so the middle of the turn is about -12 dB,
           silent at the bottom stop and full level at the top */
        static float pot_f = -1;
        static float pot_used = -1000;
        pot_f = pot_f < 0 ? pot_raw : pot_f + 0.2f * (pot_raw - pot_f);
        if (fabsf(pot_f - pot_used) > 16) pot_used = pot_f;   /* dead band: ADC noise must not move the volume */
        float x = (pot_used - 60.0f) / (3950.0f - 60.0f);
        x = x < 0 ? 0 : x > 1 ? 1 : x;
        gain = muted ? 0.0f : x * x;         /* mute in the data too: it works even if a
                                                DAC module still has its own XSMT strap */

        bool clocked = fs_meas > 8000;
        gpio_set_level(PIN_XSMT, clocked);         /* never pulled low against a strapped module while playing */
        gpio_set_level(PIN_LED, muted ? (ticks / 10) % 2 : clocked ? 1 : (ticks / 2) % 2);

        if (ticks % 20 == 19) {
            int64_t t = esp_timer_get_time();
            uint32_t f = frames_in;
            fs_meas = (uint32_t)((uint64_t)(f - f0) * 1000000 / (t - t0));
            f0 = f; t0 = t;
            for (int i = 0; i < 5; i++)
                if (fabsf((float)fs_meas - RATES[i]) < 0.02f * RATES[i]) fs_nominal = RATES[i];
            peak_db[0] = to_db(peak[0] / 2147483648.0f);
            peak_db[1] = to_db(peak[1] / 2147483648.0f);
            peak_db[2] = to_db(peak_s);
            peak[0] = peak[1] = 0; peak_s = 0;
            static uint32_t dd_prev;
            dd_frames_recent = dd_frames != dd_prev; dd_prev = dd_frames;
            if (dd_dec_n) { dd_ms_avg = dd_dec_us_sum / (float)dd_dec_n / 1000.0f; dd_dec_us_sum = 0; dd_dec_n = 0; }
            if (ticks % 200 == 199) loop_max_us = dsp_max_us = wr_max_us = 0;   /* worst case over 10 s */
            printf("fs=%lu mode=%s peak L=%.1f R=%.1f S=%.1f dBFS pot=%d gain=%.3f muted=%d rd_to=%lu wr_err=%lu ip=%s\n",
                   (unsigned long)fs_meas, MODE_NAMES[mode], peak_db[0], peak_db[1], peak_db[2], pot_raw, gain,
                   muted, (unsigned long)read_timeouts, (unsigned long)write_errors, netota_ip());
        }
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}
