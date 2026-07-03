import json
import sqlite3
import os

def generate_pricing_seed():
    pricing_data = {
        "metal": "platinum",
        "price": 985.50,
        "unit": "oz",
        "is_mock": True
    }
    with open("mock_pricing_seed.json", "w") as f:
        json.dump(pricing_data, f, indent=4)
    print("Created mock_pricing_seed.json")

def generate_inventory_db():
    db_path = "mock_inventory.sqlite"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE inventory (
        sku_id TEXT PRIMARY KEY,
        product_name TEXT,
        declared_material TEXT,
        description TEXT,
        cost_price REAL,
        retail_price REAL
    )
    """)
    
    skus = [
        # Standard Platinum Items
        ("PT-RING-001", "Solitaire Platinum Ring", "Platinum", "A classic solitaire engagement ring crafted in pure platinum.", 450.00, 1200.00),
        ("PT-BAND-002", "Brushed Platinum Band", "Platinum", "Modern brushed finish platinum wedding band.", 320.00, 850.00),
        ("PT-NECK-003", "Platinum Diamond Pendant", "Platinum", "Elegant platinum pendant featuring a brilliant cut diamond.", 550.00, 1500.00),
        ("PT-EARR-004", "Platinum Stud Earrings", "Platinum", "Simple and sophisticated platinum diamond stud earrings.", 280.00, 750.00),
        ("PT-BRAC-005", "Platinum Tennis Bracelet", "Platinum", "Stunning platinum tennis bracelet with handset diamonds.", 1800.00, 4200.00),
        ("PT-RING-006", "Vintage Platinum Halo Ring", "Platinum", "Vintage-inspired halo ring in solid platinum.", 600.00, 1600.00),
        
        # Edge Case 1: Two-tone item categorized as pure Platinum
        ("PT-RING-007", "Platinum and Rose Gold Ring", "Platinum", "A striking platinum ring featuring 18k rose gold accents for a two-tone finish.", 520.00, 1350.00),
        
        # Edge Case 2: Two-tone item categorized as pure Platinum
        ("PT-BAND-008", "Mixed Metal Comfort Band", "Platinum", "Comfort fit band in platinum with a yellow gold inner sleeve creating a two-tone aesthetic.", 410.00, 1100.00),
        
        # Edge Case 3: Very low margin to trigger Agent A's margin violation
        ("PT-RING-009", "Platinum Promotional Ring", "Platinum", "A standard platinum ring offered at a highly competitive promotional price.", 800.00, 900.00),
        
        # Standard Platinum Item
        ("PT-NECK-010", "Platinum Choker", "Platinum", "A modern, minimalist platinum choker necklace.", 950.00, 2400.00)
    ]
    
    cursor.executemany("""
    INSERT INTO inventory (sku_id, product_name, declared_material, description, cost_price, retail_price)
    VALUES (?, ?, ?, ?, ?, ?)
    """, skus)
    
    conn.commit()
    conn.close()
    print("Created mock_inventory.sqlite and populated with 10 SKUs")

if __name__ == "__main__":
    generate_pricing_seed()
    generate_inventory_db()
