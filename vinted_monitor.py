import json
import os
import random
import time
import requests

# Įrašyk savo Discord Webhook URL čia:
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1548670048107892789/jC0ZzBWmwQ3kzVV25F0QbiaAd_gEd6OyO7vJLKPUjaTKrz78pEeSPnXij5rEIqoeWorr"

# Autoriai / pagrindiniai raktažodžiai
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

# Atskiros knygos / pavadinimai
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
        return set(json.load(f))
    except Exception:
      return set()
  return set()


def save_seen_ids(seen_ids):
  with open(SEEN_FILE, "w", encoding="utf-8") as f:
    json.dump(list(seen_ids), f, ensure_ascii=False)


def send_discord_notification(item):
  title = item.get("title", "Be pavadinimo")
  price_info = item.get("price", {})
  price_val = price_info.get("amount", "0")
  currency = price_info.get("currency_code", "EUR")
  url = item.get("url", "https://www.vinted.lt")
  user_info = item.get("user", {})
  seller_name = user_info.get("login", "Nežinomas pardavėjas")

  # Nuotraukos URL jei yra
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


def check_vinted():
  seen_ids = load_seen_ids()
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
  new_seen_count = 0

  for query in queries[:5]:  # Pirmuoju metu tikriname dalį užklausų, kad neperkrautume
    url = "https://www.vinted.lt/api/v2/catalog/items"
    params = {"search_text": query, "per_page": 10, "order": "newest_first"}

    try:
      resp = session.get(url, headers=headers, params=params, timeout=10)
      if resp.status_code != 200:
        continue

      data = resp.json()
      items = data.get("items", [])

      for item in items:
        item_id = item.get("id")
        if not item_id or item_id in seen_ids:
          continue

        # Patikriname šalį (atmetame Suomiją 'FI')
        country_code = item.get("user", {}).get("countryIsoCode") or item.get(
            "country_code"
        )
        if country_code == "FI":
          seen_ids.add(item_id)
          continue

        title = item.get("title", "")
        price_info = item.get("price", {})
        try:
          price = float(price_info.get("amount", 0))
        except ValueError:
          price = 999.0

        bundle_flag = is_bundle(title)
        # Kainų taisyklė: rinkiniui <= 15 EUR, pavienei knygai <= 5 EUR
        max_allowed_price = 15.0 if bundle_flag else 5.0

        if price <= max_allowed_price:
          send_discord_notification(item)
          print(f"Rasta ir išsiųsta: {title} ({price} EUR)")

        seen_ids.add(item_id)
        new_seen_count += 1

      time.sleep(random.uniform(2.0, 4.0))

    except Exception as e:
      print(f"Klaida ieškant '{query}': {e}")

  save_seen_ids(seen_ids)


if __name__ == "__main__":
  check_vinted()
