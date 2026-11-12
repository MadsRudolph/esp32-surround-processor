/* Passthrough test for the surround carrier with the DIR9001 fitted.
 *
 * The DIR9001 makes BCK and LRCK. The ESP32 drives neither: both I2S ports are
 * slaves on those two pins. I2S0 reads the DIR9001's data (IO35) and sends it
 * to the front DAC; I2S1 sends the same stereo pair to the surround DAC.
 *
 *   USER press : mute / unmute (XSMT)
 *   BOOT held  : front only (surround silent), to tell the two DACs apart
 *   pot        : volume (J7), silent at the bottom stop
 *   status LED : on while samples arrive, fast blink with no clock, slow blink when muted
 *
 * GET /status shows the measured sample rate and the peak level of each channel.
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
#include "netota.h"

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

#define FRAMES 240

static const char *TAG = "passthrough";

static i2s_chan_handle_t tx_front, rx_dir, tx_surr;
static volatile float gain = 1.0f;
static volatile bool front_only;

/* written by the audio task, read once a second by the main loop */
static volatile uint32_t frames_in, read_timeouts, write_errors;
static volatile int32_t peak[2];

/* published once a second */
static uint32_t fs_meas;
static float peak_db[2];
static bool muted;
static int pot_raw;
static char info[200];

const char *netota_app_info(void)
{
    snprintf(info, sizeof info,
             "{\"fs\":%lu,\"peak_l_db\":%.1f,\"peak_r_db\":%.1f,\"muted\":%s,\"pot\":%d,"
             "\"gain\":%.2f,\"read_timeouts\":%lu,\"write_errors\":%lu}",
             (unsigned long)fs_meas, peak_db[0], peak_db[1], muted ? "true" : "false", pot_raw,
             gain, (unsigned long)read_timeouts, (unsigned long)write_errors);
    return info;
}

static void audio_task(void *arg)
{
    static int32_t in[FRAMES * 2], out[FRAMES * 2], zero[FRAMES * 2];
    size_t got, done;
    for (;;) {
        if (i2s_channel_read(rx_dir, in, sizeof in, &got, pdMS_TO_TICKS(100)) != ESP_OK) {
            read_timeouts++;
            continue;
        }
        int n = got / 8;
        float g = gain;
        int32_t pl = peak[0], pr = peak[1];
        for (int i = 0; i < n; i++) {
            int32_t l = in[2 * i], r = in[2 * i + 1];
            int32_t al = l < 0 ? -(l + 1) : l, ar = r < 0 ? -(r + 1) : r;
            if (al > pl) pl = al;
            if (ar > pr) pr = ar;
            out[2 * i]     = g >= 0.999f ? l : (int32_t)(l * g);
            out[2 * i + 1] = g >= 0.999f ? r : (int32_t)(r * g);
        }
        peak[0] = pl; peak[1] = pr;
        frames_in += n;
        if (i2s_channel_write(tx_front, out, n * 8, &done, pdMS_TO_TICKS(100)) != ESP_OK) write_errors++;
        if (i2s_channel_write(tx_surr, front_only ? zero : out, n * 8, &done, pdMS_TO_TICKS(100)) != ESP_OK) write_errors++;
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

    /* both ports listen on the same two clock pins; make sure nothing drives them */
    gpio_set_direction(PIN_BCK, GPIO_MODE_INPUT);
    gpio_set_direction(PIN_LRCK, GPIO_MODE_INPUT);

    ESP_ERROR_CHECK(i2s_channel_enable(tx_surr));
    ESP_ERROR_CHECK(i2s_channel_enable(tx_front));
    ESP_ERROR_CHECK(i2s_channel_enable(rx_dir));
}

static float to_db(int32_t p)
{
    return p > 0 ? 20.0f * log10f(p / 2147483648.0f) : -140.0f;
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
    xTaskCreatePinnedToCore(audio_task, "audio", 4096, NULL, 10, NULL, 1);
    ESP_LOGI(TAG, "passthrough running: clocks from the DIR9001 on BCK %d LRCK %d, data in %d",
             PIN_BCK, PIN_LRCK, PIN_DIR_DATA);

    bool user_was = false;
    uint32_t f0 = 0;
    int64_t t0 = esp_timer_get_time();
    for (int ticks = 0;; ticks++) {
        bool boot = !gpio_get_level(PIN_BOOT), user = !gpio_get_level(PIN_USER);
        if (user && !user_was) muted = !muted;
        user_was = user;
        front_only = boot;

        adc_oneshot_read(adc, POT_CHANNEL, &pot_raw);
        /* pot on J7: smoothed, square law so the middle of the turn is about -12 dB,
           silent at the bottom stop and full level at the top */
        static float pot_f = -1;
        pot_f = pot_f < 0 ? pot_raw : pot_f + 0.2f * (pot_raw - pot_f);
        float x = (pot_f - 60.0f) / (3950.0f - 60.0f);
        x = x < 0 ? 0 : x > 1 ? 1 : x;
        gain = x * x;

        bool clocked = fs_meas > 8000;
        gpio_set_level(PIN_XSMT, clocked && !muted);
        gpio_set_level(PIN_LED, muted ? (ticks / 10) % 2 : clocked ? 1 : (ticks / 2) % 2);

        if (ticks % 20 == 19) {
            int64_t t = esp_timer_get_time();
            uint32_t f = frames_in;
            fs_meas = (uint32_t)((uint64_t)(f - f0) * 1000000 / (t - t0));
            f0 = f; t0 = t;
            peak_db[0] = to_db(peak[0]); peak_db[1] = to_db(peak[1]);
            peak[0] = peak[1] = 0;
            printf("fs=%lu peak L=%.1f R=%.1f dBFS pot=%d gain=%.2f muted=%d front_only=%d rd_to=%lu wr_err=%lu ip=%s\n",
                   (unsigned long)fs_meas, peak_db[0], peak_db[1], pot_raw, gain, muted, boot,
                   (unsigned long)read_timeouts, (unsigned long)write_errors, netota_ip());
        }
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}
