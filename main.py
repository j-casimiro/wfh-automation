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


def wait_for_network_idle_safely(page, timeout=10000):
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception as e:
        print(f"Network idle timeout of {timeout}ms exceeded. Continuing: {e}")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    # Force PH timezone so the site always renders timestamps in PH time,
    # regardless of the server timezone (GitHub Actions uses UTC)
    context = browser.new_context(timezone_id="Asia/Manila")
    page = context.new_page()
    page.set_default_navigation_timeout(120000)
    page.set_default_timeout(120000)

    # ---- OPEN PAGE ----
    page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=120000)
    wait_for_network_idle_safely(page, 10000)

    # ---- WAIT FOR PAGE INITIALIZATION ----
    # Wait up to 2 minutes for the page to render either the login screen or the dashboard
    page.wait_for_selector('input[name="email"], text="Last Check-In:"', timeout=120000)

    # ---- LOGIN IF NEEDED ----
    if page.locator('input[name="email"]').count() > 0:
        page.fill('input[name="email"]', EMAIL)
        page.fill('input[name="password"]', PASSWORD)

        with page.expect_navigation(timeout=120000):
            page.click('button[type="submit"]')

        page.goto(PORTAL_URL, wait_until="domcontentloaded", timeout=120000)
        wait_for_network_idle_safely(page, 10000)

    # ---- WAIT FOR MAIN CONTENT ----
    page.wait_for_selector("text=Last Check-In:", timeout=120000)

    # ---- EXTRACT ATTENDANCE ----
    body = page.inner_text("body")

    check_in = extract_value(body, "Last Check-In:")
    check_out = extract_value(body, "Last Check-Out:")

    print("Check-In:", check_in)
    print("Check-Out:", check_out)

    now = now_ph()
    hour = now.hour

    is_morning = 5 <= hour < 15
    is_evening = 17 <= hour < 24

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
        button.wait_for(timeout=30000)

        button.click()
        print("Clicked button")

    context.close()
    browser.close()