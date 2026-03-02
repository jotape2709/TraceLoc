/*
 * libaddressgeo.c - High-performance geocoding engine
 * Compile: gcc -shared -O3 -fPIC libaddressgeo.c -o libaddressgeo.so -lcurl
 */

#include <curl/curl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    char *memory;
    size_t size;
} MemoryBuffer;

static size_t write_callback(void *contents, size_t size, size_t nmemb, void *userp) {
    size_t total = size * nmemb;
    MemoryBuffer *buffer = (MemoryBuffer *)userp;

    char *ptr = realloc(buffer->memory, buffer->size + total + 1);
    if (!ptr) {
        return 0;
    }

    buffer->memory = ptr;
    memcpy(buffer->memory + buffer->size, contents, total);
    buffer->size += total;
    buffer->memory[buffer->size] = '\0';
    return total;
}

static char *http_get(const char *url) {
    CURL *curl = curl_easy_init();
    if (!curl) {
        return NULL;
    }

    MemoryBuffer buffer;
    buffer.memory = malloc(1);
    buffer.size = 0;

    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, (void *)&buffer);
    curl_easy_setopt(curl, CURLOPT_USERAGENT, "TraceLoc/1.0");
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 10L);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);

    CURLcode res = curl_easy_perform(curl);
    if (res != CURLE_OK) {
        free(buffer.memory);
        buffer.memory = NULL;
    }

    curl_easy_cleanup(curl);
    return buffer.memory;
}

static char *json_escape(const char *input) {
    if (!input) {
        return strdup("");
    }

    size_t len = strlen(input);
    char *out = malloc((len * 2) + 1);
    if (!out) {
        return NULL;
    }

    size_t j = 0;
    for (size_t i = 0; i < len; i++) {
        char c = input[i];
        if (c == '\\' || c == '"') {
            out[j++] = '\\';
            out[j++] = c;
        } else if (c == '\n' || c == '\r' || c == '\t') {
            out[j++] = ' ';
        } else {
            out[j++] = c;
        }
    }
    out[j] = '\0';
    return out;
}

static int extract_json_string(const char *json, const char *key, char *out, size_t out_size) {
    char marker[64];
    snprintf(marker, sizeof(marker), "\"%s\":", key);

    char *pos = strstr((char *)json, marker);
    if (!pos) {
        return 0;
    }

    pos += strlen(marker);
    while (*pos == ' ' || *pos == '\n') {
        pos++;
    }

    if (*pos != '"') {
        return 0;
    }

    pos++;
    size_t i = 0;
    while (*pos && *pos != '"' && i < out_size - 1) {
        if (*pos == '\\' && *(pos + 1) != '\0') {
            pos++;
        }
        out[i++] = *pos++;
    }
    out[i] = '\0';
    return i > 0;
}

static int extract_json_number(const char *json, const char *key, double *out) {
    char marker[64];
    snprintf(marker, sizeof(marker), "\"%s\":", key);

    char *pos = strstr((char *)json, marker);
    if (!pos) {
        return 0;
    }

    pos += strlen(marker);
    while (*pos == ' ' || *pos == '\n') {
        pos++;
    }

    *out = strtod(pos, NULL);
    return 1;
}

const char *geocode_address(const char *address, const char *provider) {
    if (!address || !provider || strcmp(provider, "osm") != 0) {
        return strdup("{\"error\":\"Unsupported provider\"}");
    }

    CURL *tmp = curl_easy_init();
    if (!tmp) {
        return strdup("{\"error\":\"curl init failed\"}");
    }

    char *encoded = curl_easy_escape(tmp, address, 0);
    if (!encoded) {
        curl_easy_cleanup(tmp);
        return strdup("{\"error\":\"address encoding failed\"}");
    }

    char url[2048];
    snprintf(url,
             sizeof(url),
             "https://nominatim.openstreetmap.org/search?q=%s&format=json&addressdetails=1&limit=1",
             encoded);

    curl_free(encoded);
    curl_easy_cleanup(tmp);

    char *response = http_get(url);
    if (!response) {
        return strdup("{\"error\":\"request failed\"}");
    }

    if (strncmp(response, "[]", 2) == 0) {
        free(response);
        return strdup("{\"error\":\"No results found\"}");
    }

    char lat_str[64] = {0};
    char lon_str[64] = {0};
    char display_name[1024] = {0};
    double importance = 0.0;

    extract_json_string(response, "lat", lat_str, sizeof(lat_str));
    extract_json_string(response, "lon", lon_str, sizeof(lon_str));
    extract_json_string(response, "display_name", display_name, sizeof(display_name));
    extract_json_number(response, "importance", &importance);

    char *escaped_display = json_escape(display_name);
    if (!escaped_display) {
        free(response);
        return strdup("{\"error\":\"memory allocation failed\"}");
    }

    char result[2048];
    snprintf(result,
             sizeof(result),
             "{\"lat\":%s,\"lon\":%s,\"display_name\":\"%s\",\"confidence\":%.6f,\"provider\":\"osm\"}",
             lat_str[0] ? lat_str : "0",
             lon_str[0] ? lon_str : "0",
             escaped_display,
             importance);

    free(escaped_display);
    free(response);
    return strdup(result);
}

void free_result(const char *result) {
    if (result) {
        free((void *)result);
    }
}
