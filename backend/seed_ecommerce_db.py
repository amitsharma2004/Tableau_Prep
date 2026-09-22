import os
import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path

# Resolve DB path dynamically from environment or default to local backend directory
DB_PATH = Path(
    os.getenv(
        "ECOMMERCE_DB_PATH",
        Path(__file__).resolve().parent / "ecommerce_analytics.db",
    )
)

def create_and_seed_db():
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Customers Table
    cursor.execute("""
    CREATE TABLE customers (
        customer_id INTEGER PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT UNIQUE,
        segment TEXT, -- 'Consumer', 'Corporate', 'Home Office'
        city TEXT,
        state TEXT,
        country TEXT,
        signup_date DATE
    );
    """)

    # 2. Categories & Products Table
    cursor.execute("""
    CREATE TABLE products (
        product_id INTEGER PRIMARY KEY,
        product_name TEXT NOT NULL,
        category TEXT NOT NULL, -- 'Technology', 'Furniture', 'Office Supplies'
        sub_category TEXT NOT NULL,
        cost_price REAL NOT NULL,
        retail_price REAL NOT NULL
    );
    """)

    # 3. Orders Table
    cursor.execute("""
    CREATE TABLE orders (
        order_id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL,
        order_date DATE NOT NULL,
        status TEXT NOT NULL, -- 'Completed', 'Shipped', 'Cancelled', 'Refunded'
        shipping_mode TEXT, -- 'Standard', 'Express', 'Overnight'
        shipping_cost REAL,
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
    );
    """)

    # 4. Order Items Table
    cursor.execute("""
    CREATE TABLE order_items (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        discount REAL DEFAULT 0.0,
        FOREIGN KEY (order_id) REFERENCES orders(order_id),
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    );
    """)

    # 5. Product Reviews Table
    cursor.execute("""
    CREATE TABLE product_reviews (
        review_id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        customer_id INTEGER NOT NULL,
        rating INTEGER CHECK (rating BETWEEN 1 AND 5),
        review_text TEXT,
        review_date DATE,
        FOREIGN KEY (product_id) REFERENCES products(product_id),
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
    );
    """)

    # Seed Customers (50 customers)
    segments = ["Consumer", "Corporate", "Home Office"]
    cities = [("Mumbai", "MH"), ("Delhi", "DL"), ("Bengaluru", "KA"), ("Pune", "MH"), ("Hyderabad", "TS"), ("Jaipur", "RJ")]
    first_names = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan", "Diya", "Saanvi", "Aanya", "Aadhya", "Pari", "Ananya", "Myra", "Riya"]
    last_names = ["Sharma", "Verma", "Patel", "Mehta", "Iyer", "Rao", "Gupta", "Deshmukh", "Singh", "Nair"]

    customers_data = []
    base_date = datetime(2025, 1, 1)
    for c_id in range(1, 51):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        city, state = random.choice(cities)
        signup = (base_date + timedelta(days=random.randint(0, 300))).strftime("%Y-%m-%d")
        customers_data.append((c_id, fn, ln, f"{fn.lower()}.{ln.lower()}{c_id}@example.com", random.choice(segments), city, state, "India", signup))

    cursor.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?,?)", customers_data)

    # Seed Products (20 products)
    products_catalog = [
        ("MacBook Pro 16", "Technology", "Laptops", 180000.0, 220000.0),
        ("Dell XPS 15", "Technology", "Laptops", 130000.0, 160000.0),
        ("Logitech MX Master 3S", "Technology", "Accessories", 6000.0, 8995.0),
        ("Keychron K2 Mechanical Keyboard", "Technology", "Accessories", 7000.0, 9500.0),
        ("Ergonomic Mesh Chair", "Furniture", "Chairs", 12000.0, 18500.0),
        ("Standing Desk 140x70", "Furniture", "Desks", 22000.0, 32000.0),
        ("Bookshelf 5-Tier", "Furniture", "Bookcases", 5000.0, 7999.0),
        ("Monitor Arm Dual", "Office Supplies", "Mounts", 3500.0, 5499.0),
        ("LaserJet Multifunction Printer", "Technology", "Machines", 18000.0, 24500.0),
        ("Paper Shredder Heavy Duty", "Office Supplies", "Appliances", 4000.0, 6200.0),
        ("Sticky Notes Pastel Pack", "Office Supplies", "Paper", 150.0, 299.0),
        ("Gel Pens Pack of 10", "Office Supplies", "Pens", 200.0, 450.0),
        ("Filing Cabinet 3-Drawer", "Furniture", "Storage", 8500.0, 12900.0),
        ("Sony WH-1000XM5 Headphones", "Technology", "Audio", 21000.0, 29990.0),
        ("USB-C 7-in-1 Hub", "Technology", "Accessories", 2500.0, 3999.0),
    ]

    products_data = [(i + 1, p[0], p[1], p[2], p[3], p[4]) for i, p in enumerate(products_catalog)]
    cursor.executemany("INSERT INTO products VALUES (?,?,?,?,?,?)", products_data)

    # Seed Orders & Order Items
    order_statuses = ["Completed", "Shipped", "Completed", "Completed", "Refunded", "Cancelled"]
    shipping_modes = ["Standard", "Express", "Overnight"]

    orders_data = []
    order_items_data = []
    order_id_seq = 1001

    for o_id in range(order_id_seq, order_id_seq + 150):
        c_id = random.randint(1, 50)
        o_date = (base_date + timedelta(days=random.randint(30, 450))).strftime("%Y-%m-%d")
        status = random.choice(order_statuses)
        ship_mode = random.choice(shipping_modes)
        ship_cost = 0.0 if ship_mode == "Standard" else random.choice([250.0, 500.0, 950.0])
        orders_data.append((o_id, c_id, o_date, status, ship_mode, ship_cost))

        # 1 to 4 items per order
        num_items = random.randint(1, 4)
        chosen_prods = random.sample(products_data, num_items)
        for prod in chosen_prods:
            qty = random.randint(1, 5)
            disc = random.choice([0.0, 0.05, 0.10, 0.15])
            order_items_data.append((None, o_id, prod[0], qty, prod[5], disc))

    cursor.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?)", orders_data)
    cursor.executemany("INSERT INTO order_items VALUES (?,?,?,?,?,?)", order_items_data)

    # Seed Reviews
    reviews_data = []
    sample_reviews = [
        (5, "Excellent product, highly recommended!"),
        (4, "Build quality is very good, works as expected."),
        (3, "Average, expected better finish for the price."),
        (1, "Broke within a week. Poor support."),
        (5, "Super convenient and perfect for my home office."),
    ]
    for r_id in range(1, 60):
        prod_id = random.randint(1, len(products_catalog))
        cust_id = random.randint(1, 50)
        rating, text = random.choice(sample_reviews)
        r_date = (base_date + timedelta(days=random.randint(60, 450))).strftime("%Y-%m-%d")
        reviews_data.append((None, prod_id, cust_id, rating, text, r_date))

    cursor.executemany("INSERT INTO product_reviews VALUES (?,?,?,?,?,?)", reviews_data)

    conn.commit()
    conn.close()
    print(f"Created SQLite database at {DB_PATH} with 5 rich analytics tables!")

if __name__ == "__main__":
    create_and_seed_db()
