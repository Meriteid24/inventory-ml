from flask import Flask, request, jsonify
import pandas as pd
import numpy as np
import joblib
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import sqlite3
from functools import lru_cache
import time

app = Flask(__name__)

# ======================
# CONFIGURATION
# ======================
DB_PATH = "C:/Users/User/Desktop/projects/InventoryManagement-Django/db.sqlite3"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# ======================
# TREND SCRAPING FUNCTIONS
# ======================

def save_trends_to_db(trends):
    if not trends:
        return

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions_trendingproduct (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT,
                    product TEXT,
                    scraped_at TEXT,
                    match_confidence REAL NOT NULL
                )
            """)
            cursor.execute("DELETE FROM transactions_trendingproduct")
            cursor.executemany(
                "INSERT INTO transactions_trendingproduct (source, product, scraped_at, match_confidence) VALUES (?, ?, ?, ?)",
                [(t["source"], t["product"], t["scraped_at"], 0.8) for t in trends]  # Default confidence of 0.8
            )
            conn.commit()
            print(f"✅ Saved {len(trends)} trends to database")
    except Exception as e:
        print(f"❌ Failed to save trends: {e}")

def scrape_amazon():
    try:
        url = "https://www.amazon.com/bestsellers/computers"
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        return [p.get_text(strip=True) for p in soup.select(".a-carousel-card .p13n-sc-truncate")[:15]]
    except Exception as e:
        print(f"⚠️ Amazon scrape failed: {e}")
        return []

def scrape_newegg():
    try:
        url = "https://www.newegg.com/Best-Sellers/Computer-Accessories/ID-93"
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        return [item.get_text(strip=True) for item in soup.select(".item-title")[:15]]
    except Exception as e:
        print(f"⚠️ Newegg scrape failed: {e}")
        return []

def scrape_jumia():
    try:
        url = "https://www.jumia.co.ke/computing/"
        response = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        products = []
        # Try different selectors as Jumia might change their layout
        selectors = [
            ".name",  # Main product name selector
            ".info .title",  # Alternative selector
            "h3.name"  # Another possible variant
        ]
        
        for selector in selectors:
            products = [item.get_text(strip=True) for item in soup.select(selector)[:15]]
            if products:
                break
                
        return products
    except Exception as e:
        print(f"⚠️ Jumia scrape failed: {e}")
        return []

def scrape_global_trends():
    print("\n=== Scraping Latest Trends ===")
    scrapers = {
        "Amazon": scrape_amazon,
        "Newegg": scrape_newegg,
        "Jumia": scrape_jumia
    }

    all_trends = []
    for site, scraper in scrapers.items():
        print(f"Scraping {site}...")
        products = scraper()
        all_trends.extend({
            "source": site,
            "product": product,
            "scraped_at": datetime.now().isoformat()
        } for product in products)
        print(f"Found {len(products)} products on {site}")

    save_trends_to_db(all_trends) 
    return all_trends
@lru_cache(maxsize=1)
def get_trending_products(ttl_hash=None):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT product FROM transactions_trendingproduct")
            return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"❌ DB error: {e}")
        return []

def is_trending(item_name):
    from fuzzywuzzy import fuzz
    item_lower = item_name.lower()
    return any(fuzz.partial_ratio(item_lower, p.lower()) > 80 for p in get_trending_products())

# ======================
# PREDICTION SYSTEM
# ======================

try:
    model = joblib.load("rf_sales.pkl")
    print("✅ Model loaded successfully")
except Exception as e:
    print(f"❌ Model load failed: {e}")
    model = None

KENYAN_SCHOOL_TERMS = {
    "Term 1": {"dates": (1, 4, 4, 7), "demand_factor": 1.3},
    "Term 2": {"dates": (5, 10, 8, 5), "demand_factor": 1.2},
    "Term 3": {"dates": (9, 6, 11, 24), "demand_factor": 1.4},
    "Holidays": {"dates": (11, 25, 1, 3), "demand_factor": 0.8}
}

CATEGORY_SETTINGS = {
    "mouse": {"threshold": 0.6, "multiplier": 1.8, "min": 10, "max": None, "trend_boost": 1.2},
    "keyboard": {"threshold": 0.7, "multiplier": 1.6, "min": 5, "max": None, "trend_boost": 1.15},
    "monitor": {"threshold": 0.9, "multiplier": 1.1, "min": 1, "max": 3, "trend_boost": 1.05},
    "default": {"threshold": 0.75, "multiplier": 1.5, "min": 3, "max": None, "trend_boost": 1.1}
}

def get_current_term(date):
    date = pd.to_datetime(date)
    for term, config in KENYAN_SCHOOL_TERMS.items():
        s_m, s_d, e_m, e_d = config["dates"]
        start = datetime(date.year, s_m, s_d)
        end = datetime(date.year, e_m, e_d)
        if (s_m > e_m and (date >= start or date <= end)) or (start <= date <= end):
            return term, config["demand_factor"]
    return "Holidays", KENYAN_SCHOOL_TERMS["Holidays"]["demand_factor"]

def calculate_order(row):
    item_name = str(row["item_name"]).lower()
    settings = next((v for k, v in CATEGORY_SETTINGS.items() if k in item_name), CATEGORY_SETTINGS["default"])
    available = row["Available Stock"]
    predicted = row["Predicted_Items_Sold"]
    term_factor = row["Term_Factor"]

    critical_low = available < (2 if "monitor" in item_name else 5)
    normal_restock = predicted >= available * settings["threshold"]

    if not (critical_low or normal_restock):
        return 0

    base_order = predicted * settings["multiplier"] * term_factor
    if is_trending(row["item_name"]):
        base_order *= settings["trend_boost"]

    order_qty = max(base_order - available, settings["min"])
    if settings["max"]:
        order_qty = min(order_qty, settings["max"])

    return int(np.ceil(order_qty))

def save_predictions_to_db(predictions_df):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions_predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT,
                    predicted_items_sold INTEGER,
                    suggested_order INTEGER,
                    predicted_at TEXT
                )
            """)
            cursor.executemany(
                "INSERT INTO transactions_predictions (item_name, predicted_items_sold, suggested_order, predicted_at) VALUES (?, ?, ?, ?)",
                [
                    (
                        row["item_name"],
                        int(row["Predicted_Items_Sold"]),
                        int(row["Suggested_Order"]),
                        datetime.now().isoformat()
                    )
                    for _, row in predictions_df.iterrows()
                ]
            )
            conn.commit()
            print("✅ Predictions saved to database")
    except Exception as e:
        print(f"❌ Error saving predictions: {e}")

# ======================
# API ENDPOINTS
# ======================

@app.route("/predict_bulk", methods=["POST"])
def predict_bulk():
    try:
        data = request.json
        df = pd.DataFrame(data)

        df["Rolling_7day_Avg"] = df.get("Rolling_7day_Avg", df["Stocks_bought"])
        df["Rolling_30day_Avg"] = df.get("Rolling_30day_Avg", df["Stocks_bought"])
        df["Term"] = df.get("Term", "Holidays")
        df["Term_Factor"] = df.get("Term_Factor", 1.0)

        df["Date"] = pd.to_datetime(df["Date"])
        df["Month"] = df["Date"].dt.month
        df["DayOfWeek"] = df["Date"].dt.dayofweek
        df["IsWeekend"] = df["DayOfWeek"].apply(lambda x: 1 if x >= 5 else 0)

        df["trend_score"] = df.get("trend_score", 0)

        features = [
            "Available Stock", "Stocks_bought", "Month",
            "DayOfWeek", "IsWeekend", "trend_score"
        ]

        df["Predicted_Items_Sold"] = np.round(model.predict(df[features])).astype(int)
        df["Suggested_Order"] = df.apply(calculate_order, axis=1)

        print(df[["item_name", "Predicted_Items_Sold", "Suggested_Order"]])  # Console log
        save_predictions_to_db(df[["item_name", "Predicted_Items_Sold", "Suggested_Order"]])  # Save to DB

        return jsonify(df[["item_name", "Predicted_Items_Sold", "Suggested_Order"]].to_dict(orient="records"))

    except Exception as e:
        print(f"Prediction error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/scrape-trends", methods=["GET"])
def trigger_scrape():
    trends = scrape_global_trends()
    return jsonify({
        "status": "success",
        "trends_count": len(trends),
        "sample": trends[:3]
    })

@app.route("/trends", methods=["GET"])
def get_trends():
    return jsonify({
        "trends": get_trending_products(),
        "count": len(get_trending_products())
    })

# ======================
# APPLICATION STARTUP
# ======================

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 Starting Inventory Prediction System")
    print("="*50 + "\n")
    scrape_global_trends()
    app.run(host="0.0.0.0", port=5000, debug=True)
