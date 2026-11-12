#pragma once
#include <stdbool.h>

/* Wi-Fi station plus a small HTTP server for over-the-air updates.
 *
 *   GET  /status   -> JSON: project, version, running partition, uptime
 *   POST /update   -> body is the app .bin; header X-OTA-Token must match
 *   POST /reboot   -> restart (same token)
 *
 * A new image is only kept if it gets an IP address within a minute of its
 * first boot; otherwise the bootloader goes back to the previous one.
 * Credentials come from firmware/wifi_secrets.h, which is not in git.
 */
void netota_start(void);
bool netota_connected(void);
const char *netota_ip(void);

/* Optional: define this in the app to add a JSON object under "app" in /status. */
const char *netota_app_info(void);

/* Optional: define this in the app to take settings from GET /set?key=value&...
   (no token: keep it to harmless things such as a test tone or a mode). */
void netota_app_set(const char *query);
