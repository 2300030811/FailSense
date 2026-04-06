"""
Task definitions for the SQL Debug environment.
Each task has DDL, seed data, a broken/reference query, and reference results.
"""

from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class Task:
    task_id: str
    difficulty: str
    description: str
    ddl: str
    seed_sql: str
    reference_query: str
    reference_result: List[Any]
    broken_query: Optional[str] = None
    explain_plan: Optional[str] = None


TASK_1 = Task(
    task_id="fix_query",
    difficulty="easy",
    description=(
        "Fix the broken SQL query below. It has exactly 2 bugs: wrong column names.\n"
        "The correct query should find the name and email of all customers from 'Mumbai', "
        "ordered by name ascending.\n\n"
        "Table: customers(id INTEGER, name TEXT, email TEXT, city TEXT, age INTEGER)"
    ),
    ddl="""CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    city TEXT NOT NULL,
    age INTEGER NOT NULL
);""",
    seed_sql="""INSERT INTO customers VALUES
(1, 'Aarav Shah', 'aarav@example.com', 'Mumbai', 28),
(2, 'Priya Patel', 'priya@example.com', 'Delhi', 34),
(3, 'Rohan Mehta', 'rohan@example.com', 'Mumbai', 22),
(4, 'Neha Singh', 'neha@example.com', 'Bangalore', 29),
(5, 'Amit Kumar', 'amit@example.com', 'Mumbai', 41),
(6, 'Divya Nair', 'divya@example.com', 'Chennai', 31);""",
    broken_query="SELECT nme, emal FROM customers WHERE city = 'Mumbai' ORDER BY name ASC;",
    reference_query="SELECT name, email FROM customers WHERE city = 'Mumbai' ORDER BY name ASC;",
    reference_result=[
        ("Aarav Shah", "aarav@example.com"),
        ("Amit Kumar", "amit@example.com"),
        ("Rohan Mehta", "rohan@example.com"),
    ],
)


TASK_2 = Task(
    task_id="write_join",
    difficulty="medium",
    description=(
        "Write a SQL query from scratch using the schema below.\n\n"
        "Tables:\n"
        "  customers(id, name, email, city)\n"
        "  products(id, name, price, category)\n"
        "  orders(id, customer_id, product_id, quantity, order_date)\n\n"
        "Task: Find each customer's name and their total amount spent "
        "(quantity * price). Only include customers who spent MORE than 500 total. "
        "Order by total_spent descending.\n"
        "Return exactly these columns: customer_name, total_spent"
    ),
    ddl="""CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    city TEXT NOT NULL
);
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    category TEXT NOT NULL
);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    order_date TEXT NOT NULL
);""",
    seed_sql="""INSERT INTO customers VALUES
(1, 'Aarav Shah', 'aarav@example.com', 'Mumbai'),
(2, 'Priya Patel', 'priya@example.com', 'Delhi'),
(3, 'Rohan Mehta', 'rohan@example.com', 'Mumbai'),
(4, 'Neha Singh', 'neha@example.com', 'Bangalore');
INSERT INTO products VALUES
(1, 'Laptop', 800.0, 'Electronics'),
(2, 'Phone', 300.0, 'Electronics'),
(3, 'Desk', 200.0, 'Furniture'),
(4, 'Chair', 150.0, 'Furniture');
INSERT INTO orders VALUES
(1, 1, 1, 1, '2024-01-15'),
(2, 1, 2, 2, '2024-01-16'),
(3, 2, 3, 3, '2024-02-01'),
(4, 2, 4, 1, '2024-02-03'),
(5, 3, 2, 1, '2024-02-10'),
(6, 4, 1, 2, '2024-03-01'),
(7, 4, 4, 3, '2024-03-05');""",
    reference_query="""SELECT c.name AS customer_name, SUM(o.quantity * p.price) AS total_spent
FROM orders o
JOIN customers c ON o.customer_id = c.id
JOIN products p ON o.product_id = p.id
GROUP BY c.id, c.name
HAVING SUM(o.quantity * p.price) > 500
ORDER BY total_spent DESC;""",
    reference_result=[
        ("Neha Singh", 2050.0),
        ("Aarav Shah", 1400.0),
        ("Priya Patel", 750.0),
    ],
)


TASK_3 = Task(
    task_id="optimize_query",
    difficulty="hard",
    description=(
        "The query below is slow - it does a FULL TABLE SCAN on the events table (50k rows).\n"
        "An index exists on (event_type, created_at). Rewrite the query so it uses this index.\n\n"
        "Table: events(id, user_id, event_type, created_at, payload)\n"
        "Index: idx_events_type_date ON events(event_type, created_at)\n\n"
        "Task: Return user_id and count of 'purchase' events for users with more than 3 "
        "purchase events in the last 30 days. Order by purchase_count descending.\n"
        "Return columns: user_id, purchase_count\n\n"
        "REQUIREMENT: Your query's EXPLAIN QUERY PLAN must NOT say 'SCAN TABLE events'.\n"
        "HINT: Put your WHERE clause BEFORE GROUP BY and make sure event_type filter is present."
    ),
    ddl="""CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT
);
CREATE INDEX idx_events_type_date ON events(event_type, created_at);
CREATE INDEX idx_events_user ON events(user_id);""",
    seed_sql="",  # seeded programmatically in environment.py
    broken_query="""SELECT user_id, COUNT(*) as purchase_count
FROM events
GROUP BY user_id
HAVING SUM(CASE WHEN event_type = 'purchase' AND created_at >= date('now', '-30 days') THEN 1 ELSE 0 END) > 3
ORDER BY purchase_count DESC;""",
    explain_plan="SCAN TABLE events  (this is the problem - fix it)",
    reference_query="""SELECT user_id, COUNT(*) as purchase_count
FROM events
WHERE event_type = 'purchase'
  AND created_at >= date('now', '-30 days')
GROUP BY user_id
HAVING COUNT(*) > 3
ORDER BY purchase_count DESC;""",
    reference_result=[],  # computed live from DB
)


TASKS = {t.task_id: t for t in [TASK_1, TASK_2, TASK_3]}
