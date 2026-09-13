import json
import os
import random
import time
import requests
from google import genai
from google.genai import types

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1548670048107892789/jC0ZzBWmwQ3kzVV25F0QbiaAd_gEd6OyO7vJLKPUjaTKrz78pEeSPnXij5rEIqoeWorr"

# Inicijuojame Gemini klientą su API raktu iš GitHub Secrets
gemini_api_key = os.environ.get("GEMINI_API_KEY")
gemini_client = genai.Client(api_key=gemini_api_key) if gemini_api_key else None

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


def is_valid_book_cover_with_ai(image_url, query_title):
  """Patikrina per Gemini AI, ar nuotraukoje tikrai fizinė knyga ir ar ji yra tik EN/LT kalba."""
  if not gemini_client:
    print("DEBUG: Nėra gemini_client!")
    return True
  if not image_url:
    print("DEBUG: Nėra image_url!")
    return True

  try:
    headers = {"User-Agent": "Mozilla/5.0"}
    img_resp = requests.get(image_url, headers=headers, timeout=10)
    print(f"DEBUG: Paveiksliuko atsisiuntimo statusas: {img_resp.status_code}")
    if img_resp.status_code != 200:
      return True
    img_bytes = img_resp.content

    prompt = (
        f"Esi griežtas Vinted skelbimų moderatorius. "
        f"Ieškoma knyga arba autorius: '{query_title}'. "
        f"Analizuok pateiktą nuotrauką. "
        f"Atsakyk TIK vienu žodžiu: TAIP arba NE. "
        f"Taisyklės, kad atsakytum TAIP (atitinka visus punktus): "
        f"1. Tai turi būti FIZINĖ KNYGA (minkštas/kietas viršelis, puslapiai). Jokiu būdu negali būti figūrėlė, žaislas, drabužis, plakatas, aksesuaras ar kas nors kita. "
        f"2. Ant knygos viršelio matomas tekstas turi būti TIK ANGLŲ arba LIETUVIŲ kalba. Jei teksto kalba yra suomių, lenkų, vokiečių, ispanų ar bet kuri kita – atsakyk NE. "
        f"Jei bent vienas punktas neatitinka – atsakyk NE."
    )

    response = gemini_client.models.generate_content(
        model="gemini-1.5-flash",
        contents=[
            types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
            prompt,
        ],
    )
    answer = response.text.strip().upper()
    print(f"DEBUG: Gemini atsakymas gautas -> '{answer}'")
    return "TAIP" in answer

  except Exception as e:
    print(f"AI Vision klaida: {e}")
    return True  # Laikinai grąžinam True, kad matytum ar knygos praeina


def send_discord_notification(item, item_type="knyga"):
  title = item.get("title", "Be pavadinimo")
  price_info = item.get("price", {})
  price_val = price_info.get("amount", "0")
  currency = price_info.get("currency_code", "EUR")
  url = item.get("url", "https://www.vinted.lt")
  user_info = item.get("user", {})
  seller_name = user_info.get("login", "Nežinomas pardavėjas")
  country = str(user_info.get("country_iso_code", "Nežinoma")).upper()

  icon = "📚" if item_type == "knyga" else "🎮"
  label = "Nauja knyga Vinted" if item_type == "knyga" else "Naujas žaidimas Vinted"

  photo_url = None
  photos = item.get("photos", [])
  if photos:
    photo_url = photos[0].get("url")

  payload = {
      "embeds": [
          {
              "title": f"{icon} {label}: {title}",
              "url": url,
              "color": 3447003 if item_type == "knyga" else 5763719,
              "fields": [
                  {"name": "Kaina", "value": f"{price_val} {currency}", "inline": True},
                  {"name": "Pardavėjas", "value": f"{seller_name} ({country})", "inline": True},
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
  return any(kw in title.lower() for kw in bundle_keywords)


def has_strict_keyword_match(item, query):
  title = str(item.get("title", "")).lower()
  desc = str(item.get("description", "")).lower()
  brand = str(item.get("brand_title", "")).lower()
  full_text = f"{title} {desc} {brand}"
  return query.lower() in full_text


def is_clothing_or_invalid_category(item):
  url = str(item.get("url", "")).lower()
  invalid_url_keywords = ["/moterims/", "/vyrams/", "/vaikams/", "/women/", "/men/", "/kids/"]
  if any(kw in url for kw in invalid_url_keywords):
    return True
  return False


def is_invalid_book_item(item):
  title = str(item.get("title", "")).lower()
  description = str(item.get("description", "")).lower()
  full_text = f"{title} {description}"

  # Atmesti ne knygų daiktus (figūrėlės, plakatai, drabužiai ir t.t.)
  non_book_keywords = [
      "figurėlė", "figure", "figūra", "funko", "pop!", "plakatas", "poster", 
      "marškinėliai", "t-shirt", "hoodie", "džemperis", "lipdukas", "sticker", 
      "pakabukas", "keychain", "merch", "paveikslas"
  ]
  if any(kw in full_text for kw in non_book_keywords):
    return True

  user_info = item.get("user", {})
  country = str(user_info.get("country_iso_code", "")).upper()
  if not country:
    country = str(item.get("country_code", "")).upper()

  if country in ["FI", "SE"]:
    return True

  if is_clothing_or_invalid_category(item):
    return True

  attributes = item.get("attributes", [])
  if isinstance(attributes, list):
    for attr in attributes:
      code = str(attr.get("code", "")).lower()
      name = str(attr.get("name", "")).lower()
      if "lang" in code or "kalba" in name or "język" in name or "jezyk" in name:
        ans = str(attr.get("answer", "")).lower()
        val = str(attr.get("value", "")).lower()
        combined_val = f"{ans} {val}"
        if any(p in combined_val for p in ["lenkų", "lenku", "polish", "polski", "pl", "suomių", "finnish"]):
          return True

  polish_chars_in_title = ["ł", "ś", "ć", "ż", "ź", "ę", "ą", "ń"]
  if any(char in title for char in polish_chars_in_title):
    return True

  if any(word in title for word in ["książka", "ksiazka", "część", "czesc"]):
    return True

  polish_language_phrases = ["po polsku", "język polski", "jezyk polski", "wersja polska", "wydanie polskie"]
  if any(phrase in description for phrase in polish_language_phrases):
    return True

  return False


def check_vinted():
  seen_ids = load_seen_ids()
  session = requests.Session()
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.1; Win64; x64) AppleWebKit/537.36 (KHTML,"
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

  book_queries = AUTHORS + BOOKS
  for query in book_queries:
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

        if is_invalid_book_item(item):
          seen_ids.add(item_id)
          continue

        if not has_strict_keyword_match(item, query):
          seen_ids.add(item_id)
          continue

        # AI viršelio patikrinimas čia:
        photos = item.get("photos", [])
        photo_url = photos[0].get("url") if photos else None
        if not photo_url or not is_valid_book_cover_with_ai(photo_url, query):
          print(f"AI arba sistema atmetė: {item.get('title')}")
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
          send_discord_notification(item, item_type="knyga")
          print(f"Rasta knyga: {title} ({price} EUR)")

        seen_ids.add(item_id)

      time.sleep(random.uniform(1.5, 3.0))

    except Exception as e:
      print(f"Klaida ieškant knygos '{query}': {e}")

  save_seen_ids(seen_ids)
  print(f"Baigta. Viso matytų ID po ciklo: {len(seen_ids)}")


if __name__ == "__main__":
  check_vinted()
