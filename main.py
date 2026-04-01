import os
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

PORTAL_URL = os.getenv("PORTAL_URL")
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")

# ---- PH TIMEZONE ----
PH_TIMEZONE = timezone(timedelta(hours=8))


def now_ph():
    return datetime.now(PH_TIMEZONE)


def is_today(text):
    if not text or "n/a" in text.lower():
        return False
    for fmt in ("%B %d, %Y at %I:%M:%S %p", "%B %d, %Y %I:%M:%S %p", "%B %d, %Y at %I:%M %p", "%B %d, %Y %I:%M %p"):
        try:
            # Browser context is set to Asia/Manila, so the site always displays PH time
            dt = datetime.strptime(text.strip(), fmt)
            return dt.date() == now_ph().date()
        except:
            continue
    print("Date parse failed:", text)
    return False


def extract_value(body, label):
    for line in body.splitlines():
        if label in line:
            return line.replace(label, "").strip()
    return ""


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    # Force PH timezone so the site always renders timestamps in PH time,
    # regardless of the server timezone (GitHub Actions uses UTC)
    context = browser.new_context(timezone_id="Asia/Manila")
    page = context.new_page()

    # ---- OPEN PAGE ----
    page.goto(PORTAL_URL, wait_until="domcontentloaded")

    # ---- LOGIN IF NEEDED ----
    if "login" in page.url or page.locator('input[name="email"]').count() > 0:
        page.wait_for_selector('input[name="email"]', timeout=10000)

        page.fill('input[name="email"]', EMAIL)
        page.fill('input[name="password"]', PASSWORD)

        with page.expect_navigation():
            page.click('button[type="submit"]')

        page.goto(PORTAL_URL, wait_until="domcontentloaded")

    # ---- WAIT FOR MAIN CONTENT ----
    page.wait_for_selector("text=Attendance History", timeout=15000)

    # ---- EXTRACT ATTENDANCE ----
    body = page.inner_text("body")

    check_in = extract_value(body, "Last Check-In:")
    check_out = extract_value(body, "Last Check-Out:")

    print("Check-In:", check_in)
    print("Check-Out:", check_out)

    now = now_ph()
    hour = now.hour

    is_morning = 7 <= hour < 12
    is_evening = 17 <= hour < 22

    has_checkin_today = is_today(check_in)
    has_checkout_today = is_today(check_out)

    print("Current PH Time:", now.strftime("%Y-%m-%d %H:%M:%S"))

    # ---- DECISION ----
    should_click = False

    if not has_checkin_today and is_morning:
        print("Action: CHECK-IN")
        should_click = True

    elif has_checkin_today and not has_checkout_today and is_evening:
        print("Action: CHECK-OUT")
        should_click = True

    else:
        print("Action: SKIP")

    # ---- EXTRA SAFETY GUARD ----
    if not (is_morning or is_evening):
        print("Outside allowed time window → FORCE SKIP")
        should_click = False

    # ---- CLICK BUTTON ----
    if should_click:
        button = page.locator('button:has-text("Check")')
        button.wait_for(timeout=10000)

        button.click()
        print("Clicked button")

    context.close()
    browser.close()