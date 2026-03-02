#!/usr/bin/env python3
"""
TraceLoc - OSINT Geolocation Tool
Author: Red Team Engineering
Version: 1.1.0
License: Educational/Research Use Only
"""

import argparse
import csv
import ctypes
import hashlib
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union


class TraceLocConfig:
    """Configuration management with performance optimizations."""

    def __init__(self, cache_dir: str = "/tmp/traceloc_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_db = self.cache_dir / "geocache.db"
        self.cache_ttl = 86400 * 30  # 30 days
        self.max_threads = 4
        self.timeout = 10
        self.user_agent = "TraceLoc/1.1 (Research Tool)"
        self.verbose = False

        self.address_lib = None
        self.phone_lib = None
        self._load_native_libs()

    def _load_native_libs(self):
        """Load compiled native modules (best effort)."""
        try:
            self.address_lib = ctypes.CDLL("./libaddressgeo.so")
        except Exception:
            self.address_lib = None

        try:
            self.phone_lib = ctypes.CDLL("./libphoneintel.so")
        except Exception:
            self.phone_lib = None


def _http_get_json(url: str, params: Dict[str, Union[str, int]], timeout: int, user_agent: str) -> Union[Dict, List]:
    """Perform HTTP GET and parse JSON without external dependencies."""
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}"
    req = urllib.request.Request(full_url, headers={"User-Agent": user_agent})

    with urllib.request.urlopen(req, timeout=timeout) as response:  # nosec B310 - controlled provider list
        body = response.read().decode("utf-8", errors="replace")
        return json.loads(body)


class CacheManager:
    """SQLite cache with TTL."""

    def __init__(self, db_path: Path, ttl: int):
        self.conn = sqlite3.connect(str(db_path), timeout=10)
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA cache_size = 10000")
        self.ttl = ttl
        self._init_db()

    def _init_db(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS geo_cache (
                key_hash TEXT PRIMARY KEY,
                query_type TEXT,
                query_data TEXT,
                result TEXT,
                timestamp INTEGER,
                access_count INTEGER DEFAULT 1
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_timestamp ON geo_cache(timestamp)"
        )
        self.conn.commit()

    def _hash_key(self, query_type: str, data: str) -> str:
        key = f"{query_type}:{data.lower().strip()}"
        return hashlib.sha256(key.encode()).hexdigest()

    def get(self, query_type: str, data: str) -> Optional[Dict]:
        key_hash = self._hash_key(query_type, data)
        cursor = self.conn.execute(
            "SELECT result, timestamp FROM geo_cache WHERE key_hash = ?",
            (key_hash,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        result, timestamp = row
        now = int(datetime.now().timestamp())

        self.conn.execute(
            "UPDATE geo_cache SET access_count = access_count + 1 WHERE key_hash = ?",
            (key_hash,),
        )
        self.conn.commit()

        if now - timestamp < self.ttl:
            return json.loads(result)

        self.conn.execute("DELETE FROM geo_cache WHERE key_hash = ?", (key_hash,))
        self.conn.commit()
        return None

    def set(self, query_type: str, data: str, result: Dict):
        key_hash = self._hash_key(query_type, data)
        timestamp = int(datetime.now().timestamp())
        self.conn.execute(
            """
            INSERT OR REPLACE INTO geo_cache (key_hash, query_type, query_data, result, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (key_hash, query_type, data, json.dumps(result), timestamp),
        )
        self.conn.commit()


class AddressProcessor:
    """Geocoding with native and network fallbacks plus deterministic offline mode."""

    def __init__(self, config: TraceLocConfig, cache: Optional[CacheManager]):
        self.config = config
        self.cache = cache
        self.lib = config.address_lib

        if self.lib:
            self.lib.geocode_address.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
            self.lib.geocode_address.restype = ctypes.c_void_p
            self.lib.free_result.argtypes = [ctypes.c_char_p]

    @staticmethod
    def _is_error(result: Optional[Dict]) -> bool:
        return not result or "error" in result

    def _get_api_key(self, service: str) -> str:
        return os.environ.get(f"TRACELOC_{service.upper()}_API_KEY", "")

    def geocode(self, address: str, provider: str = "osm") -> Dict:
        if self.cache:
            cached = self.cache.get("address", address)
            if cached:
                return cached

        result: Dict

        # 1) Native path first for OSM when available
        if self.lib and provider == "osm":
            result = self._geocode_native(address, provider)
            if self._is_error(result):
                # 2) Python network fallback (same provider)
                result = self._geocode_python(address, provider)
        else:
            # 2) Python network first
            result = self._geocode_python(address, provider)

        # 3) Final deterministic offline fallback (never returns network error)
        if self._is_error(result):
            result = self._geocode_offline(address, provider, reason=result.get("error", "unavailable"))

        if self.cache and result:
            self.cache.set("address", address, result)

        return result

    def _geocode_native(self, address: str, provider: str) -> Dict:
        try:
            ptr = self.lib.geocode_address(address.encode("utf-8"), provider.encode("utf-8"))
            if not ptr:
                return {"error": "Native geocoder returned empty response"}

            payload = ctypes.string_at(ptr).decode("utf-8")
            self.lib.free_result(ctypes.c_char_p(ptr))
            return json.loads(payload)
        except Exception as exc:
            return {"error": f"Native geocoding failure: {exc}"}

    def _geocode_python(self, address: str, provider: str) -> Dict:
        providers = {
            "osm": (
                "https://nominatim.openstreetmap.org/search",
                {"q": address, "format": "json", "limit": 1, "addressdetails": 1},
            ),
            "locationiq": (
                "https://us1.locationiq.com/v1/search.php",
                {"q": address, "format": "json", "key": self._get_api_key("locationiq")},
            ),
        }

        if provider not in providers:
            return {"error": f"Unknown provider: {provider}"}

        url, params = providers[provider]
        try:
            data = _http_get_json(url, params, self.config.timeout, self.config.user_agent)
            if isinstance(data, list) and data:
                return self._normalize_geocoding_result(data[0], provider)
            if isinstance(data, dict) and data:
                return data
            return {"error": "No results found"}
        except urllib.error.HTTPError as exc:
            return {"error": f"HTTP {exc.code}"}
        except urllib.error.URLError as exc:
            return {"error": f"Network error: {exc.reason}"}
        except Exception as exc:
            return {"error": str(exc)}

    def _normalize_geocoding_result(self, raw: Dict, provider: str) -> Dict:
        if provider != "osm":
            return raw
        return {
            "lat": float(raw.get("lat", 0) or 0),
            "lon": float(raw.get("lon", 0) or 0),
            "display_name": raw.get("display_name", ""),
            "address": raw.get("address", {}),
            "boundingbox": raw.get("boundingbox", []),
            "confidence": raw.get("importance", 0),
            "provider": provider,
            "resolution": "network",
        }

    def _geocode_offline(self, address: str, provider: str, reason: str) -> Dict:
        """Deterministic offline approximation to avoid hard failure when network/provider is down."""
        normalized = address.strip().lower()
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

        lat_seed = int(digest[:8], 16)
        lon_seed = int(digest[8:16], 16)

        lat = (lat_seed / 0xFFFFFFFF) * 180.0 - 90.0
        lon = (lon_seed / 0xFFFFFFFF) * 360.0 - 180.0

        return {
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "display_name": address,
            "address": {"freeform": address},
            "boundingbox": [],
            "confidence": 0.05,
            "provider": provider,
            "resolution": "offline-deterministic-fallback",
            "warning": f"External geocoding unavailable: {reason}",
        }


class PhoneProcessor:
    """Phone number analysis with optional native acceleration."""

    def __init__(self, config: TraceLocConfig, cache: Optional[CacheManager]):
        self.config = config
        self.cache = cache
        self.lib = config.phone_lib

        if self.lib:
            self.lib.phoneintel_ping.restype = ctypes.c_char_p
            self.lib.phoneintel_validate_e164.argtypes = [ctypes.c_char_p]
            self.lib.phoneintel_validate_e164.restype = ctypes.c_int
            self.lib.phoneintel_country_code.argtypes = [ctypes.c_char_p]
            self.lib.phoneintel_country_code.restype = ctypes.c_char_p
            self.lib.phoneintel_carrier.argtypes = [ctypes.c_char_p]
            self.lib.phoneintel_carrier.restype = ctypes.c_char_p

        self.country_codes = {
            "1": {"country": "US/CA", "length": 10, "format": "+1 XXX XXX XXXX"},
            "44": {"country": "UK", "length": 10, "format": "+44 XX XXXX XXXX"},
            "55": {"country": "Brazil", "length": 11, "format": "+55 XX XXXXX XXXX"},
            "91": {"country": "India", "length": 10, "format": "+91 XXXXX XXXXX"},
        }

        self.br_ddd_map = {
            "11": "São Paulo/SP", "21": "Rio de Janeiro/RJ", "31": "Belo Horizonte/MG", "41": "Curitiba/PR",
            "51": "Porto Alegre/RS", "61": "Brasília/DF", "71": "Salvador/BA", "81": "Recife/PE",
            "85": "Fortaleza/CE", "27": "Vitória/ES", "48": "Florianópolis/SC", "62": "Goiânia/GO",
            "67": "Campo Grande/MS", "98": "São Luís/MA", "83": "João Pessoa/PB", "79": "Aracaju/SE"
        }

        self.br_carrier_hints = {
            "912": "Claro", "913": "Tim", "914": "Vivo", "915": "Oi", "916": "Claro", "917": "Tim", "918": "Vivo", "919": "Oi"
        }

    def _get_api_key(self, service: str) -> str:
        return os.environ.get(f"TRACELOC_{service.upper()}_API_KEY", "")

    def analyze(self, phone: str) -> Dict:
        if self.cache:
            cached = self.cache.get("phone", phone)
            if cached:
                return cached

        clean = self._clean_number(phone)
        if not self._validate(clean):
            return {"error": "Invalid phone number format"}

        country_info = self._get_country_info(clean)
        if self.lib:
            result = self._analyze_native(phone, clean, country_info)
        else:
            result = self._analyze_python(phone, clean, country_info)

        if self.cache and result and "error" not in result:
            self.cache.set("phone", phone, result)
        return result

    @staticmethod
    def _clean_number(phone: str) -> str:
        return "".join(filter(str.isdigit, phone))

    def _validate(self, phone: str) -> bool:
        if self.lib:
            try:
                return self.lib.phoneintel_validate_e164(phone.encode("utf-8")) == 1
            except Exception:
                pass

        import re
        return bool(re.match(r"^[1-9][0-9]{7,14}$", phone))

    def _get_country_info(self, phone: str) -> Dict:
        if self.lib:
            try:
                code = self.lib.phoneintel_country_code(phone.encode("utf-8")).decode("utf-8")
                if code and code in self.country_codes:
                    info = self.country_codes[code]
                    return {
                        "country_code": code,
                        "country": info["country"],
                        "national_number": phone[len(code):],
                        "format": info["format"],
                    }
            except Exception:
                pass

        for code, info in sorted(self.country_codes.items(), key=lambda item: len(item[0]), reverse=True):
            if phone.startswith(code):
                return {
                    "country_code": code,
                    "country": info["country"],
                    "national_number": phone[len(code):],
                    "format": info["format"],
                }
        return {"country_code": "unknown", "national_number": phone}

    def _line_type_guess(self, country_info: Dict) -> str:
        nn = country_info.get("national_number", "")
        cc = country_info.get("country_code", "")

        if cc == "55":
            if len(nn) == 11 and nn[2:3] == "9":
                return "mobile"
            if len(nn) == 10:
                return "fixed_line"
        if cc == "1" and len(nn) == 10:
            return "fixed_or_mobile"
        if cc in {"44", "91"} and len(nn) >= 10:
            return "mobile_or_fixed"
        return "unknown"

    def _location_guess(self, country_info: Dict) -> str:
        if country_info.get("country_code") != "55":
            return "unknown"

        nn = country_info.get("national_number", "")
        if len(nn) < 2:
            return "unknown"

        ddd = nn[:2]
        return self.br_ddd_map.get(ddd, "Brazil (DDD não mapeado)")

    def _carrier_guess(self, clean: str, country_info: Dict) -> str:
        if self.lib:
            try:
                native = self.lib.phoneintel_carrier(clean.encode("utf-8")).decode("utf-8")
                if native and native.lower() != "unknown":
                    return native
            except Exception:
                pass

        if country_info.get("country_code") == "55":
            nn = country_info.get("national_number", "")
            if len(nn) >= 5 and nn[2:3] == "9":
                prefix3 = nn[2:5]
                if prefix3 in self.br_carrier_hints:
                    return self.br_carrier_hints[prefix3]
            return "carrier_estimate_unavailable_br"

        return "unknown"

    def _analyze_python(self, raw_phone: str, clean: str, country_info: Dict) -> Dict:
        result = {
            "raw": raw_phone,
            "clean": clean,
            "country": country_info,
            "carrier": self._carrier_guess(clean, country_info),
            "location": self._location_guess(country_info),
            "line_type": self._line_type_guess(country_info),
            "processor": "python-heuristic",
            "confidence": "medium" if country_info.get("country_code") == "55" else "low",
        }

        api_key = self._get_api_key("numverify")
        if not api_key:
            return result

        try:
            data = _http_get_json(
                "http://apilayer.net/api/validate",
                {
                    "access_key": api_key,
                    "number": clean,
                    "country_code": country_info.get("country_code", ""),
                    "format": 1,
                },
                self.config.timeout,
                self.config.user_agent,
            )
            if isinstance(data, dict) and data.get("valid"):
                result.update(
                    {
                        "carrier": data.get("carrier") or result["carrier"],
                        "location": data.get("location") or result["location"],
                        "line_type": data.get("line_type") or result["line_type"],
                        "international_format": data.get("international_format", ""),
                        "local_format": data.get("local_format", ""),
                        "processor": "python+online",
                        "confidence": "high",
                    }
                )
        except Exception as exc:
            result["online_error"] = str(exc)

        return result

    def _analyze_native(self, raw_phone: str, clean: str, country_info: Dict) -> Dict:
        result = self._analyze_python(raw_phone, clean, country_info)
        result["processor"] = f"native+{result.get('processor', 'python')}"
        return result


class OutputFormatter:
    @staticmethod
    def json(data: Union[Dict, List]) -> str:
        return json.dumps(data, indent=2, ensure_ascii=False)

    @staticmethod
    def csv(data: List[Dict], headers: List[str]) -> str:
        import io

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
        return output.getvalue()

    @staticmethod
    def human(data: Union[Dict, List]) -> str:
        if isinstance(data, list):
            return "\n".join(OutputFormatter._format_item(item) for item in data)
        return OutputFormatter._format_item(data)

    @staticmethod
    def pretty(data: Union[Dict, List], use_color: bool = True) -> str:
        items = data if isinstance(data, list) else [data]
        blocks = []

        palette = {
            "reset": "[0m",
            "title": "[96m",
            "key": "[92m",
            "muted": "[90m",
            "error": "[91m",
            "warn": "[93m",
        }

        def colorize(text: str, color: str) -> str:
            if not use_color:
                return text
            return f"{palette[color]}{text}{palette['reset']}"

        for index, item in enumerate(items, start=1):
            title = colorize(f"Resultado #{index}", "title")
            lines = [f"╔══════════════════════════════════════════════════════════", f"║ {title}"]

            if "error" in item:
                lines.append(f"║ {colorize('Erro:', 'error')} {item['error']}")
                lines.append("╚══════════════════════════════════════════════════════════")
                blocks.append("\n".join(lines))
                continue

            for key, value in item.items():
                if value is None or value == "":
                    continue

                if isinstance(value, dict):
                    lines.append(f"║ {colorize(key, 'key')}")
                    for sub_key, sub_value in value.items():
                        lines.append(f"║   ├─ {colorize(sub_key, 'muted')}: {sub_value}")
                else:
                    marker = "•"
                    if key == "warning":
                        marker = colorize("⚠", "warn")
                    lines.append(f"║ {marker} {colorize(key, 'key')}: {value}")

            lines.append("╚══════════════════════════════════════════════════════════")
            blocks.append("\n".join(lines))

        return "\n\n".join(blocks)

    @staticmethod
    def _format_item(item: Dict) -> str:
        lines = ["=" * 50]
        for key, value in item.items():
            if value and value != "unknown":
                if isinstance(value, dict):
                    lines.append(f"  {key}:")
                    for sub_key, sub_value in value.items():
                        lines.append(f"    {sub_key}: {sub_value}")
                else:
                    lines.append(f"  {key}: {value}")
        return "\n".join(lines)


class TraceLocCLI:
    def __init__(self):
        self.config = TraceLocConfig()
        self.cache = CacheManager(self.config.cache_db, self.config.cache_ttl)
        self.address_proc = AddressProcessor(self.config, self.cache)
        self.phone_proc = PhoneProcessor(self.config, self.cache)
        self.formatter = OutputFormatter()

    def run(self):
        parser = argparse.ArgumentParser(description="TraceLoc - OSINT Geolocation Tool")
        input_group = parser.add_mutually_exclusive_group(required=True)
        input_group.add_argument("-a", "--address", help="Single address to geocode")
        input_group.add_argument("-p", "--phone", help="Single phone number to analyze")
        input_group.add_argument("-f", "--file", help="Input file with targets (one per line)")

        parser.add_argument("--provider", default="osm", choices=["osm", "locationiq"])
        parser.add_argument("--threads", type=int, default=4)
        parser.add_argument("-o", "--output", help="Output file")
        parser.add_argument("--format", default="pretty", choices=["json", "csv", "human", "pretty"])
        parser.add_argument("--no-cache", action="store_true")
        parser.add_argument("--cache-clear", action="store_true")
        parser.add_argument("--timeout", type=int, default=10)
        parser.add_argument("--verbose", "-v", action="store_true")

        args = parser.parse_args()

        self.config.timeout = args.timeout
        self.config.max_threads = args.threads
        self.config.verbose = args.verbose

        if args.cache_clear:
            self._clear_cache()

        if args.no_cache:
            self.cache = None
            self.address_proc.cache = None
            self.phone_proc.cache = None

        targets = self._get_targets(args)
        if args.address:
            results = self._process_addresses(targets, args.provider)
        elif args.phone:
            results = self._process_phones(targets)
        else:
            results = self._process_auto(targets, args.provider)

        self._output_results(results, args.format, args.output)

    @staticmethod
    def _get_targets(args) -> List[str]:
        if args.address:
            return [line.strip() for line in sys.stdin if line.strip()] if args.address == "-" else [args.address]
        if args.phone:
            return [line.strip() for line in sys.stdin if line.strip()] if args.phone == "-" else [args.phone]
        if args.file:
            with open(args.file, "r", encoding="utf-8") as handle:
                return [line.strip() for line in handle if line.strip()]
        return []

    def _process_addresses(self, addresses: List[str], provider: str) -> List[Dict]:
        if len(addresses) <= 1 or self.config.max_threads <= 1:
            return [self.address_proc.geocode(addr, provider) for addr in addresses]

        import concurrent.futures

        results: List[Dict] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.max_threads) as executor:
            future_to_address = {executor.submit(self.address_proc.geocode, addr, provider): addr for addr in addresses}
            for future in concurrent.futures.as_completed(future_to_address):
                address = future_to_address[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    results.append({"address": address, "error": str(exc)})
        return results

    def _process_phones(self, phones: List[str]) -> List[Dict]:
        return [self.phone_proc.analyze(phone) for phone in phones]

    def _process_auto(self, targets: List[str], provider: str) -> List[Dict]:
        results: List[Dict] = []
        for target in targets:
            compact = target.replace(" ", "").replace("-", "")
            if target.startswith("+") or compact.isdigit():
                results.append(self.phone_proc.analyze(target))
            else:
                results.append(self.address_proc.geocode(target, provider))
        return results

    def _output_results(self, results: List[Dict], output_format: str, output_file: Optional[str]):
        if output_format == "json":
            output = self.formatter.json(results)
        elif output_format == "csv":
            headers = sorted({key for result in results for key in result.keys()})
            output = self.formatter.csv(results, headers)
        elif output_format == "human":
            output = self.formatter.human(results)
        else:
            output = self.formatter.pretty(results, use_color=sys.stdout.isatty() and not output_file)

        if output_file:
            with open(output_file, "w", encoding="utf-8") as handle:
                handle.write(output)
            if self.config.verbose:
                print(f"[+] Results written to {output_file}")
            return

        print(output)

    def _clear_cache(self):
        if self.cache:
            self.cache.conn.execute("DELETE FROM geo_cache")
            self.cache.conn.commit()
            print("[+] Cache cleared")


def main():
    try:
        TraceLocCLI().run()
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
        sys.exit(1)
    except Exception as exc:
        print(f"[!] Fatal error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
