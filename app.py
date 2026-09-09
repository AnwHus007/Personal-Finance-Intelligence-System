import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
import os
from etl_pipeline import ReceiptETL, FinanceAnalytics
from agent_engine import build_financial_agent


# Page configuration
st.set_page_config(
    page_title="Smart Finance Intelligence",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .kpi-card {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .kpi-label {
        font-size: 0.9rem;
        color: #666;
        margin-top: 0.5rem;
    }
    </style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if 'analytics' not in st.session_state:
        st.session_state.analytics = FinanceAnalytics()
    if 'etl' not in st.session_state:
        # Check for API key
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            st.session_state.etl = None
        else:
            st.session_state.etl = ReceiptETL(api_key)
            
    # Add this to track receipts waiting for review
    if 'pending_receipt' not in st.session_state:
        st.session_state.pending_receipt = None

def upload_receipt_section():
    """Receipt upload and processing section."""
    st.header("📤 Upload Receipt")
    
    # API Key input if not in environment
    if not st.session_state.etl:
        st.warning("⚠️ Gemini API Key Required")
        api_key = st.text_input(
            "Enter your Google Gemini API Key",
            type="password",
            help="Get your API key from https://makersuite.google.com/app/apikey"
        )
        
        if api_key:
            try:
                st.session_state.api_key = api_key
                st.session_state.etl = ReceiptETL(api_key)
                st.success("✅ API Key configured!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error configuring API: {e}")
        
        st.info("""
        **How to get a Gemini API Key:**
        1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
        2. Click "Create API Key"
        3. Copy and paste the key above
        
        Alternatively, set the `GEMINI_API_KEY` environment variable.
        """)
        return
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Choose a receipt image",
        type=["png", "jpg", "jpeg", "webp"],
        help="Upload a clear image of your receipt"
    )
    
    if uploaded_file is not None:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.image(uploaded_file, caption="Uploaded Receipt", use_container_width=True)
        
        with col2:
            # STATE 1: No receipt extracted yet -> Show process button
            if st.session_state.pending_receipt is None:
                if st.button("🔍 Process Receipt", type="primary", use_container_width=True):
                    with st.spinner("🤖 AI is analyzing your receipt..."):
                        temp_path = f"temp_receipt_{datetime.now().timestamp()}.jpg"
                        with open(temp_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        try:
                            # Step 1 & 2: Extract and Transform only
                            raw_data = st.session_state.etl.extract_receipt_data(temp_path)
                            if raw_data:
                                clean_data = st.session_state.etl.validate_and_transform(raw_data)
                                # Save to state and refresh to show the edit form
                                st.session_state.pending_receipt = clean_data
                                st.rerun()
                            else:
                                st.error("❌ Failed to extract data.")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                        finally:
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
            
            # STATE 2: Receipt extracted -> Show edit form
            else:
                st.subheader("📝 Review and Edit Data")
                data = st.session_state.pending_receipt
                
                with st.form("edit_receipt_form"):
                    # Basic Fields
                    merchant = st.text_input("Merchant Name", value=data.get("merchant_name", ""))
                    
                    # Handle date conversion safely
                    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
                    try:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except ValueError:
                        date_obj = datetime.now().date()
                    
                    date_val = st.date_input("Date", value=date_obj)
                    amount_val = st.number_input("Total Amount", value=float(data.get("total_amount", 0.0)), format="%.2f")
                    
                    # Category dropdown
                    categories = ["Groceries", "Dining", "Transportation", "Utilities", "Healthcare", "Entertainment", "Shopping", "Other"]
                    cat_index = categories.index(data.get("category")) if data.get("category") in categories else 7
                    category_val = st.selectbox("Category", options=categories, index=cat_index)
                    
                    st.markdown("**Line Items**")
                    
                    # Interactive table for line items
                    items_df = pd.DataFrame(data.get("line_items", []))
                    if items_df.empty:
                        items_df = pd.DataFrame(columns=["item_name", "price", "quantity"])
                        
                    edited_items_df = st.data_editor(
                        items_df, 
                        num_rows="dynamic", 
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    # Form Buttons
                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        submitted = st.form_submit_button("💾 Save to Database", type="primary", use_container_width=True)
                    with col_cancel:
                        cancelled = st.form_submit_button("❌ Cancel", use_container_width=True)
                        
                    if submitted:
                        # Repackage the edited data
                        final_data = {
                            "merchant_name": merchant,
                            "date": date_val.strftime("%Y-%m-%d"),
                            "total_amount": amount_val,
                            "category": category_val,
                            "confidence": data.get("confidence", "medium"),
                            "date_estimated": data.get("date_estimated", False),
                            "line_items": edited_items_df.to_dict('records')
                        }
                        
                        # Step 3: Load to Database
                        tx_id = st.session_state.etl.load_to_database(final_data)
                        
                        # Clear state and celebrate
                        st.session_state.pending_receipt = None
                        st.success(f"✅ Transaction {tx_id} saved successfully!")
                        st.balloons()
                        
                    if cancelled:
                        st.session_state.pending_receipt = None
                        st.rerun()


def dashboard_section():
    """Main BI dashboard section."""
    st.header("📊 Financial Intelligence Dashboard")
    
    # Date selector
    col1, col2 = st.columns([1, 3])
    with col1:
        selected_month = st.date_input(
            "Select Month",
            value=datetime.now(),
            help="View analytics for a specific month"
        )
    
    year = selected_month.year
    month = selected_month.month
    
    # Get KPIs
    kpis = st.session_state.analytics.get_monthly_kpis(year, month)
    
    # KPI Cards
    st.subheader("📈 Key Metrics")
    kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
    
    with kpi_col1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">${kpis['total_spend']:,.2f}</div>
            <div class="kpi-label">Total Spend This Month</div>
        </div>
        """, unsafe_allow_html=True)
    
    with kpi_col2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">{kpis['top_category']}</div>
            <div class="kpi-label">Top Spending Category</div>
        </div>
        """, unsafe_allow_html=True)
    
    with kpi_col3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-value">${kpis['top_category_amount']:,.2f}</div>
            <div class="kpi-label">Top Category Amount</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Visualizations
    viz_col1, viz_col2 = st.columns(2)
    
    # Category Breakdown (Donut Chart)
    with viz_col1:
        st.subheader("💳 Category Breakdown")
        category_data = st.session_state.analytics.get_category_breakdown(year, month)
        
        if category_data:
            df_categories = pd.DataFrame(category_data)
            
            fig_donut = go.Figure(data=[go.Pie(
                labels=df_categories['category'],
                values=df_categories['amount'],
                hole=0.4,
                marker=dict(
                    colors=px.colors.qualitative.Set3,
                    line=dict(color='white', width=2)
                ),
                textposition='inside',
                textinfo='label+percent',
                hovertemplate='<b>%{label}</b><br>$%{value:.2f}<br>%{percent}<extra></extra>'
            )])
            
            fig_donut.update_layout(
                showlegend=True,
                height=400,
                margin=dict(t=20, b=20, l=20, r=20),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.2,
                    xanchor="center",
                    x=0.5
                )
            )
            
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("No data available for this period")
    
    # Daily Spending Trend (Bar Chart)
    with viz_col2:
        st.subheader("📅 Daily Spending Trend")
        daily_data = st.session_state.analytics.get_daily_spending(year, month)
        
        if daily_data:
            df_daily = pd.DataFrame(daily_data)
            
            fig_bar = go.Figure(data=[go.Bar(
                x=df_daily['date'],
                y=df_daily['amount'],
                marker=dict(
                    color=df_daily['amount'],
                    colorscale='Blues',
                    line=dict(color='rgb(8,48,107)', width=1.5)
                ),
                hovertemplate='<b>%{x}</b><br>$%{y:.2f}<extra></extra>'
            )])
            
            fig_bar.update_layout(
                xaxis_title="Date",
                yaxis_title="Amount ($)",
                height=400,
                margin=dict(t=20, b=60, l=60, r=20),
                hovermode='x unified'
            )
            
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No data available for this period")


def transaction_search_section():
    """Transaction search and history section."""
    st.header("🔍 Transaction Search")
    
    # Search bar
    search_col1, search_col2 = st.columns([3, 1])
    with search_col1:
        search_term = st.text_input(
            "Search transactions",
            placeholder="e.g., coffee, Walmart, groceries...",
            help="Search by merchant name or item name"
        )
    
    with search_col2:
        search_button = st.button("Search", type="primary", use_container_width=True)
    
    # Display results
    if search_term and search_button:
        results = st.session_state.analytics.search_transactions(search_term)
        
        if results:
            st.success(f"Found {len(results)} matching transaction(s)")
            df_results = pd.DataFrame(results)
            df_results['amount'] = df_results['amount'].apply(lambda x: f"${x:.2f}")
            
            st.dataframe(
                df_results,
                column_config={
                    "id": "ID",
                    "merchant": "Merchant",
                    "date": "Date",
                    "amount": "Amount",
                    "category": "Category"
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.warning("No transactions found matching your search.")
    
    # Recent transactions
    st.subheader("📜 Recent Transactions")
    limit = st.slider("Number of transactions to display", 5, 50, 20)
    
    transactions = st.session_state.analytics.get_all_transactions(limit=limit)
    
    if transactions:
        df_transactions = pd.DataFrame(transactions)
        df_transactions['amount'] = df_transactions['amount'].apply(lambda x: f"${x:.2f}")
        df_transactions['date_estimated'] = df_transactions['date_estimated'].apply(
            lambda x: "⚠️ Yes" if x else "No"
        )
        
        st.dataframe(
            df_transactions,
            column_config={
                "id": "ID",
                "merchant": "Merchant",
                "date": "Date",
                "amount": "Amount",
                "category": "Category",
                "confidence": "Confidence",
                "date_estimated": "Date Estimated"
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("No transactions yet. Upload a receipt to get started!")

def ai_advisor_section():
    """Chat interface for the Agentic Financial Advisor."""
    st.header("💬 AI Financial Advisor")
    st.markdown("Ask complex questions about your spending or budget policies!")
    
    if not st.session_state.etl:
        st.warning("⚠️ Gemini API Key Required. Please configure it in the 'Upload Receipt' tab.")
        return

    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
        
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
    if prompt := st.chat_input("E.g., I just spent ₹4,500 on dinner. Am I still within my monthly budget?"):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            with st.spinner("Analyzing data and querying tools..."):
                try:
                    # Retrieve the API key from environment or the ETL session state
                    api_key = os.getenv("GEMINI_API_KEY")
                    # If it's not in the environment, check if it's in the Streamlit session state
                    if not api_key and 'api_key' in st.session_state:
                        api_key = st.session_state.api_key
                        
                    # If we still don't have it, stop and warn the user
                    if not api_key:
                        st.error("⚠️ Gemini API Key not found. Please ensure it is set as an environment variable (GEMINI_API_KEY) or entered in the setup tab.")
                        st.stop()
                    agent = build_financial_agent(api_key)
                    response = agent.invoke({"input": prompt})
                    
                    # Get the raw output
                    raw_answer = response.get("output", "")
                    
                    # Parse the output if it comes back as a list of dictionaries
                    if isinstance(raw_answer, list) and len(raw_answer) > 0 and isinstance(raw_answer[0], dict):
                        answer = raw_answer[0].get('text', str(raw_answer))
                    else:
                        # Fallback just in case the agent returns a standard string later
                        answer = str(raw_answer)
                    
                    st.markdown(answer)                    
                    st.session_state.chat_messages.append({"role": "assistant", "content": answer})
                except Exception as e:
                    st.error(f"Agent encountered an error: {e}")
def main():
    """Main application entry point."""
    # Initialize
    init_session_state()
    
    # Header
    st.markdown('<h1 class="main-header">💰 Smart Personal Finance Intelligence System</h1>', 
                unsafe_allow_html=True)
    
    st.markdown("""
    Transform your receipts into actionable financial insights using AI-powered OCR and analytics.
    """)
    
    # Sidebar navigation
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/money-bag.png", width=80)
        st.title("Navigation")
        
        page = st.radio(
            "Go to",
            ["📊 Dashboard", "📤 Upload Receipt", "🔍 Search Transactions", "💬 AI Advisor"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.markdown("""
        ### About
        This system uses:
        - **Google Gemini AI** for receipt OCR
        - **SQLite** for data storage
        - **Streamlit** for visualization
        
        ### Tech Stack
        - Python 3.10+
        - Gemini 2.5 Flash
        - Plotly for charts
        - Pandas for data analysis
        """)
        
        st.markdown("---")
        st.caption("Built with ❤️ using GenAI")
    
    # Route to selected page
    if page == "📊 Dashboard":
        dashboard_section()
    elif page == "📤 Upload Receipt":
        upload_receipt_section()
    elif page == "🔍 Search Transactions":
        transaction_search_section()
    elif page == "💬 AI Advisor":
        ai_advisor_section()

if __name__ == "__main__":
    main()
