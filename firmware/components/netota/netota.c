#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_app_desc.h"
#include "esp_event.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_netif.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_wifi.h"
#include "nvs_flash.h"
#include "netota.h"
#include "wifi_secrets.h"

static const char *TAG = "netota";
static volatile bool connected;
static char ip_str[16] = "0.0.0.0";
static bool pending_verify;

bool netota_connected(void) { return connected; }
const char *netota_ip(void) { return ip_str; }

static void on_event(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        connected = false;
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *e = data;
        snprintf(ip_str, sizeof ip_str, IPSTR, IP2STR(&e->ip_info.ip));
        connected = true;
        ESP_LOGI(TAG, "connected, ip %s", ip_str);
        if (pending_verify) {
            esp_ota_mark_app_valid_cancel_rollback();
            pending_verify = false;
            ESP_LOGI(TAG, "new image confirmed");
        }
    }
}

static bool token_ok(httpd_req_t *req)
{
    char tok[80] = "";
    httpd_req_get_hdr_value_str(req, "X-OTA-Token", tok, sizeof tok);
    if (strcmp(tok, OTA_TOKEN) == 0) return true;
    httpd_resp_send_err(req, HTTPD_401_UNAUTHORIZED, "bad token\n");
    return false;
}

/* The app may define this to add its own JSON object to /status. */
__attribute__((weak)) const char *netota_app_info(void) { return "{}"; }

static esp_err_t status_get(httpd_req_t *req)
{
    const esp_app_desc_t *d = esp_app_get_description();
    const esp_partition_t *p = esp_ota_get_running_partition();
    char buf[1400];
    int n = snprintf(buf, sizeof buf,
        "{\"project\":\"%s\",\"version\":\"%s\",\"built\":\"%s %s\",\"partition\":\"%s\","
        "\"uptime_s\":%lld,\"heap\":%lu,\"app\":%s}\n",
        d->project_name, d->version, d->date, d->time, p->label,
        esp_timer_get_time() / 1000000, (unsigned long)esp_get_free_heap_size(), netota_app_info());
    httpd_resp_set_type(req, "application/json");
    return httpd_resp_send(req, buf, n);
}

/* The app may define this to take settings from GET /set?key=value&... */
__attribute__((weak)) void netota_app_set(const char *query) { }

static esp_err_t set_get(httpd_req_t *req)
{
    char q[160] = "";
    httpd_req_get_url_query_str(req, q, sizeof q);
    netota_app_set(q);
    return status_get(req);
}

static void reboot_task(void *arg)
{
    vTaskDelay(pdMS_TO_TICKS(500));
    esp_restart();
}

static esp_err_t update_post(httpd_req_t *req)
{
    if (!token_ok(req)) return ESP_OK;
    const esp_partition_t *part = esp_ota_get_next_update_partition(NULL);
    esp_ota_handle_t h;
    if (!part || esp_ota_begin(part, OTA_SIZE_UNKNOWN, &h) != ESP_OK)
        return httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "ota begin failed\n");
    static char buf[4096];
    int left = req->content_len, total = 0;
    while (left > 0) {
        int n = httpd_req_recv(req, buf, left < (int)sizeof buf ? left : (int)sizeof buf);
        if (n == HTTPD_SOCK_ERR_TIMEOUT) continue;
        if (n <= 0 || esp_ota_write(h, buf, n) != ESP_OK) {
            esp_ota_abort(h);
            return httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "ota write failed\n");
        }
        left -= n; total += n;
    }
    esp_err_t e = esp_ota_end(h);
    if (e == ESP_OK) e = esp_ota_set_boot_partition(part);
    if (e != ESP_OK)
        return httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "image rejected\n");
    ESP_LOGI(TAG, "wrote %d bytes to %s, restarting", total, part->label);
    char msg[80];
    int n = snprintf(msg, sizeof msg, "ok %d bytes to %s, restarting\n", total, part->label);
    httpd_resp_send(req, msg, n);
    xTaskCreate(reboot_task, "reboot", 2048, NULL, 5, NULL);
    return ESP_OK;
}

static esp_err_t reboot_post(httpd_req_t *req)
{
    if (!token_ok(req)) return ESP_OK;
    httpd_resp_sendstr(req, "restarting\n");
    xTaskCreate(reboot_task, "reboot", 2048, NULL, 5, NULL);
    return ESP_OK;
}

static void verify_task(void *arg)
{
    vTaskDelay(pdMS_TO_TICKS(60000));
    if (pending_verify) {
        ESP_LOGE(TAG, "no network after 60 s on a new image: going back to the previous one");
        esp_ota_mark_app_invalid_rollback_and_reboot();
    }
    vTaskDelete(NULL);
}

void netota_start(void)
{
    esp_err_t e = nvs_flash_init();
    if (e == ESP_ERR_NVS_NO_FREE_PAGES || e == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        nvs_flash_erase();
        nvs_flash_init();
    }
    esp_ota_img_states_t st;
    if (esp_ota_get_state_partition(esp_ota_get_running_partition(), &st) == ESP_OK
        && st == ESP_OTA_IMG_PENDING_VERIFY) {
        pending_verify = true;
        xTaskCreate(verify_task, "verify", 3072, NULL, 3, NULL);
    }

    esp_netif_init();
    esp_event_loop_create_default();
    esp_netif_t *nif = esp_netif_create_default_wifi_sta();
    esp_netif_set_hostname(nif, OTA_HOSTNAME);
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    esp_wifi_init(&cfg);
    esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, on_event, NULL);
    esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, on_event, NULL);
    wifi_config_t wc = { 0 };
    strlcpy((char *)wc.sta.ssid, WIFI_SSID, sizeof wc.sta.ssid);
    strlcpy((char *)wc.sta.password, WIFI_PASSWORD, sizeof wc.sta.password);
    esp_wifi_set_mode(WIFI_MODE_STA);
    esp_wifi_set_config(WIFI_IF_STA, &wc);
    esp_wifi_start();

    httpd_handle_t srv;
    httpd_config_t hc = HTTPD_DEFAULT_CONFIG();
    hc.recv_wait_timeout = 15;
    if (httpd_start(&srv, &hc) == ESP_OK) {
        httpd_uri_t u1 = { .uri = "/status", .method = HTTP_GET, .handler = status_get };
        httpd_uri_t u2 = { .uri = "/update", .method = HTTP_POST, .handler = update_post };
        httpd_uri_t u3 = { .uri = "/reboot", .method = HTTP_POST, .handler = reboot_post };
        httpd_register_uri_handler(srv, &u1);
        httpd_register_uri_handler(srv, &u2);
        httpd_register_uri_handler(srv, &u3);
        httpd_uri_t u4 = { .uri = "/set", .method = HTTP_GET, .handler = set_get };
        httpd_register_uri_handler(srv, &u4);
    }
}
