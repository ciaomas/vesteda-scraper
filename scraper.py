from playwright.sync_api import sync_playwright
import requests
import json
import os
import time

# === CONFIGURATION ===
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEEN_FILE = "seen.json"
LISTING_URL = "https://www.vesteda.com/nl/woning-zoeken?placeType=1&sortType=0&radius=20&s=Amsterdam&sc=woning&latitude=52.36757278442383&longitude=4.904139041900635&filters=&priceFrom=500&priceTo=9999"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    response = requests.post(url, data=payload)
    return response.ok

def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r") as f:
        return set(json.load(f))

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def main():
    seen = load_seen()
    new_seen = set()
    new_listings = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print("🔎 Opening Vesteda listings page...")
        page.goto(LISTING_URL, timeout=60000)

        # Accept cookies
        try:
            page.click('#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll', timeout=5000)
            print("✅ Cookie banner accepted.")
            time.sleep(2)
        except:
            print("⚠️ No cookie banner found.")

        print("⏳ Scrolling to load listings...")
        for _ in range(15):
            page.mouse.wheel(0, 4000)
            time.sleep(0.8)

        try:
            page.wait_for_selector('article.o-card--listing', timeout=20000)
        except:
            print("⚠️ Listings didn’t appear in time — trying again after scrolling more...")
            for _ in range(5):
                page.mouse.wheel(0, 4000)
                time.sleep(1)
            try:
                page.wait_for_selector('article.o-card--listing', timeout=10000)
            except:
                print("❌ Failed to load listings. Exiting.")
                browser.close()
                return

        listings = page.query_selector_all('article.o-card--listing')
        print(f"🔍 Found {len(listings)} total listings.")

        for listing in listings:
            try:
                html = listing.inner_html().lower()
                if "verhuurd" in html or "gereserveerd" in html:
                    continue

                title = listing.query_selector('h3 span').inner_text().strip()
                city = listing.query_selector('strong').inner_text().strip()
                price = listing.query_selector('.o-card--listview-price b').inner_text().strip()
                href = listing.query_selector('div.c-button--hyperlink').get_attribute('href')
                full_url = f"https://www.vesteda.com{href}"

                if full_url not in seen:
                    new_listings.append((title, city, price, full_url))

                new_seen.add(full_url)
            except Exception as e:
                print("⚠️ Error parsing listing:", e)
                continue

        browser.close()

    for title, city, price, url in new_listings:
        message = f"🏠 <b>{title}</b>\n📍 {city}\n💶 {price}\n🔗 {url}"
        send_telegram_message(message)
        print(f"🚀 Sent alert: {title}")

    save_seen(seen.union(new_seen))

    if not new_listings:
        print("✅ No new listings found.")
        send_telegram_message("ℹ️ <b>No new listings found.</b>")
    else:
        print(f"✅ {len(new_listings)} new listings sent.")

if __name__ == "__main__":
    main()
