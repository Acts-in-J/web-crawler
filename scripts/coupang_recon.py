"""쿠팡 리뷰 정찰 - Chrome 프로필 복사 후 CDP 연결"""
import json
import os
import shutil
import subprocess
import time
from playwright.sync_api import sync_playwright

CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_PROFILE = r"C:\Users\byung\AppData\Local\Google\Chrome\User Data"
TEMP_PROFILE = r"C:\Users\byung\AppData\Local\Temp\chrome_crawl_profile"

# Step 1: Copy Chrome profile
print("1) Copying Chrome profile (this may take a moment)...")
if os.path.exists(TEMP_PROFILE):
    shutil.rmtree(TEMP_PROFILE, ignore_errors=True)

# Only copy essential files (cookies, local state)
os.makedirs(os.path.join(TEMP_PROFILE, "Default", "Network"), exist_ok=True)

files_to_copy = [
    ("Local State", "Local State"),
    ("Default/Preferences", "Default/Preferences"),
    ("Default/Network/Cookies", "Default/Network/Cookies"),
    ("Default/Login Data", "Default/Login Data"),
]

for src_rel, dst_rel in files_to_copy:
    src = os.path.join(CHROME_PROFILE, src_rel)
    dst = os.path.join(TEMP_PROFILE, dst_rel)
    if os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        print(f"   Copied: {src_rel}")

print("   Profile copied.")

# Step 2: Launch Chrome with copied profile + remote debugging
print("\n2) Launching Chrome with debugging port...")
chrome_proc = subprocess.Popen([
    CHROME_EXE,
    f"--user-data-dir={TEMP_PROFILE}",
    "--remote-debugging-port=9222",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-default-apps",
    "--disable-extensions",
    "--disable-sync",
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

time.sleep(5)

# Step 3: Connect via Playwright CDP
print("3) Connecting via CDP...")
captured_reviews = []

def handle_response(response):
    url = response.url
    if "review" in url and "coupang.com" in url:
        try:
            body = response.text()
            captured_reviews.append({"url": url, "status": response.status, "body": body[:15000]})
            print(f"  [CAPTURED] {response.status} {url[:120]}")
        except Exception as e:
            captured_reviews.append({"url": url, "status": response.status, "error": str(e)})

try:
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.new_page()
        page.on("response", handle_response)

        print("   Navigating to product page...")
        page.goto(
            "https://www.coupang.com/vp/products/5690564126?itemId=9421831344&vendorItemId=76706774229",
            wait_until="domcontentloaded",
            timeout=30000
        )
        title = page.title()
        print(f"   Title: {title}")

        time.sleep(8)

        # Scroll to review section
        page.evaluate("document.querySelector('#sdpReview')?.scrollIntoView()")
        time.sleep(3)

        # Click review tab
        try:
            tabs = page.query_selector_all("a")
            for tab in tabs:
                text = tab.inner_text()
                if "상품평" in text and "(" in text:
                    tab.click()
                    print(f"   Clicked tab: {text}")
                    time.sleep(5)
                    break
        except Exception as e:
            print(f"   Tab click error: {e}")

        # Check review content
        review_el = page.query_selector("#sdpReview")
        if review_el:
            print(f"   Review section: {review_el.inner_text()[:300]}")

        # Get performance entries
        perf = page.evaluate("""
            () => performance.getEntriesByType('resource')
                .filter(e => e.name.includes('review'))
                .map(e => ({url: e.name, type: e.initiatorType, dur: Math.round(e.duration)}))
        """)
        print(f"\n   Performance review entries: {len(perf)}")
        for entry in perf:
            print(f"   [{entry['type']}] {entry['url'][:150]}")

        page.screenshot(path="./scripts/coupang_review_page.png")
        browser.close()

except Exception as e:
    print(f"Error: {e}")

# Cleanup
chrome_proc.terminate()
chrome_proc.wait()

print(f"\n=== Captured {len(captured_reviews)} review responses ===")
for item in captured_reviews:
    print(f"\nURL: {item['url'][:200]}")
    print(f"Status: {item['status']}")
    if "body" in item:
        try:
            data = json.loads(item["body"])
            print(f"Keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            preview = json.dumps(data, ensure_ascii=False)[:3000]
            print(f"Preview: {preview}")
            with open("./scripts/review_api_sample.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("-> Saved to scripts/review_api_sample.json")
        except json.JSONDecodeError:
            if 'Access Denied' in item["body"]:
                print("ACCESS DENIED")
            else:
                print(f"Raw: {item['body'][:500]}")

# Cleanup temp profile
shutil.rmtree(TEMP_PROFILE, ignore_errors=True)
