import google.generativeai as genai
import json
import sqlite3
from datetime import datetime
from typing import Dict, Optional, List
import os


class ReceiptETL:
    """
    Handles the complete ETL process for receipt data:
    1. Extract: Use Gemini to extract structured data from receipt images
    2. Transform: Validate and clean the extracted data
    3. Load: Store in SQLite database
    """
    
    # PROMPT ENGINEERING STRATEGY:
    # This prompt uses several advanced techniques:
    # 1. Role Assignment: "You are an expert financial data extraction assistant"
    # 2. Output Format Specification: Strict JSON schema with examples
    # 3. Few-shot Learning: Examples of expected behavior
    # 4. Edge Case Handling: Instructions for missing data, ambiguous dates
    # 5. Chain-of-Thought: Asks model to classify category based on items
    # 6. Constraints: "CRITICAL" and "MUST" keywords for non-negotiable requirements
    
    GEMINI_SYSTEM_PROMPT = """You are an expert financial data extraction assistant specializing in receipt processing.

Your task is to analyze receipt images and extract structured financial data with high accuracy.

CRITICAL REQUIREMENTS:
1. Output MUST be valid JSON only - no markdown, no explanations, no preamble
2. Use EXACTLY this schema (no additional fields):
{
  "merchant_name": "string",
  "date": "YYYY-MM-DD",
  "total_amount": float,
  "line_items": [
    {
      "item_name": "string",
      "price": float,
      "quantity": int
    }
  ],
  "category": "string",
  "confidence": "high|medium|low",
  "date_estimated": boolean
}

EXTRACTION RULES:

Merchant Name:
- Extract the business/store name (e.g., "Walmart", "Starbucks", "Shell Gas Station")
- Use the most prominent name on the receipt
- If unclear, use "Unknown Merchant"

Date:
- Convert to YYYY-MM-DD format
- If year is missing but month/day present, use current year
- If date is completely missing, use current date and set "date_estimated": true
- Common formats to parse: MM/DD/YYYY, DD-MM-YYYY, Month DD, YYYY

Total Amount:
- Extract the final total (after tax, tips, discounts)
- Look for keywords: "Total", "Amount Due", "Balance", "Grand Total"
- Return as float (e.g., 45.99, not "$45.99")
- If multiple totals exist, use the largest

Line Items:
- Extract individual products/services purchased
- Include item name, price, and quantity (default to 1 if not shown)
- Skip subtotals, tax lines, payment method lines
- If too many items (>20), extract the 10 most expensive

Category (AUTO-CLASSIFICATION):
Analyze the line items and merchant to classify into ONE of these categories:
- "Groceries": Supermarkets, food items, household goods
- "Dining": Restaurants, cafes, fast food, bars
- "Transportation": Gas stations, uber, parking, tolls
- "Utilities": Electric, water, internet, phone bills
- "Healthcare": Pharmacy, doctor visits, medical supplies
- "Entertainment": Movies, games, subscriptions, events
- "Shopping": Clothing, electronics, home goods, general retail
- "Other": Anything that doesn't fit above

Confidence Level:
- "high": All key fields clearly visible and extracted
- "medium": Some fields unclear or estimated
- "low": Receipt quality poor or multiple ambiguities

EXAMPLES:

Example 1 (Grocery Receipt):
{
  "merchant_name": "Whole Foods Market",
  "date": "2024-01-15",
  "total_amount": 87.43,
  "line_items": [
    {"item_name": "Organic Bananas", "price": 3.99, "quantity": 2},
    {"item_name": "Almond Milk", "price": 4.50, "quantity": 1},
    {"item_name": "Chicken Breast", "price": 12.99, "quantity": 1}
  ],
  "category": "Groceries",
  "confidence": "high",
  "date_estimated": false
}

Example 2 (Restaurant Receipt with missing date):
{
  "merchant_name": "Starbucks Coffee",
  "date": "2024-02-08",
  "total_amount": 12.75,
  "line_items": [
    {"item_name": "Caffe Latte Grande", "price": 5.25, "quantity": 1},
    {"item_name": "Blueberry Muffin", "price": 3.50, "quantity": 2}
  ],
  "category": "Dining",
  "confidence": "medium",
  "date_estimated": true
}

NOW PROCESS THE PROVIDED RECEIPT IMAGE:
"""

    def __init__(self, api_key: str, db_path: str = "finance.db"):
        """
        Initialize the ETL pipeline.
        
        Args:
            api_key: Google Gemini API key
            db_path: Path to SQLite database
        """
        # Configure Gemini
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Database setup
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """
        Initialize SQLite database with optimized schema for analytics.
        
        Schema Design Decisions:
        - Transactions table: Core fact table for all purchases
        - LineItems table: Normalized to support item-level analytics
        - Indexes on date and category for fast filtering
        - date_estimated flag for data quality tracking
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Transactions table (Fact table)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_name TEXT NOT NULL,
                transaction_date DATE NOT NULL,
                total_amount REAL NOT NULL,
                category TEXT NOT NULL,
                confidence TEXT,
                date_estimated BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                receipt_processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Line Items table (Dimension table for drill-down analysis)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS LineItems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER DEFAULT 1,
                FOREIGN KEY (transaction_id) REFERENCES Transactions(id) ON DELETE CASCADE
            )
        """)
        
        # Performance indexes for BI queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_transaction_date 
            ON Transactions(transaction_date DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_category 
            ON Transactions(category)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_merchant 
            ON Transactions(merchant_name)
        """)
        
        conn.commit()
        conn.close()
    
    def extract_receipt_data(self, image_path: str) -> Optional[Dict]:
        """
        Extract structured data from receipt image using Gemini Vision API.
        
        Args:
            image_path: Path to receipt image file
            
        Returns:
            Dictionary with extracted data or None if extraction failed
        """
        try:
            # Load and prepare image
            from PIL import Image
            img = Image.open(image_path)
            
            # Call Gemini with system prompt and image
            response = self.model.generate_content([
                self.GEMINI_SYSTEM_PROMPT,
                img
            ])
            
            # Parse JSON response
            # Note: Gemini sometimes wraps JSON in markdown code blocks
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            response_text = response_text.strip()
            
            # Parse JSON
            data = json.loads(response_text)
            
            return data
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Response text: {response_text}")
            return None
        except Exception as e:
            print(f"Extraction error: {e}")
            return None
    
    def validate_and_transform(self, data: Dict) -> Dict:
        """
        Validate and clean extracted data.
        
        Transformations:
        1. Date normalization and validation
        2. Amount validation (must be positive)
        3. Category standardization
        4. Missing value handling
        """
        # Default values for missing data
        if not data.get("date") or data.get("date_estimated"):
            data["date"] = datetime.now().strftime("%Y-%m-%d")
            data["date_estimated"] = True
        
        # Validate date format
        try:
            datetime.strptime(data["date"], "%Y-%m-%d")
        except ValueError:
            # Try to parse and reformat
            data["date"] = datetime.now().strftime("%Y-%m-%d")
            data["date_estimated"] = True
        
        # Validate amount
        data["total_amount"] = max(0.0, float(data.get("total_amount", 0)))
        
        # Standardize category
        valid_categories = [
            "Groceries", "Dining", "Transportation", "Utilities",
            "Healthcare", "Entertainment", "Shopping", "Other"
        ]
        if data.get("category") not in valid_categories:
            data["category"] = "Other"
        
        # Ensure line items exist
        if not data.get("line_items"):
            data["line_items"] = []
        
        # Set default confidence
        if not data.get("confidence"):
            data["confidence"] = "medium"
        
        return data
    
    def load_to_database(self, data: Dict) -> int:
        """
        Load validated data into SQLite database.
        
        Returns:
            Transaction ID of inserted record
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Insert transaction
            cursor.execute("""
                INSERT INTO Transactions 
                (merchant_name, transaction_date, total_amount, category, 
                 confidence, date_estimated)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                data["merchant_name"],
                data["date"],
                data["total_amount"],
                data["category"],
                data.get("confidence", "medium"),
                data.get("date_estimated", False)
            ))
            
            transaction_id = cursor.lastrowid
            
            # Insert line items
            for item in data.get("line_items", []):
                cursor.execute("""
                    INSERT INTO LineItems 
                    (transaction_id, item_name, price, quantity)
                    VALUES (?, ?, ?, ?)
                """, (
                    transaction_id,
                    item["item_name"],
                    item["price"],
                    item.get("quantity", 1)
                ))
            
            conn.commit()
            return transaction_id
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def process_receipt(self, image_path: str) -> Optional[int]:
        """
        Complete ETL pipeline: Extract -> Transform -> Load
        
        Returns:
            Transaction ID if successful, None otherwise
        """
        # Extract
        raw_data = self.extract_receipt_data(image_path)
        if not raw_data:
            return None
        
        # Transform
        clean_data = self.validate_and_transform(raw_data)
        
        # Load
        transaction_id = self.load_to_database(clean_data)
        
        return transaction_id


class FinanceAnalytics:
    """
    Analytics layer for generating BI insights from transaction data.
    """
    
    def __init__(self, db_path: str = "finance.db"):
        self.db_path = db_path
    
    def get_monthly_kpis(self, year: int = None, month: int = None) -> Dict:
        """
        Calculate key performance indicators for a specific month.
        """
        if not year or not month:
            now = datetime.now()
            year, month = now.year, now.month
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Total spend this month
        cursor.execute("""
            SELECT SUM(total_amount) 
            FROM Transactions 
            WHERE strftime('%Y', transaction_date) = ? 
            AND strftime('%m', transaction_date) = ?
        """, (str(year), f"{month:02d}"))
        
        total_spend = cursor.fetchone()[0] or 0.0
        
        # Top spending category
        cursor.execute("""
            SELECT category, SUM(total_amount) as total
            FROM Transactions 
            WHERE strftime('%Y', transaction_date) = ? 
            AND strftime('%m', transaction_date) = ?
            GROUP BY category
            ORDER BY total DESC
            LIMIT 1
        """, (str(year), f"{month:02d}"))
        
        result = cursor.fetchone()
        top_category = result[0] if result else "N/A"
        top_category_amount = result[1] if result else 0.0
        
        conn.close()
        
        return {
            "total_spend": total_spend,
            "top_category": top_category,
            "top_category_amount": top_category_amount
        }
        
    def get_transaction_details(self, transaction_id: int) -> dict:
        """Fetch a specific transaction and its line items by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Fetch main transaction
        cursor.execute("""
            SELECT merchant_name, transaction_date, total_amount, 
                   category, confidence, date_estimated
            FROM Transactions WHERE id = ?
        """, (transaction_id,))
        tx = cursor.fetchone()
        
        if not tx:
            conn.close()
            return None
            
        # Fetch associated line items
        cursor.execute("""
            SELECT item_name, quantity, price 
            FROM LineItems WHERE transaction_id = ?
        """, (transaction_id,))
        
        items = [{"Item": row[0], "Qty": row[1], "Price": f"₹{row[2]:.2f}"} for row in cursor.fetchall()]
        conn.close()
        
        # Return the complete formatted dictionary
        return {
            "Merchant": tx[0],
            "Date": tx[1],
            "Amount": f"₹{tx[2]:.2f}",
            "Category": tx[3],
            "Confidence": tx[4],
            "Date Estimated": "Yes" if tx[5] else "No",
            "Line Items": items
        }
    
    def get_category_breakdown(self, year: int = None, month: int = None) -> List[Dict]:
        """
        Get spending breakdown by category.
        """
        if not year or not month:
            now = datetime.now()
            year, month = now.year, now.month
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT category, SUM(total_amount) as total
            FROM Transactions 
            WHERE strftime('%Y', transaction_date) = ? 
            AND strftime('%m', transaction_date) = ?
            GROUP BY category
            ORDER BY total DESC
        """, (str(year), f"{month:02d}"))
        
        results = cursor.fetchall()
        conn.close()
        
        return [{"category": r[0], "amount": r[1]} for r in results]
    
    def get_daily_spending(self, year: int = None, month: int = None) -> List[Dict]:
        """
        Get daily spending trend for a month.
        """
        if not year or not month:
            now = datetime.now()
            year, month = now.year, now.month
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT transaction_date, SUM(total_amount) as total
            FROM Transactions 
            WHERE strftime('%Y', transaction_date) = ? 
            AND strftime('%m', transaction_date) = ?
            GROUP BY transaction_date
            ORDER BY transaction_date
        """, (str(year), f"{month:02d}"))
        
        results = cursor.fetchall()
        conn.close()
        
        return [{"date": r[0], "amount": r[1]} for r in results]
    
    def search_transactions(self, search_term: str) -> List[Dict]:
        """
        Search transactions by merchant name or item name.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Search in both transactions and line items
        cursor.execute("""
            SELECT DISTINCT 
                t.id,
                t.merchant_name,
                t.transaction_date,
                t.total_amount,
                t.category
            FROM Transactions t
            LEFT JOIN LineItems li ON t.id = li.transaction_id
            WHERE t.merchant_name LIKE ?
            OR li.item_name LIKE ?
            ORDER BY t.transaction_date DESC
            LIMIT 50
        """, (f"%{search_term}%", f"%{search_term}%"))
        
        results = cursor.fetchall()
        conn.close()
        
        return [{
            "id": r[0],
            "merchant": r[1],
            "date": r[2],
            "amount": r[3],
            "category": r[4]
        } for r in results]
    
    def get_all_transactions(self, limit: int = 100) -> List[Dict]:
        """
        Get recent transactions.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, merchant_name, transaction_date, total_amount, 
                   category, confidence, date_estimated
            FROM Transactions
            ORDER BY transaction_date DESC, created_at DESC
            LIMIT ?
        """, (limit,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [{
            "id": r[0],
            "merchant": r[1],
            "date": r[2],
            "amount": r[3],
            "category": r[4],
            "confidence": r[5],
            "date_estimated": bool(r[6])
        } for r in results]
