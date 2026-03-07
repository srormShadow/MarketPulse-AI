"""Generate a rich demo SKU master + sales CSV for MarketPulse AI demo purposes."""
import csv
import random
from datetime import date, timedelta

# ── SKU catalog (6 categories, 4 SKUs each = 24 SKUs) ─────────────────────────
skus = [
    # Snacks
    ("SNK_CHIPS_LAY",   "Lay's Classic Salted Chips 50g",       "Snacks",        30,  17,  900),
    ("SNK_BISCUIT_PG",  "Parle-G Original Biscuits 250g",       "Snacks",        30,  18,  800),
    ("SNK_NAMKEEN_HD",  "Haldiram's Aloo Bhujia 200g",          "Snacks",        80,  48,  600),
    ("SNK_CHOCO_KITKAT","KitKat Chocolate Bar 30g",             "Snacks",        25,  15, 1000),

    # Beverages
    ("BEV_JUICE_TRP",   "Tropicana Orange Juice 1L",            "Beverages",    120,  72,  400),
    ("BEV_COLA_CC",     "Coca-Cola 600ml",                      "Beverages",     45,  27,  700),
    ("BEV_TEA_TATA",    "Tata Tea Premium 250g",                "Beverages",    145,  98,  350),
    ("BEV_WATER_KLEY",  "Kinley Mineral Water 1L",              "Beverages",     20,  10, 1200),

    # Dairy
    ("DAI_BUTTER_AMUL", "Amul Butter 500g",                     "Dairy",        278, 220,  200),
    ("DAI_MILK_MDRY",   "Mother Dairy Full Cream Milk 1L",      "Dairy",         68,  55,  500),
    ("DAI_CURD_AMUL",   "Amul Dahi 500g",                       "Dairy",         55,  40,  300),
    ("DAI_CHEESE_AMUL", "Amul Cheese Slices 200g",              "Dairy",        140,  95,  220),

    # Personal Care
    ("PCA_SHMP_HNS",    "Head and Shoulders Shampoo 200ml",     "Personal Care", 235, 165,  180),
    ("PCA_SOAP_DOVE",   "Dove Moisturising Soap 100g",          "Personal Care",  60,  38,  500),
    ("PCA_TPSTE_CLG",   "Colgate MaxFresh 200g",                "Personal Care", 128,  88,  320),
    ("PCA_DEODR_AXE",   "Axe Dark Temptation Deodorant 150ml", "Personal Care", 250, 175,  150),

    # Home Care
    ("HMC_DETG_SURF",   "Surf Excel Matic 2kg",                 "Home Care",    340, 255,  120),
    ("HMC_DISH_VIM",    "Vim Dishwash Liquid 750ml",            "Home Care",    115,  78,  200),
    ("HMC_FLOOR_LZL",   "Lizol Floor Cleaner 500ml",            "Home Care",    165, 115,  160),
    ("HMC_AIRCL_GLD",   "Godrej aer Room Freshener 220ml",      "Home Care",    240, 170,  140),

    # Staples
    ("STP_RICE_BSMT",   "India Gate Basmati Rice 5kg",          "Staples",      595, 450,   90),
    ("STP_ATTA_ASH",    "Aashirvaad Atta 10kg",                 "Staples",      590, 445,   70),
    ("STP_DAL_LNTH",    "Tata Sampann Masoor Dal 1kg",          "Staples",      150, 110,  250),
    ("STP_OIL_FRTN",    "Fortune Sunflower Oil 1L",             "Staples",      180, 142,  380),
]

# ── Date range: last 90 days ending yesterday ─────────────────────────────────
today = date(2026, 3, 7)
start_date = today - timedelta(days=90)
end_date = today - timedelta(days=1)

def date_range(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)

def sales_for_sku(sku_id, d, base):
    r = random.Random(hash((sku_id, d.isoformat())))
    mult = 1.0
    if d.weekday() in (5, 6):
        mult *= 1.25
    if date(2026, 3, 14) <= d <= date(2026, 3, 20):
        mult *= 1.45
    if d == date(2026, 1, 26):
        mult *= 1.3
    noise = r.uniform(0.82, 1.18)
    return max(1, int(base * mult * noise))

base_sales = {
    "SNK_CHIPS_LAY": 55, "SNK_BISCUIT_PG": 70, "SNK_NAMKEEN_HD": 40, "SNK_CHOCO_KITKAT": 80,
    "BEV_JUICE_TRP": 30, "BEV_COLA_CC": 85, "BEV_TEA_TATA": 45, "BEV_WATER_KLEY": 120,
    "DAI_BUTTER_AMUL": 20, "DAI_MILK_MDRY": 95, "DAI_CURD_AMUL": 60, "DAI_CHEESE_AMUL": 25,
    "PCA_SHMP_HNS": 18, "PCA_SOAP_DOVE": 35, "PCA_TPSTE_CLG": 30, "PCA_DEODR_AXE": 12,
    "HMC_DETG_SURF": 15, "HMC_DISH_VIM": 22, "HMC_FLOOR_LZL": 14, "HMC_AIRCL_GLD": 10,
    "STP_RICE_BSMT": 25, "STP_ATTA_ASH": 20, "STP_DAL_LNTH": 35, "STP_OIL_FRTN": 50,
}

sku_out = r"d:\Projects\MarketPulse_AI\MarketPulse-AI\data\demo_sku_master_v2.csv"
with open(sku_out, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["sku_id", "product_name", "category", "mrp", "cost", "current_inventory"])
    for row in skus:
        w.writerow(row)
print(f"SKU master written: {sku_out}  ({len(skus)} SKUs)")

sales_out = r"d:\Projects\MarketPulse_AI\MarketPulse-AI\data\demo_sales_upload.csv"
rows_written = 0
with open(sales_out, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["date", "sku_id", "units_sold"])
    for sku_id, _, _, _, _, _ in skus:
        base = base_sales[sku_id]
        for d in date_range(start_date, end_date):
            w.writerow([d.isoformat(), sku_id, sales_for_sku(sku_id, d, base)])
            rows_written += 1
print(f"Sales data written: {sales_out}  ({rows_written} rows, {len(skus)} SKUs, 90 days)")
