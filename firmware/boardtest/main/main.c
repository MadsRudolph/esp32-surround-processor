/* Board test for the surround carrier, without the DIR9001.
 *
 * The ESP32 makes the clocks itself (48 kHz, 64 fs) on the pins that the DIR9001
 * will drive later, and plays a 1 kHz tone on one output at a time:
 * front L, front R, surround L, surround R, 2 s each.
 *
 *   BOOT held  : tone on all four outputs
 *   USER press : mute / unmute (XSMT)
 *   pot        : level, up to -6 dBFS at the top; with no pot fitted, -12 dBFS
 *   status LED : on while a tone plays, blinks slowly when muted
 *
 * I2S0 is master on BCK/LRCK and feeds the front DAC. I2S1 is a slave on the
 * same two pins and feeds the surround DAC, which is how the real firmware
 * will hang both ports on the DIR9001's clocks.
 */
#include <math.h>
#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "driver/i2s_std.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_log.h"
#include "netota.h"

#define PIN_BCK       14
#define PIN_LRCK      26
#define PIN_DIN_FRONT 2
#define PIN_DIN_SURR  13
#define PIN_XSMT      21
#define PIN_LED       17
#define PIN_BOOT      0
#define PIN_USER      15
#define POT_CHANNEL   ADC_CHANNEL_5          /* IO33 */

#define FS      48000
#define TONE_HZ 1000
#define FRAMES  240                          /* 5 ms, whole periods of 1 kHz */

static const char *TAG = "boardtest";
static const char *NAMES[] = {"FRONT L", "FRONT R", "SURR L", "SURR R"};

static i2s_chan_handle_t tx_front, tx_surr;
static volatile int active = 0;              /* 0..3, or 4 = all */
static volatile float level = 0.25f;
static int32_t sine[FRAMES];

/* One task per port, so a port that stalls cannot starve the other. */
static volatile uint32_t written[2], timeouts[2];

static void audio_task(void *arg)
{
    int port = (int)arg;                     /* 0 = front, 1 = surround */
    i2s_chan_handle_t tx = port ? tx_surr : tx_front;
    static int32_t bufs[2][FRAMES * 2];
    int32_t *buf = bufs[port];
    size_t done;
    for (;;) {
        int a = active;
        float g = level;
        for (int i = 0; i < FRAMES; i++) {
            int32_t s = (int32_t)(sine[i] * g);
            buf[2 * i]     = (a == 2 * port     || a == 4) ? s : 0;
            buf[2 * i + 1] = (a == 2 * port + 1 || a == 4) ? s : 0;
        }
        if (i2s_channel_write(tx, buf, sizeof bufs[0], &done, pdMS_TO_TICKS(200)) != ESP_OK)
            timeouts[port]++;
        written[port] += done / 8;
    }
}

static void i2s_start(void)
{
    i2s_std_config_t std = {
        .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(FS),
        .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_STEREO),
        .gpio_cfg = { .mclk = I2S_GPIO_UNUSED, .bclk = PIN_BCK, .ws = PIN_LRCK,
                      .dout = PIN_DIN_SURR, .din = I2S_GPIO_UNUSED },
    };
    /* slave first: it takes the two clock pins as inputs */
    i2s_chan_config_t c1 = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_1, I2S_ROLE_SLAVE);
    c1.auto_clear = true;
    ESP_ERROR_CHECK(i2s_new_channel(&c1, &tx_surr, NULL));
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(tx_surr, &std));

    /* then the master drives the same pins; switch their input buffers back on
       so the slave still sees them */
    i2s_chan_config_t c0 = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
    c0.auto_clear = true;
    std.gpio_cfg.dout = PIN_DIN_FRONT;
    ESP_ERROR_CHECK(i2s_new_channel(&c0, &tx_front, NULL));
    ESP_ERROR_CHECK(i2s_channel_init_std_mode(tx_front, &std));
    gpio_input_enable(PIN_BCK);
    gpio_input_enable(PIN_LRCK);

    ESP_ERROR_CHECK(i2s_channel_enable(tx_surr));
    ESP_ERROR_CHECK(i2s_channel_enable(tx_front));
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

    for (int i = 0; i < FRAMES; i++)
        sine[i] = (int32_t)(2147483647.0 * sin(2.0 * M_PI * TONE_HZ * i / FS));

    i2s_start();
    netota_start();                          /* Wi-Fi and over-the-air updates */
    xTaskCreatePinnedToCore(audio_task, "front", 4096, (void *)0, 10, NULL, 1);
    xTaskCreatePinnedToCore(audio_task, "surr", 4096, (void *)1, 10, NULL, 1);
    vTaskDelay(pdMS_TO_TICKS(300));
    gpio_set_level(PIN_XSMT, 1);
    ESP_LOGI(TAG, "board test running: 1 kHz, 48 kHz, BCK %d LRCK %d", PIN_BCK, PIN_LRCK);

    bool muted = false, user_was = false;
    int step = 0, ticks = 0;
    for (;;) {
        bool boot = !gpio_get_level(PIN_BOOT), user = !gpio_get_level(PIN_USER);
        if (user && !user_was) {
            muted = !muted;
            gpio_set_level(PIN_XSMT, !muted);
        }
        user_was = user;

        int raw = 0;
        adc_oneshot_read(adc, POT_CHANNEL, &raw);
        /* an open pot input floats between 0 and about 100 counts: below 400, play at
           a fixed -12 dBFS so the outputs can be measured */
        level = raw < 400 ? 0.25f : 0.5f * raw / 4095.0f;

        if (ticks % 40 == 0 && !boot) step = (ticks / 40) % 4;
        active = boot ? 4 : step;
        gpio_set_level(PIN_LED, muted ? (ticks / 10) % 2 : 1);

        if (ticks % 10 == 0)
        {
            static uint32_t w0, w1;
            uint32_t a0 = written[0], a1 = written[1];
            printf("out=%-7s pot=%4d level=%.2f boot=%d user=%d muted=%d  frames/s front=%lu surr=%lu timeouts=%lu/%lu ip=%s\n",
                   boot ? "ALL" : NAMES[step], raw, level, boot, user, muted,
                   (unsigned long)(a0 - w0) * 2, (unsigned long)(a1 - w1) * 2,
                   (unsigned long)timeouts[0], (unsigned long)timeouts[1], netota_ip());
            w0 = a0; w1 = a1;
        }
        ticks++;
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}
