# 💰 Smart Personal Finance Intelligence System

A production-grade GenAI application that transforms unstructured receipt images into structured financial insights using Google Gemini API, SQLite, and Streamlit.

## 🎯 Project Overview

This system demonstrates enterprise-level skills in:
- **GenAI & Prompt Engineering**: Robust system prompts for accurate OCR and semantic extraction
- **ETL Pipeline Design**: Extract, Transform, Load architecture for receipt processing
- **Database Design**: Normalized SQL schema optimized for analytics
- **Business Intelligence**: Interactive dashboards with KPIs and visualizations
- **Full Stack Development**: End-to-end Python application with UI

## 🏗️ Architecture

```
┌─────────────────┐
│  Receipt Image  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│   Gemini Vision API     │ ◄── System Prompt (Prompt Engineering)
│  (OCR + Extraction)     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Validation & Transform │
│  - Date normalization   │
│  - Category mapping     │
│  - Data cleaning        │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   SQLite Database       │
│  - Transactions table   │
│  - LineItems table      │
│  - Indexes for BI       │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Streamlit Dashboard    │
│  - KPI metrics          │
│  - Category breakdown   │
│  - Spending trends      │
│  - Transaction search   │
└─────────────────────────┘
```

## 🚀 Features

### 1. **AI-Powered Receipt Processing**
- Upload any receipt image (grocery, restaurant, retail, etc.)
- Gemini AI extracts structured data:
  - Merchant name
  - Transaction date
  - Total amount
  - Individual line items
  - Auto-categorized spending category
  - Confidence level

### 2. **Intelligent Data Pipeline (ETL)**
- **Extract**: Gemini Vision API with engineered system prompts
- **Transform**: Data validation, normalization, and enrichment
- **Load**: Optimized SQLite storage with analytics-ready schema

### 3. **Business Intelligence Dashboard**
- **KPI Metrics**:
  - Total spend this month
  - Top spending category
  - Category-specific totals
  
- **Visualizations**:
  - Category breakdown (donut chart)
  - Daily spending trend (bar chart)
  - Interactive, filterable charts

- **Search & Analytics**:
  - Full-text search across merchants and items
  - Transaction history with filters
  - Export capabilities

## 📋 Prerequisites

- Python 3.10 or higher
- Google Gemini API key ([Get one here](https://makersuite.google.com/app/apikey))
- 50MB free disk space

## ⚙️ Installation

### 1. Clone or Download the Project
```bash
# If you have the files, navigate to the directory
cd smart-finance-intelligence
```

### 2. Create Virtual Environment (Recommended)
```bash
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure API Key

**Option A: Environment Variable (Recommended)**
```bash
# Create .env file
cp .env.example .env

# Edit .env and add your API key
GEMINI_API_KEY=your_actual_api_key_here
```

**Option B: Enter in UI**
- Run the app and enter your API key in the web interface

## 🎮 Usage

### Start the Application
```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

### Workflow

1. **Upload Receipt**
   - Navigate to "📤 Upload Receipt"
   - Choose a receipt image (JPG, PNG, JPEG, WEBP)
   - Click "Process Receipt"
   - Wait for AI to extract data (5-10 seconds)

2. **View Dashboard**
   - Go to "📊 Dashboard"
   - Select month to analyze
   - View KPIs and visualizations

3. **Search Transactions**
   - Go to "🔍 Search Transactions"
   - Search by merchant or item name
   - Browse recent transactions

## 🧠 Prompt Engineering Deep Dive

### System Prompt Design Philosophy

The Gemini system prompt in `etl_pipeline.py` uses advanced techniques:

#### 1. **Role Assignment**
```
"You are an expert financial data extraction assistant specializing in receipt processing."
```
Establishes context and expected expertise level.

#### 2. **Strict Output Format Specification**
```json
{
  "merchant_name": "string",
  "date": "YYYY-MM-DD",
  ...
}
```
Prevents hallucinations and ensures parseable JSON.

#### 3. **Edge Case Handling**
- Missing dates → Default to current date + flag as estimated
- Ambiguous totals → Use largest value
- Unclear items → Extract top 10 most expensive

#### 4. **Chain-of-Thought Reasoning**
```
"Analyze the line items and merchant to classify into ONE of these categories..."
```
Guides the model to think before categorizing.

#### 5. **Few-Shot Learning**
Two complete examples (grocery + restaurant) teach the model:
- Expected output structure
- How to handle edge cases
- Category classification logic

#### 6. **Constraint Keywords**
- "CRITICAL REQUIREMENTS" → Non-negotiable rules
- "MUST" → Mandatory behaviors
- "EXACTLY" → Precision requirements

### Why This Works
- **High accuracy**: Clear examples reduce hallucinations
- **Consistency**: Strict schema ensures parseable output
- **Robustness**: Edge cases are explicitly handled
- **Maintainability**: Prompt is self-documenting

## 🗄️ Database Schema

### Transactions Table (Fact Table)
```sql
CREATE TABLE Transactions (
    id INTEGER PRIMARY KEY,
    merchant_name TEXT NOT NULL,
    transaction_date DATE NOT NULL,
    total_amount REAL NOT NULL,
    category TEXT NOT NULL,
    confidence TEXT,              -- Quality indicator
    date_estimated BOOLEAN,       -- Data quality flag
    created_at TIMESTAMP,
    receipt_processed_at TIMESTAMP
)
```

**Design Decisions**:
- `date_estimated` flag for data quality tracking
- `confidence` field for filtering low-quality extractions
- Indexes on `transaction_date` and `category` for fast BI queries

### LineItems Table (Dimension Table)
```sql
CREATE TABLE LineItems (
    id INTEGER PRIMARY KEY,
    transaction_id INTEGER,
    item_name TEXT NOT NULL,
    price REAL NOT NULL,
    quantity INTEGER DEFAULT 1,
    FOREIGN KEY (transaction_id) REFERENCES Transactions(id)
)
```

**Design Decisions**:
- Normalized to support item-level analytics
- Enables drill-down queries ("Show all coffee purchases")
- Cascade delete maintains referential integrity

## 📊 Sample Analytics Queries

```sql
-- Top 5 merchants by spend
SELECT merchant_name, SUM(total_amount) as total
FROM Transactions
GROUP BY merchant_name
ORDER BY total DESC
LIMIT 5;

-- Monthly spending trend
SELECT 
    strftime('%Y-%m', transaction_date) as month,
    SUM(total_amount) as total
FROM Transactions
GROUP BY month
ORDER BY month;

-- Most purchased items
SELECT item_name, COUNT(*) as frequency, AVG(price) as avg_price
FROM LineItems
GROUP BY item_name
ORDER BY frequency DESC
LIMIT 10;
```

## 🎨 Tech Stack Details

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **GenAI** | Google Gemini 1.5 Flash | OCR + semantic extraction |
| **Backend** | Python 3.10+ | Core application logic |
| **Database** | SQLite | Embedded SQL database |
| **ETL** | Custom pipeline | Data processing |
| **Frontend** | Streamlit | Interactive dashboard |
| **Visualization** | Plotly | Charts and graphs |
| **Data Analysis** | Pandas | Data manipulation |

## 🔒 Security & Best Practices

1. **API Key Management**
   - Use environment variables
   - Never commit `.env` to version control
   - `.env.example` template provided

2. **Data Validation**
   - All inputs validated before database insert
   - SQL injection protection via parameterized queries
   - Date normalization with fallbacks

3. **Error Handling**
   - Try-catch blocks around API calls
   - Graceful degradation on failures
   - User-friendly error messages

4. **Database Best Practices**
   - Foreign key constraints
   - Indexes on query columns
   - Transaction rollback on errors

## 📈 Performance Considerations

- **Database**: Indexes on `transaction_date` and `category` for sub-second BI queries
- **API**: Gemini 1.5 Flash model for speed (5-10s per receipt)
- **Caching**: Streamlit's `@st.cache_data` for expensive computations
- **Pagination**: Transaction list limited to prevent UI slowdowns

## 🧪 Testing Receipt Images

For best results, use receipt images with:
- ✅ Clear, high-resolution text
- ✅ Good lighting (no shadows)
- ✅ Flat, uncrumpled paper
- ✅ All four corners visible

Supported receipt types:
- Grocery stores
- Restaurants & cafes
- Gas stations
- Retail stores
- Online order confirmations (screenshots)

## 🐛 Troubleshooting

### "JSON parsing error"
- Receipt image quality too low
- Try a clearer image or better lighting

### "API Key Error"
- Verify your Gemini API key is correct
- Check API quota limits

### "No data in dashboard"
- Upload at least one receipt first
- Check selected month has transactions

### Database locked
- Close any other applications accessing `finance.db`
- Restart the Streamlit app

## 🚀 Future Enhancements

- [ ] Multi-currency support
- [ ] Budget alerts and notifications
- [ ] Export to CSV/Excel
- [ ] Mobile app version
- [ ] Integration with bank APIs
- [ ] Recurring transaction detection
- [ ] Predictive spending analytics
- [ ] Receipt archive with image storage

## 📝 Code Structure

```
smart-finance-intelligence/
├── app.py                 # Streamlit UI and dashboard
├── etl_pipeline.py        # Core ETL logic and analytics
├── requirements.txt       # Python dependencies
├── .env.example          # API key template
├── README.md             # This file
└── finance.db            # SQLite database (auto-created)
```

### Key Classes

**`ReceiptETL`** (`etl_pipeline.py`)
- `extract_receipt_data()`: Gemini API integration
- `validate_and_transform()`: Data cleaning
- `load_to_database()`: SQL insertion
- `process_receipt()`: Full ETL pipeline

**`FinanceAnalytics`** (`etl_pipeline.py`)
- `get_monthly_kpis()`: KPI calculations
- `get_category_breakdown()`: Spending by category
- `get_daily_spending()`: Time series data
- `search_transactions()`: Full-text search

## 🎓 Learning Outcomes

This project demonstrates:

1. **Prompt Engineering**
   - System prompt design
   - Few-shot learning
   - Output format enforcement
   - Edge case handling

2. **ETL Pipeline Design**
   - Extract: API integration
   - Transform: Data validation
   - Load: Database operations

3. **SQL & Database Design**
   - Normalized schema
   - Index optimization
   - Analytical queries

4. **Business Intelligence**
   - KPI definition
   - Data visualization
   - Interactive dashboards

5. **Full Stack Development**
   - Backend (Python)
   - Database (SQLite)
   - Frontend (Streamlit)
   - Deployment considerations

## 📄 License

This project is provided as-is for educational and portfolio purposes.

## 🤝 Contributing

This is a portfolio project, but suggestions are welcome! Feel free to:
- Report bugs
- Suggest features
- Improve documentation

## 📧 Contact

Built as a demonstration of Full Stack AI Engineering skills.

---

**Built with ❤️ using Python, GenAI, and modern data engineering practices.**
#   P e r s o n a l - F i n a n c e - I n t e l l i g e n c e - S y s t e m  
 