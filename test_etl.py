import sys
import json
from etl_pipeline import ReceiptETL, FinanceAnalytics
from datetime import datetime


def test_receipt_processing(image_path: str, api_key: str):
    """
    Test the complete ETL pipeline with a sample receipt.
    """
    print("=" * 80)
    print("🧪 Testing Smart Finance Intelligence System ETL Pipeline")
    print("=" * 80)
    print()
    
    # Initialize ETL pipeline
    print("📋 Step 1: Initializing ETL pipeline...")
    etl = ReceiptETL(api_key=api_key, db_path="test_finance.db")
    print("✅ ETL pipeline initialized with database: test_finance.db")
    print()
    
    # Extract data from receipt
    print("📋 Step 2: Extracting data from receipt image...")
    print(f"   Image path: {image_path}")
    raw_data = etl.extract_receipt_data(image_path)
    
    if raw_data:
        print("✅ Data extraction successful!")
        print()
        print("📊 Raw Extracted Data:")
        print(json.dumps(raw_data, indent=2))
        print()
    else:
        print("❌ Data extraction failed!")
        return False
    
    # Transform data
    print("📋 Step 3: Validating and transforming data...")
    clean_data = etl.validate_and_transform(raw_data)
    print("✅ Data validation successful!")
    print()
    print("📊 Cleaned Data:")
    print(json.dumps(clean_data, indent=2))
    print()
    
    # Load to database
    print("📋 Step 4: Loading data to database...")
    transaction_id = etl.load_to_database(clean_data)
    print(f"✅ Data loaded successfully! Transaction ID: {transaction_id}")
    print()
    
    # Test analytics
    print("📋 Step 5: Running analytics queries...")
    analytics = FinanceAnalytics(db_path="test_finance.db")
    
    # Get KPIs
    now = datetime.now()
    kpis = analytics.get_monthly_kpis(now.year, now.month)
    print("📊 Monthly KPIs:")
    print(f"   Total Spend: ${kpis['total_spend']:.2f}")
    print(f"   Top Category: {kpis['top_category']}")
    print(f"   Top Category Amount: ${kpis['top_category_amount']:.2f}")
    print()
    
    # Get category breakdown
    categories = analytics.get_category_breakdown(now.year, now.month)
    print("📊 Category Breakdown:")
    for cat in categories:
        print(f"   {cat['category']}: ${cat['amount']:.2f}")
    print()
    
    # Get all transactions
    transactions = analytics.get_all_transactions(limit=5)
    print("📊 Recent Transactions:")
    for tx in transactions:
        date_flag = "⚠️" if tx['date_estimated'] else "✓"
        print(f"   {date_flag} {tx['date']} | {tx['merchant']} | ${tx['amount']:.2f} | {tx['category']}")
    print()
    
    print("=" * 80)
    print("✅ ETL Pipeline Test Completed Successfully!")
    print("=" * 80)
    
    return True


def demonstrate_search(api_key: str):
    """
    Demonstrate the search functionality.
    """
    print()
    print("=" * 80)
    print("🔍 Testing Search Functionality")
    print("=" * 80)
    print()
    
    analytics = FinanceAnalytics(db_path="test_finance.db")
    
    # Example searches
    search_terms = ["coffee", "grocery", "food"]
    
    for term in search_terms:
        print(f"🔎 Searching for: '{term}'")
        results = analytics.search_transactions(term)
        print(f"   Found {len(results)} result(s)")
        
        for r in results[:3]:  # Show max 3 results per search
            print(f"   • {r['merchant']} - {r['date']} - ${r['amount']:.2f}")
        print()


def main():
    """
    Main test function.
    """
    if len(sys.argv) < 3:
        print("Usage: python test_etl.py <receipt_image_path> <gemini_api_key>")
        print()
        print("Example:")
        print("  python test_etl.py sample_receipt.jpg YOUR_API_KEY")
        print()
        print("Get your Gemini API key from:")
        print("  https://makersuite.google.com/app/apikey")
        sys.exit(1)
    
    image_path = sys.argv[1]
    api_key = sys.argv[2]
    
    # Validate image exists
    import os
    if not os.path.exists(image_path):
        print(f"❌ Error: Image file not found: {image_path}")
        sys.exit(1)
    
    # Run tests
    success = test_receipt_processing(image_path, api_key)
    
    if success:
        demonstrate_search(api_key)
        print()
        print("💡 Next steps:")
        print("   1. Run 'streamlit run app.py' to see the full dashboard")
        print("   2. Upload more receipts to build your financial history")
        print("   3. Explore the analytics and visualizations")
        print()


if __name__ == "__main__":
    main()
