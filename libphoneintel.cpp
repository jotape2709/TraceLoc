/*
 * libphoneintel.cpp - High-performance phone number analysis
 * Compile: g++ -shared -O3 -std=c++11 -fPIC libphoneintel.cpp -o libphoneintel.so
 */

#include <map>
#include <regex>
#include <string>
#include <vector>

struct CountryInfo {
    std::string country_code;
    std::string country_name;
    int number_length;
    std::string format;
    std::vector<std::string> carriers;
};

class PhoneDatabase {
public:
    PhoneDatabase() {
        countries_["1"] = {"1", "US/Canada", 10, "+1 XXX XXX XXXX", {"AT&T", "Verizon", "T-Mobile", "Sprint"}};
        countries_["44"] = {"44", "United Kingdom", 10, "+44 XX XXXX XXXX", {"BT", "Vodafone", "O2", "EE"}};
        countries_["55"] = {"55", "Brazil", 11, "+55 XX XXXXX XXXX", {"Vivo", "Claro", "TIM", "Oi"}};
        countries_["91"] = {"91", "India", 10, "+91 XXXXX XXXXX", {"Airtel", "Jio", "Vi", "BSNL"}};

        carrier_map_["1415"] = "AT&T";
        carrier_map_["1212"] = "Verizon";
        carrier_map_["1310"] = "T-Mobile";
    }

    const CountryInfo *get_country_info(const std::string &number) const {
        std::string best_code;
        for (std::map<std::string, CountryInfo>::const_iterator it = countries_.begin(); it != countries_.end(); ++it) {
            const std::string &code = it->first;
            if (number.size() >= code.size() && number.compare(0, code.size(), code) == 0) {
                if (code.size() > best_code.size()) {
                    best_code = code;
                }
            }
        }

        if (best_code.empty()) {
            return NULL;
        }

        return &countries_.find(best_code)->second;
    }

    std::string get_carrier(const std::string &number) const {
        if (number.size() >= 4) {
            std::string prefix = number.substr(0, 4);
            std::map<std::string, std::string>::const_iterator it = carrier_map_.find(prefix);
            if (it != carrier_map_.end()) {
                return it->second;
            }
        }

        return "Unknown";
    }

private:
    std::map<std::string, CountryInfo> countries_;
    std::map<std::string, std::string> carrier_map_;
};

extern "C" {

const char *phoneintel_ping() {
    return "phoneintel-ok";
}

int phoneintel_validate_e164(const char *number) {
    if (!number) {
        return 0;
    }

    static const std::regex pattern("^[1-9][0-9]{7,14}$");
    return std::regex_match(number, pattern) ? 1 : 0;
}

const char *phoneintel_country_code(const char *number) {
    static PhoneDatabase db;
    static std::string out;

    if (!number) {
        out = "";
        return out.c_str();
    }

    const CountryInfo *info = db.get_country_info(number);
    out = info ? info->country_code : "";
    return out.c_str();
}

const char *phoneintel_carrier(const char *number) {
    static PhoneDatabase db;
    static std::string out;

    if (!number) {
        out = "Unknown";
        return out.c_str();
    }

    out = db.get_carrier(number);
    return out.c_str();
}

}
