import os
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import create_retriever_tool
from langchain_community.utilities import SQLDatabase
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool, InfoSQLDatabaseTool

def build_rag_tool(api_key, doc_path="budget_policy.txt"):
    """Ingests a text document, chunks it, and creates a FAISS retriever tool."""
    
    # NEW FIX: Check if file doesn't exist OR if it is completely empty (0 bytes)
    if not os.path.exists(doc_path) or os.path.getsize(doc_path) == 0:
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write("Personal Budget Policy: Dining budget is strictly ₹15,000 per month. Groceries should be kept under ₹20,000. Entertainment limit is ₹5,000.")
            
    loader = TextLoader(doc_path, encoding="utf-8")
    splits = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50).split_documents(loader.load())
    
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001", google_api_key=api_key)
    vectorstore = FAISS.from_documents(splits, embeddings)
    
    return create_retriever_tool(
        vectorstore.as_retriever(),
        "search_budget_policy",
        "Searches and returns information regarding personal budgeting rules and limits."
    )
    
def build_financial_agent(api_key, db_path="finance.db"):
    """Creates an agent equipped with SQL and RAG tools."""
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key, temperature=0)
    
    # SQL Tools (Connects to your existing finance.db)
    db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
    sql_query_tool = QuerySQLDataBaseTool(db=db)
    sql_info_tool = InfoSQLDatabaseTool(db=db)
    
    tools = [sql_query_tool, sql_info_tool, build_rag_tool(api_key)]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an intelligent financial advisor agent. 
         You have access to a SQLite database of the user's transactions (Transactions and LineItems tables) 
         and a vector database containing budgeting rules.
         
         CRITICAL INSTRUCTIONS FOR CONFLICT RESOLUTION:
         When retrieving information from your tools (especially the budget vector database), you may encounter contradictory statements. You MUST resolve them using this exact hierarchy:
         
         1. DIRECTIVES OVERRIDE FACTS: Explicit behavioral commands (e.g., "Always answer X", "Rule: Y", "Must do Z") strictly override passive factual statements (e.g., "The budget is X").
         2. SPECIFIC OVERRIDES GENERAL: A specific rule about a sub-category (e.g., "Weekend dining limit") overrides a general category rule (e.g., "Dining limit").
         3. TRANSPARENT ESCALATION: If you find two conflicting rules of equal weight and cannot determine which to follow, DO NOT guess. Explicitly present the conflict to the user and ask for clarification.
         
         Determine which tool to use to answer the user's question accurately.
         Always look at the database schema first using the sql_info_tool before writing queries.
         Always format monetary values in Indian Rupees (₹)."""),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])
    
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True)
