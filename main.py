import os
from datetime import datetime
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

PORTAL_URL = os.getenv("PORTAL_URL")
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")


def is_today(text):
    if not text or "N/A" in text:
        return False
    try:
        dt = datetime.strptime(text.strip(), "%B %d, %Y %I:%M %p")
        return dt.date() == datetime.now().date()
    except:
        return False


def extract_value(body, label):
    for line in body.splitlines():
        if label in line:
            return line.replace(label, "").strip()
    return ""


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # ---- OPEN PAGE ----
    page.goto(PORTAL_URL, wait_until="networkidle")

    # ---- LOGIN IF NEEDED ----
    if "login" in page.url or page.locator('input[name="email"]').count() > 0:
        page.wait_for_selector('input[name="email"]', timeout=10000)

        page.fill('input[name="email"]', EMAIL)
        page.fill('input[name="password"]', PASSWORD)

        with page.expect_navigation():
            page.click('button[type="submit"]')

        page.goto(PORTAL_URL, wait_until="networkidle")

    # ---- WAIT FOR MAIN CONTENT ----
    page.wait_for_selector("text=Attendance History", timeout=15000)

    # ---- EXTRACT ATTENDANCE ----
    body = page.inner_text("body")

    check_in = extract_value(body, "Last Check-In:")
    check_out = extract_value(body, "Last Check-Out:")

    print("Check-In:", check_in)
    print("Check-Out:", check_out)

    now = datetime.now()
    hour = now.hour

    is_morning = 7 <= hour < 12
    is_evening = 17 <= hour < 22

    has_checkin_today = is_today(check_in)
    has_checkout_today = is_today(check_out)

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

    # ---- CLICK BUTTON SAFELY ----
    if should_click:
        button = page.locator('button:has-text("Check")')
        button.wait_for(timeout=10000)

        button.click()
        print("Clicked button")

    browser.close()