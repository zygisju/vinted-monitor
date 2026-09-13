import json
import os
import random
import time
import requests

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1548670048107892789/jC0ZzBWmwQ3kzVV25F0QbiaAd_gEd6OyO7vJLKPUjaTKrz78pEeSPnXij5rEIqoeWorr"

AUTHORS = [
    "Freida McFadden",
    "Chris Carter",
    "Ana Huang",
    "Holly Jackson",
    "Emily Henry",
    "Ali Hazelwood",
    "Mercedes Ron",
    "Elsie Silver",
    "LJ Ross",
    "Agnė Bausienė",
    "Lauren Asher",
    "Hanna Grace",
]

BOOKS = [
    "The Witch",
    "Brain Damage",
    "Dead Med",
    "The Coworker",
    "The Wife Upstairs",
    "The Ex",
    "Do you remember?",
    "The Gift",
    "The Widow's husband's secret lie",
    "Death Row",
    "The Dinner Party",
    "The Devil wears scrubs",
    "The Devil you know",
    "Baby City",
    "Lakefront Billionaires",
    "Dreamland Billionaires",
    "Dirty Air",
    "Chestnut springs",
    "Rose hill",
]

SEEN_FILE = "seen_items.json"


def load_seen_ids():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(str(x) for x in data)
        except Exception as e:
            print(f"Klaida skaitant {SEEN_FILE}: {e}")
            return set()
    return set()


def save_seen_ids(seen_ids):
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(list(seen_ids), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Klaida rašant {SEEN_FILE}: {e}")


def send_discord_notification(item):
    title = item.get("title", "Be pavadinimo")
    price_info = item.get("price", {})
    price_val = price_info.get("amount", "0")
    currency = price_info.get("currency_code", "EUR")
    url = item.get("url", "https://www.vinted.lt")
    user_info = item.get("user", {})
    seller_name = user_info.get("login", "Nežinomas pardavėjas")

    photo_url = None
    photos = item.get("photos", [])
    if photos:
        photo_url = photos[0].get("url")

    payload = {
        "embeds": [
            {
                "title": f"📚 Nauja knyga Vinted: {title}",
                "url": url,
                "color": 3447003,
                "fields": [
                    {"name": "Kaina", "value": f"{price_val} {currency}", "inline": True},
                    {"name": "Pardavėjas", "value": seller_name, "inline": True},
                ],
            }
        ]
    }
    if photo_url:
        payload["embeds"][0]["image"] = {"url": photo_url}

    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    except Exception as e:
        print(f"Nepavyko išsiųsti į Discord: {e}")


def is_bundle(title):
    bundle_keywords = ["rinkinys", "komplektas", "set", "dalys", "knygų rinkinys"]
    t_lower = title.lower()
    return any(kw in t_lower for kw in bundle_keywords)


def is_invalid_item(item):
    # 1. Griežtas Suomijos blokavimas
    user_info = item.get("user", {})
    country = str(user_info.get("country_iso_code", "")).upper()
    if not country:
        country = str(item.get("country_code", "")).upper()
    
    if country == "FI":
        return True

    # 2. Kalbos atributų patikra (Lenkų)
    for field in ["language", "language_id", "package_language", "original_language"]:
        val = str(item.get(field, "")).lower()
        if any(w in val for w in ["pl", "polish", "lenk", "18"]):
            return True

    attributes = item.get("attributes", [])
    if isinstance(attributes, list):
        for attr in attributes:
            code = str(attr.get("code", "")).lower()
            name = str(attr.get("name", "")).lower()
            answer = str(attr.get("answer", "")).lower()
            value = str(attr.get("value", "")).lower()

            if any(k in code or k in name for k in ["lang", "kalba", "book_language"]):
                if any(p in answer or p in value for p in ["lenkų", "lenku", "polish", "pl", "18"]):
                    return True

            attr_combined = f"{code} {name} {answer} {value}".lower()
            if any(term in attr_combined for term in ["lenkų", "lenku", "język polski", "po polsku"]):
                return True

    # 3. Teksto patikra aprašyme ir pavadinime
    title = str(item.get("title", ""))
    description = str(item.get("description", ""))
    full_text = f"{title} {description}".lower()

    polish_letters = ["ł", "ść", "ż", "ź", "ę", "ą", "ń", "ó"]
    if any(char in full_text for char in polish_letters):
        return True

    polish_words = [
        "wydawnictwo", "miękka oprawa", "twarda oprawa", "sprzedam",
        "książka", "książki", "okładka", "stron", "po polsku",
        "język polski", "seria ", "używana", "stan bardzo dobry",
        "stan idealny", "jedno lato", "rywali", "zwrot akcji", "czytać"
    ]
    if any(word in full_text for word in polish_words):
        return True

    return False


def check_vinted():
    seen_ids = load_seen_ids()
    initial_seen_count = len(seen_ids)
    session = requests.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
            " like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "lt-LT,lt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.vinted.lt/",
    }

    try:
        session.get("https://www.vinted.lt/", headers=headers, timeout=10)
    except Exception as e:
        print(f"Klaida jungiantis į vinted.lt: {e}")
        return

    queries = AUTHORS + BOOKS

    for query in queries:
        url = "https://www.vinted.lt/api/v2/catalog/items"
        params = {
            "search_text": query,
            "per_page": 20,
            "order": "newest_first",
            "catalog_ids": "117",
        }

        try:
            resp = session.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code != 200:
                continue

            data = resp.json()
            items = data.get("items", [])

            for item in items:
                item_id = str(item.get("id"))
                if not item_id or item_id in seen_ids:
                    continue

                if is_invalid_item(item):
                    seen_ids.add(item_id)
                    continue

                title = item.get("title", "")
                price_info = item.get("price", {})
                try:
                    price = float(price_info.get("amount", 0))
                except ValueError:
                    price = 999.0

                bundle_flag = is_bundle(title)
                max_allowed_price = 15.0 if bundle_flag else 5.0

                if price <= max_allowed_price:
                    send_discord_notification(item)
                    print(f"Rasta ir išsiųsta: {title} ({price} EUR)")

                seen_ids.add(item_id)

            time.sleep(random.uniform(1.5, 3.0))

        except Exception as e:
            print(f"Klaida ieškant '{query}': {e}")

    save_seen_ids(seen_ids)
    print(f"Baigta. Viso matytų ID prieš: {initial_seen_count}, po: {len(seen_ids)}")


if __name__ == "__main__":
    check_vinted()
