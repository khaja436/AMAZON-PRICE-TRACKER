from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import re
import smtplib
import os
import json
import threading
import time

from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.header import Header


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

app = Flask(__name__)

MY_EMAIL = os.getenv("MY_EMAIL")
MY_PASSWORD = os.getenv("MY_PASSWORD")

TRACKING_FILE = "tracked_products.json"

# Check Amazon every 1 hour
CHECK_INTERVAL = 60 * 60


# ============================================================
# TRACKING FILE
# ============================================================

def load_tracking_data():

    if not os.path.exists(TRACKING_FILE):
        return []

    try:
        with open(
            TRACKING_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception as e:

        print("Could not read tracking file:", e)

        return []


def save_tracking_data(products):

    try:

        with open(
            TRACKING_FILE,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                products,
                file,
                indent=4,
                ensure_ascii=False
            )

    except Exception as e:

        print("Could not save tracking data:", e)


# ============================================================
# AMAZON PRICE CHECKER
# ============================================================

def get_amazon_price(url):

    headers = {

        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/139.0.0.0 Safari/537.36"
        ),

        "Accept-Language": "en-US,en;q=0.9",

        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,"
            "*/*;q=0.8"
        ),

        "Connection": "keep-alive"
    }

    try:

        print()
        print("Checking Amazon...")
        print("URL:", url)

        response = requests.get(
            url,
            headers=headers,
            timeout=30,
            allow_redirects=True
        )

        print(
            "Amazon status:",
            response.status_code
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        # ----------------------------------------------------
        # CAPTCHA CHECK
        # ----------------------------------------------------

        page_text = soup.get_text(
            " ",
            strip=True
        ).lower()

        if (
            "captcha" in page_text
            or "robot check" in page_text
        ):

            print(
                "Amazon returned a CAPTCHA/Robot Check."
            )

            return None, None

        # ----------------------------------------------------
        # PRODUCT NAME
        # ----------------------------------------------------

        title_element = soup.select_one(
            "#productTitle"
        )

        if title_element:

            product_name = " ".join(
                title_element.get_text().split()
            )

        else:

            product_name = "Amazon Product"

        # ----------------------------------------------------
        # PRICE
        # ----------------------------------------------------

        price = None

        price_selectors = [

            "#corePriceDisplay_desktop_feature_div "
            ".a-offscreen",

            "#corePriceDisplay_mobile_feature_div "
            ".a-offscreen",

            "#apex_desktop .a-offscreen",

            ".priceToPay .a-offscreen",

            ".a-price .a-offscreen",

            "span.a-offscreen"
        ]

        for selector in price_selectors:

            element = soup.select_one(
                selector
            )

            if element:

                price_text = element.get_text(
                    strip=True
                )

                match = re.search(
                    r"[\d,]+(?:\.\d{1,2})?",
                    price_text
                )

                if match:

                    price = float(
                        match.group().replace(
                            ",",
                            ""
                        )
                    )

                    break

        # ----------------------------------------------------
        # ALTERNATIVE PRICE SEARCH
        # ----------------------------------------------------

        if price is None:

            patterns = [

                r'"priceAmount":\s*"?([\d,]+\.?\d*)',

                r'"price":\s*"?([\d,]+\.?\d*)',

                r'₹\s*([\d,]+\.?\d*)',

                r'\$\s*([\d,]+\.?\d*)'
            ]

            for pattern in patterns:

                match = re.search(
                    pattern,
                    response.text
                )

                if match:

                    price = float(
                        match.group(1).replace(
                            ",",
                            ""
                        )
                    )

                    break

        if price is None:

            print(
                "Could not find Amazon price."
            )

            return None, product_name

        print(
            f"Product: {product_name}"
        )

        print(
            f"Current price: ₹{price:,.2f}"
        )

        return price, product_name

    except Exception as e:

        print(
            "Amazon price check failed:",
            e
        )

        return None, None


# ============================================================
# EMAIL ALERT
# ============================================================

def send_price_alert(
    product_name,
    price,
    target_price,
    product_url,
    to_email
):

    if not MY_EMAIL or not MY_PASSWORD:

        print(
            "Gmail credentials are not configured."
        )

        return False

    try:

        email_body = (

            "Amazon Price Alert\n\n"

            f"Product:\n"
            f"{product_name}\n\n"

            f"Current Price:\n"
            f"₹{price:,.2f}\n\n"

            f"Target Price:\n"
            f"₹{target_price:,.2f}\n\n"

            "The product price has reached "
            "your target price.\n\n"

            f"Product Link:\n"
            f"{product_url}"
        )

        email_message = MIMEText(
            email_body,
            "plain",
            "utf-8"
        )

        email_message["Subject"] = Header(
            "Amazon Price Alert",
            "utf-8"
        )

        email_message["From"] = MY_EMAIL

        email_message["To"] = to_email

        with smtplib.SMTP(
            "smtp.gmail.com",
            587
        ) as connection:

            connection.starttls()

            connection.login(
                MY_EMAIL,
                MY_PASSWORD
            )

            connection.sendmail(
                MY_EMAIL,
                to_email,
                email_message.as_string()
            )

        print()
        print(
            "========================================"
        )

        print(
            "EMAIL ALERT SENT!"
        )

        print(
            f"Sent to: {to_email}"
        )

        print(
            "========================================"
        )

        return True

    except Exception as e:

        print(
            "Email could not be sent:"
        )

        print(e)

        return False


# ============================================================
# CHECK ALL TRACKED PRODUCTS
# ============================================================

def check_tracked_products():

    print()
    print(
        "========================================"
    )

    print(
        "AUTOMATIC PRICE CHECK"
    )

    print(
        "========================================"
    )

    products = load_tracking_data()

    if not products:

        print(
            "No products are currently being tracked."
        )

        return

    updated_products = []

    for product in products:

        url = product["url"]

        target_price = float(
            product["target_price"]
        )

        email = product["email"]

        price, product_name = get_amazon_price(
            url
        )

        if price is None:

            # Keep tracking if price couldn't be checked

            updated_products.append(product)

            continue

        # Save latest information

        product["current_price"] = price

        product["product_name"] = product_name

        # ----------------------------------------------------
        # TARGET PRICE REACHED
        # ----------------------------------------------------

        if price <= target_price:

            print()
            print(
                f"TARGET REACHED!"
            )

            print(
                f"Current: ₹{price:,.2f}"
            )

            print(
                f"Target: ₹{target_price:,.2f}"
            )

            email_sent = send_price_alert(

                product_name,

                price,

                target_price,

                url,

                email
            )

            if email_sent:

                # Do NOT add it back.
                # This stops tracking after alert.

                print(
                    "Tracking stopped for this product."
                )

                continue

            else:

                # If email failed, keep tracking

                updated_products.append(
                    product
                )

        else:

            print(
                f"Still above target."
            )

            print(
                f"Current: ₹{price:,.2f}"
            )

            print(
                f"Target: ₹{target_price:,.2f}"
            )

            updated_products.append(
                product
            )

    save_tracking_data(
        updated_products
    )


# ============================================================
# BACKGROUND TRACKER
# ============================================================

def background_tracker():

    print()
    print(
        "========================================"
    )

    print(
        "AUTOMATIC TRACKER STARTED"
    )

    print(
        "Checking every 1 hour."
    )

    print(
        "========================================"
    )

    while True:

        try:

            check_tracked_products()

        except Exception as e:

            print(
                "Background tracker error:",
                e
            )

        print()
        print(
            "Next automatic check in 1 hour."
        )

        time.sleep(
            CHECK_INTERVAL
        )


# ============================================================
# WEBSITE HOME PAGE
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# START TRACKING
# ============================================================

@app.route(
    "/track",
    methods=["POST"]
)
def track():

    try:

        data = request.get_json()

        url = data.get("url")

        target_price = float(
            data.get("target_price")
        )

        email = data.get("email")

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        if not url:

            return jsonify({

                "success": False,

                "message":
                "Please enter an Amazon product URL."
            })

        if not email:

            return jsonify({

                "success": False,

                "message":
                "Please enter your email."
            })

        if target_price <= 0:

            return jsonify({

                "success": False,

                "message":
                "Target price must be greater than zero."
            })

        # ----------------------------------------------------
        # CHECK AMAZON NOW
        # ----------------------------------------------------

        price, product_name = get_amazon_price(
            url
        )

        if price is None:

            return jsonify({

                "success": False,

                "message":
                "Could not find the Amazon price."
            })

        # ----------------------------------------------------
        # PRICE ALREADY BELOW TARGET
        # ----------------------------------------------------

        if price <= target_price:

            email_sent = send_price_alert(

                product_name,

                price,

                target_price,

                url,

                email
            )

            if email_sent:

                return jsonify({

                    "success": True,

                    "product": product_name,

                    "price": price,

                    "message":
                    (
                        "Price is already below "
                        "your target! "
                        "Email alert sent."
                    )
                })

            else:

                return jsonify({

                    "success": False,

                    "product": product_name,

                    "price": price,

                    "message":
                    (
                        "Price is below your target "
                        "but the email could not be sent."
                    )
                })

        # ----------------------------------------------------
        # SAVE PRODUCT FOR AUTOMATIC TRACKING
        # ----------------------------------------------------

        products = load_tracking_data()

        # Prevent duplicate tracking

        for existing in products:

            if (
                existing["url"] == url
                and existing["email"] == email
            ):

                return jsonify({

                    "success": True,

                    "product": product_name,

                    "price": price,

                    "message":
                    "This product is already being tracked."
                })

        new_product = {

            "url": url,

            "target_price": target_price,

            "email": email,

            "product_name": product_name,

            "current_price": price
        }

        products.append(
            new_product
        )

        save_tracking_data(
            products
        )

        print()
        print(
            "========================================"
        )

        print(
            "NEW PRODUCT ADDED"
        )

        print(
            f"Product: {product_name}"
        )

        print(
            f"Current price: ₹{price:,.2f}"
        )

        print(
            f"Target price: ₹{target_price:,.2f}"
        )

        print(
            f"Email: {email}"
        )

        print(
            "Automatic tracking started."
        )

        print(
            "========================================"
        )

        return jsonify({

            "success": True,

            "product": product_name,

            "price": price,

            "message":
            (
                f"Currently ₹{price:,.2f}. "
                f"Your target is ₹{target_price:,.2f}. "
                "Automatic tracking has started. "
                "You can close the website."
            )
        })

    except ValueError:

        return jsonify({

            "success": False,

            "message":
            "Please enter a valid target price."
        })

    except Exception as e:

        print(
            "Tracking error:",
            e
        )

        return jsonify({

            "success": False,

            "message":
            "An error occurred: " + str(e)
        })


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    # Start background tracker only once

    tracker_thread = threading.Thread(
        target=background_tracker,
        daemon=True
    )

    tracker_thread.start()

    print()
    print(
        "========================================"
    )

    print(
        "AMAZON AUTOMATIC PRICE TRACKER"
    )

    print(
        "========================================"
    )

    print(
        "Website:"
    )

    print(
        "http://127.0.0.1:5000"
    )

    print()
    print(
        "You can close the browser after"
    )

    print(
        "starting a tracking request."
    )

    print(
        "Keep this Python program running."
    )

    print(
        "========================================"
    )

    app.run(
        debug=False,
        host="127.0.0.1",
        port=5000
    )