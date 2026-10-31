import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
import smtplib
import re

# Load environment variables
load_dotenv()

MY_EMAIL = os.getenv("MY_EMAIL")
MY_PASSWORD = os.getenv("MY_PASSWORD")
TO_EMAIL = os.getenv("TO_EMAIL")

# Amazon product URL
URL = "https://www.amazon.in/wipro-Warm-White-Bulb-N90002/dp/B00LO6WD2C?ref=dlx_deals_dg_dcl_B00LO6WD2C_dt_sl10_33_pi&pf_rd_r=3W691BARVXXXY3NY23Z2&pf_rd_p=a1f490ce-fe55-425e-9932-455f92f72533&sbo=RZvfv%2F%2FHxDF%2BO5021pAnSA%3D%3D&th=1"
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/139.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Connection": "keep-alive",
}

print("Connecting to Amazon...")

try:
    response = requests.get(
        URL,
        headers=headers,
        timeout=30,
        allow_redirects=True
    )

except requests.RequestException as e:
    print("Could not connect to Amazon.")
    print("Error:", e)
    exit()

print("Status code:", response.status_code)
print("Final URL:", response.url)

# Save response
with open("amazon_page.html", "w", encoding="utf-8") as file:
    file.write(response.text)

soup = BeautifulSoup(response.text, "html.parser")

# Check whether Amazon returned a CAPTCHA / robot page
page_text = soup.get_text(" ", strip=True).lower()

if "captcha" in page_text or "robot check" in page_text:
    print()
    print("Amazon returned a CAPTCHA/Robot Check page.")
    print("Open amazon_page.html to confirm.")
    exit()

# Find product title
title_element = soup.select_one("#productTitle")

if title_element:
    product_name = " ".join(title_element.get_text().split())
else:
    product_name = "Amazon Product"

# Try multiple price locations
price = None

price_selectors = [
    "#corePriceDisplay_desktop_feature_div .a-offscreen",
    "#corePriceDisplay_mobile_feature_div .a-offscreen",
    "#apex_desktop .a-offscreen",
    ".priceToPay .a-offscreen",
    ".a-price .a-offscreen",
    "span.a-offscreen",
]

for selector in price_selectors:
    element = soup.select_one(selector)

    if element:
        price_text = element.get_text(strip=True)

        match = re.search(r"[\d,]+(?:\.\d{1,2})?", price_text)

        if match:
            price = float(match.group().replace(",", ""))
            break

# Alternative: search Amazon HTML for a price
if price is None:
    patterns = [
        r'"priceAmount":\s*"?([\d,]+\.\d{2})',
        r'"price":\s*"?([\d,]+\.\d{2})',
        r'\$([\d,]+\.\d{2})',
    ]

    for pattern in patterns:
        match = re.search(pattern, response.text)

        if match:
            price = float(match.group(1).replace(",", ""))
            break

# If price wasn't found
if price is None:
    print()
    print("Could not find the Amazon price.")
    print()
    print("Amazon is not providing the price to this request.")
    print("The Amazon response was saved as:")
    print("amazon_page.html")
    print()
    print("Open amazon_page.html to see what Amazon returned.")
    exit()

# Display result
print()
print("----------------------------------------")
print("AMAZON PRICE TRACKER")
print("----------------------------------------")
print("Product:", product_name)
print("Price:  $", price)
print("----------------------------------------")

# Price threshold
TARGET_PRICE = 250.00

if price <= TARGET_PRICE:

    print()
    print("Price is below your target price!")

    if not MY_EMAIL or not MY_PASSWORD or not TO_EMAIL:
        print()
        print("Email details are not configured.")
        print("Create a .env file with:")
        print()
        print("MY_EMAIL=MY_EMAIL")
        print("MY_PASSWORD=MY_PASSWORD")
        print("TO_EMAIL=TO_EMAIL")
        exit()

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as connection:

            connection.starttls()

            connection.login(
                MY_EMAIL,
                MY_PASSWORD
            )

            connection.sendmail(
                from_addr=MY_EMAIL,
                to_addrs=TO_EMAIL,
                msg=(
                    f"Subject: Amazon Price Alert\n\n"
                    f"{product_name}\n\n"
                    f"Current price: ${price}\n\n"
                    f"{URL}"
                )
            )

        print("Email alert sent successfully!")

    except Exception as e:
        print("Email could not be sent.")
        print("Error:", e)

else:

    print()
    print(
        f"Price is ${price}, which is above "
        f"your target of ${TARGET_PRICE}."
    )

    print("No email was sent.")