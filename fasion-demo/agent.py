# agent.py - Enhanced AI-Driven E-commerce Assistant

import os
import configparser
import urllib3
import ssl
import json
import re
import traceback
from datetime import datetime, timedelta
from decimal import Decimal
from hdbcli import dbapi
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import ToolMessage, SystemMessage, AIMessage, HumanMessage, AIMessageChunk, AnyMessage
from langgraph.prebuilt import create_react_agent, ToolNode, tools_condition
from langgraph.graph.message import add_messages
from urllib.parse import quote
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from ecom_llm import google_generative_ai_llm as llm
from ecom_llm import get_google_embedding as get_embedding
import hana_ml
from langgraph.graph import StateGraph, START, END
from langchain_core.tools import tool
from typing import List, Literal, Optional, Union
from typing_extensions import TypedDict, Annotated
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableConfig
from langchain_core.chat_history import InMemoryChatMessageHistory
import memory_store
from memory_store import SessionMemory
import requests
from promotion_helper import get_product_with_promotion, get_active_promotion, calculate_discounted_price

def get_cross_sell_products_for_search(product_ids: list, conn, cursor, limit_per_product=2) -> list:
    """
    Fetch cross-sell products for given product IDs from search results.
    Returns combined cross-sell products with promotion data.
    """
    try:
        if not product_ids:
            return []
        
        # Clean and prepare product IDs
        product_ids_clean = [str(pid).strip() for pid in product_ids if pid]
        if not product_ids_clean:
            return []
        
        print(f"🔗 Fetching cross-sell products for {len(product_ids_clean)} source products")
        
        # Get current date for active promotions
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Build query to get cross-sell products with promotions
        placeholders = ','.join(['?' for _ in product_ids_clean])
        
        sql = f"""
            SELECT DISTINCT
                p.PRODUCT_ID, p.PRODUCT_NAME, p.SUMMARY, p.PRICE, p.IMAGE_URL,
                cs.SOURCE_PRODUCT_ID, cs.RELATIONSHIP_TYPE, cs.PRIORITY,
                promo.PROMO_ID, promo.PROMO_TITLE, promo.PROMO_DISCOUNT_PERCENT,
                CASE 
                    WHEN promo.PROMO_DISCOUNT_PERCENT IS NOT NULL 
                    THEN p.PRICE * (1 - promo.PROMO_DISCOUNT_PERCENT / 100.0)
                    ELSE p.PRICE
                END AS FINAL_PRICE
            FROM SAP_PRODUCT_CROSS_SELL_V2 cs
            JOIN SAP_PRODUCTS_COMMERCE_2211_V2 p 
                ON TRIM(cs.CROSS_SELL_PRODUCT_ID) = TRIM(p.PRODUCT_ID)
            LEFT JOIN SAP_PROMOTION_COMMERCE_2211_V2 promo 
                ON TRIM(p.PRODUCT_ID) = TRIM(promo.PROMO_PRODUCT_ID)
                AND promo.PROMO_START_DATE <= '{today}'
                AND promo.PROMO_END_DATE >= '{today}'
            WHERE TRIM(cs.SOURCE_PRODUCT_ID) IN ({placeholders})
            ORDER BY cs.PRIORITY, p.PRICE DESC
        """
        
        cursor.execute(sql, product_ids_clean)
        rows = cursor.fetchall()
        
        print(f"📦 Found {len(rows)} cross-sell products")
        
        cross_sell_products = []
        seen_product_ids = set()
        
        for row in rows:
            cross_sell_id = str(row[0]).strip() if row[0] else ""
            
            # Avoid duplicates
            if cross_sell_id in seen_product_ids or cross_sell_id in product_ids_clean:
                continue
            
            seen_product_ids.add(cross_sell_id)
            
            # Limit per source product
            if len(cross_sell_products) >= limit_per_product * len(product_ids_clean):
                break
            
            product_name = row[1] if row[1] else ""
            summary = row[2] if row[2] else ""
            original_price = float(row[3]) if row[3] else 0.0
            image_url = row[4] if row[4] else ""
            source_id = row[5] if row[5] else ""
            rel_type = row[6] if row[6] else "cross-sell"
            priority = row[7] if row[7] else 1
            promo_id = row[8]
            promo_title = row[9] if row[9] else ""
            discount_percent = float(row[10]) if row[10] else 0
            final_price = float(row[11]) if row[11] else original_price
            
            has_promotion = promo_id is not None and discount_percent > 0
            
            # Calculate discounted price using promotion_helper for consistency
            if has_promotion:
                calculated_discount_price = calculate_discounted_price(original_price, discount_percent)
                savings_amount = round(original_price - calculated_discount_price, 2)
            else:
                calculated_discount_price = original_price
                savings_amount = 0
            
            cross_sell_products.append({
                "product_id": cross_sell_id,  # lowercase for frontend
                "product_name": product_name,  # lowercase for frontend
                "summary": summary,  # lowercase for frontend
                "price": calculated_discount_price,  # Use calculated discount price as the display price
                "image_url": image_url,  # lowercase for frontend
                "PRODUCT_ID": cross_sell_id,  # Keep uppercase for backend compatibility
                "PRODUCT_NAME": product_name,
                "SUMMARY": summary,
                "PRICE": original_price,  # Keep PRICE as original for frontend calculations
                "IMAGE_URL": image_url,
                "SOURCE_PRODUCT_ID": source_id,
                "RELATIONSHIP_TYPE": rel_type,
                "PRIORITY": priority,
                "has_promotion": has_promotion,
                "original_price": original_price,
                "discount_percent": discount_percent,
                "discounted_price": calculated_discount_price,
                "savings": savings_amount,
                "promo_title": promo_title
            })
        
        print(f"✅ Returning {len(cross_sell_products)} unique cross-sell products")
        return cross_sell_products
        
    except Exception as e:
        print(f"❌ Error fetching cross-sell products: {e}")
        import traceback
        print(traceback.format_exc())
        return []

config_properties = configparser.ConfigParser()
config_properties.read('config.ini')
cert_path=os.path.join(os.path.dirname(__file__), 'certs', 'VM_hybris.crt')

memory= SessionMemory()

# 🎯 Session product cache: stores product_data per session_id OUTSIDE LangGraph memory
# This prevents PRODUCT_CONTEXT_DATA from leaking into LLM conversation history
_session_products = {}  # session_id -> list of product dicts

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context
class SearchInput(BaseModel):
    query:str = Field(description="input required for the tool, e.g., user's query or customer_id or order_id")

class AgentState(TypedDict):
    """The state of the agent."""
    messages: Annotated[list, add_messages]
    nextnode: str
    number_of_steps: int

# Load the configuration file
configParser = configparser.ConfigParser()
configParser.read('config.ini')
pdp_url = configParser['DEFAULT']['PDP_URL']
# -----------------------------------------------
# Helper: SAP HANA Connection
# -----------------------------------------------
def hana_connect():
    """
    Establish a connection to SAP HANA Vector DB using environment variables.
    Ensure that HANA_HOST, HANA_PORT, HANA_USER, and HANA_PASSWORD are set.
    """
    conn = dbapi.connect(
        address='794d7a51-4a96-4b97-a476-dacb3a0440b4.hna2.prod-eu10.hanacloud.ondemand.com',
        port='443',
        user='00F588CD78904954BA0FA8C9585A169F_8C04J77WXE7NPHALBEVGEC4AA_DT',
        password='Ae7Z34V2HG_8_j8r1kb_dWJsCGEnmE_nN0Z0cMULba.EdRcYbilznUf.bsX-ZJJ9q.9_13It90i_q3n8jSzE8zF_gfHbwEuE9LJos0bENwD2Q6YJjo_TlBICY23muSi.',
        encrypt=True,
        autocommit=True,
        sslValidateCertificate=False,
    )
    return conn

#------------------------------------------------
# SCHEMAS
#------------------------------------------------
class categorySchema(BaseModel):
    """
    A schema representing a product category.
    """
    category_id: str = Field(description="Unique identifier for the category (e.g. CATEGORY_ID)")
    category_name: str = Field(description="Human-readable category name")
    # response_text: Optional[str] = Field(description="Optional free-text explanation or summary about the category")

class productSchema(BaseModel):
    """
    A schema representing a product's details.
    """
    response_type: Literal["product"] = Field(description="The type of response this schema represents")
    ai_response: Optional[str] = Field(description="Response generated by the AI for the query")
    product_id: str = Field(description="Unique product identifier (e.g. PRODUCT_ID)")
    product_name: str = Field(description="Product display name")
    summary: str = Field(description="Short product summary or description")
    price: float = Field(description="Product price as a float in the store currency")
    image_url: str = Field(description="URL to the product image; must be returned for every product result")
    category: List[categorySchema] = Field(description="List of category objects the product belongs to")
    # response_text: Optional[str] = Field( description="Optional preformatted response text for this product")

class productsListSchema(BaseModel):
    """
    A schema representing a list of products.
    """
    response_type: Literal["products_list"] = Field(description="The type of response this schema represents")
    ai_response: Optional[str] = Field(description="Response generated by the AI for the query")
    products: List[productSchema] = Field(description="List of product objects matching the search criteria")

class customerSchema(BaseModel):
    """
    A schema representing a customer's details.
    """
    customer_id: str = Field(description="Customer identifier (e.g. email or customer number)")
    customer_name: str = Field(description="Full name of the customer")
    gender: str = Field(description="Customer gender, if available")
    age: int = Field(description="Customer age in years")
    # response_text: Optional[str] = Field( description="Optional free-text about the customer")

class orderSchema(BaseModel):
    """
    A schema representing a particular order details.
    """
    response_type: Literal["order"] = Field(description="The type of response this schema represents")
    ai_response: Optional[str] = Field(description="Response generated by the AI for the query")
    order_id: str = Field(description="Unique order identifier")
    order_date: str = Field(description="Order date (ISO format preferred, e.g. YYYY-MM-DD)")
    order_status: str = Field(description="Status of the order (e.g. COMPLETED, SHIPPED)")
    total_price: float = Field(description="Total order price as a float in the store currency")
    product: productSchema = Field(description="Product details for the order")
    customer: customerSchema = Field(description="Customer details for the order")
    # response_text: Optional[str] = Field( description="Optional preformatted response text for this order")

class orderHistorySchema(BaseModel):
    """
    A schema representing a customer's order history.
    """
    response_type: Literal["order_history"] = Field(description="The type of response this schema represents")
    ai_response: Optional[str] = Field(description="Response generated by the AI for the query")
    orders: List[orderSchema] = Field(description="List of orders in the customer's order history")

class FinalResponse(BaseModel):
    final_output: Union[categorySchema, productsListSchema, productSchema, customerSchema, orderSchema, orderHistorySchema, str]
#------------------------------------------------
# SCHEMAS
#------------------------------------------------

# -----------------------------------------------
# Tool Function Implementations
# -----------------------------------------------
@tool("query_orders", args_schema=SearchInput, return_direct=True, description="Queries the SAP_ORDERS_COMMERCE_2211_V2 Input: SQL QUERY to fetch the order details "
      "Order_ID in the sql query should be inside inverted commas example: '1234'."
        "Assumes the SAP_ORDERS_COMMERCE_2211_V2 table has the columns: ORDER_ID, CUSTOMER_ID, ORDER_DATE, TOTAL_PRICE, PRODUCT_ID, ORDER_STATUS, PRODUCT_NAME, VECTOR_PRODUCT_NAME. "
        "For additional customer details, join with the SAP_CUSTOMER_COMMERCE_2211 having columns: CUSTOMER_NAME,CUSTOMER_ID,GENDER,AGE"
        "Assume Customer_ID contains customer's email"
        "For additional product details, join with the SAP_PRODUCTS_COMMERCE_2211_V2 table having columns: PRODUCT_ID,PRODUCT_NAME,SUMMARY,PRICE,CATEGORY_IDs,IMAGE_URL"
        "For additional category details, join with the SAP_CATEGORIES_COMMERCE_2211_V2 table having columns: CATEGORY_NAME,CATEGORY_ID")
def query_orders(query: str) -> dict:
    """
    Query the SAP_ORDERS_COMMERCE_2211_V2 table based on the user's query.
    """
    print(f"Querying orders with SQL: {query}")  # Debugging output
    try:
        conn = hana_connect()
        cursor = conn.cursor()
        # Dynamically generate SQL based on the query
        # sql = f"SELECT * FROM ORDERS WHERE {query}"
        cursor.execute(query)
        rows = cursor.fetchall()
        # Extract column names from cursor description
        columns = [col[0] for col in cursor.description] if cursor.description else []
        # Convert rows (tuples) to list of dicts keyed by column name
        results = [dict(zip(columns, row)) for row in rows] if rows else []
        cursor.close()
        conn.close()
        return {"results": results}
    except Exception as e:
        return {"error": f"Error querying orders: {str(e)}"}

@tool("get_orders_by_status", args_schema=SearchInput, return_direct=True, description=
      "SMART ORDER FILTERING tool that intelligently handles order queries with status filtering."
      "USAGE: Use for ANY order query that mentions a specific status or filter:"
      "• 'show my approved orders' → filters for APPROVED status"
      "• 'show my pending orders' → filters for OPEN status" 
      "• 'show my completed orders' → filters for COMPLETED status"
      "• 'show my ready orders' → filters for READY status"
      "• 'show orders on hold' → filters for ON_HOLD status"
      "INTELLIGENT: Automatically detects status keywords and maps them to database values"
      "Available statuses: APPROVED, OPEN, COMPLETED, READY, ON_HOLD, CREATED, CHECKED_VALID"
      "Input: Natural language query mentioning order status (e.g., 'show my approved orders')"
      "AUTO-AUTHENTICATION: Uses customer context automatically - no manual email needed")
def get_orders_by_status(query: str) -> dict:
    """
    Smart order filtering tool that handles status-based order queries intelligently.
    Automatically detects status keywords and filters orders accordingly.
    """
    try:
        # Extract customer context from the process_query function context
        import os
        
        # Try to get customer_id from environment (set by process_query)
        customer_id = os.environ.get('CURRENT_CUSTOMER_ID', '')
        if not customer_id:
            # Fallback: Try to extract from query if provided
            import re
            email_match = re.search(r'Customer ID:\s*([^\s]+)', query)
            if email_match:
                customer_id = email_match.group(1)
        
        # Enhanced authentication check
        if not customer_id or customer_id.strip() == '':
            print("DEBUG: get_orders_by_status - No customer authentication")
            return {
                "error": "Authentication required",
                "ai_response": """
                <div style='padding: 25px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; color: white; font-family: Arial, sans-serif; box-shadow: 0 4px 15px rgba(0,0,0,0.2); margin: 10px 0;'>
                    <div style='display: flex; align-items: center; margin-bottom: 15px;'>
                        <div style='background: rgba(255,255,255,0.2); border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; margin-right: 15px; font-size: 20px;'>
                            LOGIN REQUIRED
                        </div>
                        <h3 style='margin: 0; font-size: 18px; font-weight: 600;'>Login Required</h3>
                    </div>
                    <p style='margin: 0 0 15px 0; font-size: 14px; line-height: 1.5; opacity: 0.9;'>
                        To view your orders, please log in to your account first.
                    </p>
                    <div style='background: rgba(255,255,255,0.1); padding: 12px; border-radius: 8px; font-size: 13px;'>
                        <strong>Tip:</strong> Enter your email address in the login field above to access your orders.
                    </div>
                </div>
                """,
                "results": []
            }
        
        # Intelligent status detection
        status_mapping = detect_order_status_from_query(query)
        
        # Build dynamic SQL query based on detected status
        sql_query = build_order_status_query(customer_id, status_mapping)
        
        # Execute the query
        conn = hana_connect()
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        
        # Process results
        columns = [col[0] for col in cursor.description] if cursor.description else []
        results = [dict(zip(columns, row)) for row in rows] if rows else []
        
        cursor.close()
        conn.close()
        
        return {"results": results, "status_filter": status_mapping}
        
    except Exception as e:
        print(f"ERROR in get_orders_by_status: {str(e)}")
        return {"error": f"Error retrieving filtered orders: {str(e)}"}

def detect_order_status_from_query(query: str) -> dict:
    """
    Intelligently detect order status filters from natural language query
    """
    query_lower = query.lower()
    
    # Status keyword mapping
    status_keywords = {
        'approved': ['approved', 'approve'],
        'open': ['open', 'pending', 'new'],
        'completed': ['completed', 'complete', 'finished', 'done'],
        'ready': ['ready', 'prepared'],
        'on_hold': ['hold', 'on hold', 'on_hold', 'waiting', 'paused'],
        'created': ['created', 'new'],
        'checked_valid': ['checked', 'valid', 'verified']
    }
    
    detected_status = None
    confidence = 'low'
    
    # Check for exact status matches
    for db_status, keywords in status_keywords.items():
        for keyword in keywords:
            if keyword in query_lower:
                detected_status = db_status.upper()
                confidence = 'high'
                print(f"DEBUG: Detected status '{detected_status}' from keyword '{keyword}'")
                break
        if detected_status:
            break
    
    return {
        'status': detected_status,
        'confidence': confidence,
        'is_filtered': detected_status is not None,
        'original_query': query
    }

def build_order_status_query(customer_id: str, status_mapping: dict) -> str:
    """
    Build SQL query with optional status filtering
    """
    base_query = """
        SELECT o.ORDER_ID, o.ORDER_DATE, o.ORDER_STATUS, o.PRODUCT_NAME, o.TOTAL_PRICE, 
               o.PRODUCT_ID, p.IMAGE_URL
        FROM SAP_ORDERS_COMMERCE_2211_V2 o
        LEFT JOIN SAP_PRODUCTS_COMMERCE_2211_V2 p ON o.PRODUCT_ID = p.PRODUCT_ID
        WHERE o.CUSTOMER_ID = '{customer_id}'
    """
    
    # Add status filter if detected
    if status_mapping['is_filtered'] and status_mapping['status']:
        base_query += f" AND UPPER(o.ORDER_STATUS) = '{status_mapping['status']}'"
        print(f"DEBUG: Added status filter for: {status_mapping['status']}")
    
    base_query += " ORDER BY o.ORDER_DATE DESC"
    
    return base_query.format(customer_id=customer_id)

@tool("get_order_history", args_schema=SearchInput, return_direct=True, description=
      "🛍️ PRIMARY TOOL for showing customer's personal ORDER HISTORY and past purchases!"
      "🎯 USE THIS TOOL when user asks about THEIR orders, purchase history, or past orders!"
      "📝 TRIGGER KEYWORDS: 'my orders', 'show my orders', 'order history', 'my purchases', 'view my orders', 'my past orders', 'show orders', 'list my orders'"
      "⚡ IMMEDIATE USE for: 'show my orders', 'what are my orders', 'order history', 'my order history', 'view orders'"
      "🚫 DO NOT USE for product searches like 'show jackets' or 'show tshirts' - those use ai_semantic_product_search!"
      "✅ CRITICAL RULE: If query contains 'my orders' or 'order history' → USE THIS TOOL IMMEDIATELY!"
      "🔐 Automatically handles customer authentication and fetches order details with images."
      "Returns: Complete order history with ORDER_ID, ORDER_DATE, PRODUCT_NAME, PRICE, STATUS, IMAGE_URL")
def get_order_history(query: str) -> dict:
    """
    Retrieve order history for a given customer ID.
    Enhanced with proper authentication handling and automatic IMAGE_URL inclusion.
    """
    print(f"DEBUG: get_order_history called with query: {query}")
    
    try:
        # Check for customer authentication from environment
        import os
        customer_id = os.environ.get('CURRENT_CUSTOMER_ID', '')
        
        # Enhanced authentication check
        if not customer_id or customer_id.strip() == '':
            print("DEBUG: get_order_history - No customer authentication")
            return {
                "error": "Authentication required",
                "ai_response": """
                <div style='padding: 25px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; color: white; font-family: Arial, sans-serif; box-shadow: 0 4px 15px rgba(0,0,0,0.2); margin: 10px 0;'>
                    <div style='display: flex; align-items: center; margin-bottom: 15px;'>
                        <div style='background: rgba(255,255,255,0.2); border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; margin-right: 15px; font-size: 20px;'>
                            LOGIN REQUIRED
                        </div>
                        <h3 style='margin: 0; font-size: 18px; font-weight: 600;'>Login Required</h3>
                    </div>
                    <p style='margin: 0 0 15px 0; font-size: 14px; line-height: 1.5; opacity: 0.9;'>
                        To view your order history, please log in to your account first.
                    </p>
                    <div style='background: rgba(255,255,255,0.1); padding: 12px; border-radius: 8px; font-size: 13px;'>
                        <strong>Tip:</strong> Enter your email address in the login field above to access your orders.
                    </div>
                </div>
                """,
                "results": []
            }
        
        conn = hana_connect()
        cursor = conn.cursor()
        
        # Instead of executing the LLM-generated query directly, use a fixed query that ensures IMAGE_URL is included
        # This guarantees images will always be available in order history
        # IMPORTANT: Use TRIM() to handle trailing spaces in PRODUCT_ID
        fixed_query = """
            SELECT o.ORDER_ID, o.ORDER_DATE, o.ORDER_STATUS, o.PRODUCT_NAME, o.TOTAL_PRICE, 
                   o.PRODUCT_ID, p.IMAGE_URL
            FROM SAP_ORDERS_COMMERCE_2211_V2 o
            LEFT JOIN SAP_PRODUCTS_COMMERCE_2211_V2 p ON TRIM(o.PRODUCT_ID) = TRIM(p.PRODUCT_ID)
            WHERE o.CUSTOMER_ID = ?
            ORDER BY o.ORDER_DATE DESC
        """
        
        print(f"DEBUG: Executing order history SQL with customer_id: {customer_id}")
        cursor.execute(fixed_query, (customer_id,))
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description] if cursor.description else []
        
        # Create results with lowercase keys for JavaScript compatibility
        results = []
        for row in rows:
            order_dict = dict(zip(columns, row))
            # Convert keys to lowercase for frontend compatibility
            lowercase_order = {key.lower(): value for key, value in order_dict.items()}
            results.append(lowercase_order)
        
        cursor.close()
        conn.close()
        return {"results": results}
    except Exception as e:
        print(f"ERROR in get_order_history: {str(e)}")
        return {"error": f"Error retrieving order history: {str(e)}"}
    
@tool("get_product_details", args_schema=SearchInput, return_direct=True, description=
       "Gets detailed information for a specific product by Product ID. Use this when user asks for details about a specific product or clicks on a product."
        "Input: Query containing product ID (e.g., 'Show me detailed information about product 99146' or 'Tell me about product 300123456') "
        "Extracts the product ID from the query and returns comprehensive product details including name, description, price, categories, image, and related information.")
def get_product_details(query: str) -> dict:
    """
    Get detailed information for a specific product by Product ID.
    Extracts product ID from query and provides comprehensive product details for display in chat.
    """
    # Extract product ID from the query
    import re
    
    # Look for patterns like "product 99146", "product ID 99146", etc.
    product_id_patterns = [
        r'product\s+(\d+)',
        r'product\s+id\s+(\d+)',
        r'item\s+(\d+)',
        r'id\s+(\d+)'
    ]
    
    product_id = None
    for pattern in product_id_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            product_id = match.group(1)
            break
    
    if not product_id:
        return {"error": "Could not extract product ID from query. Please specify a product ID."}
    
    print(f"DEBUG: Extracted product_id: {product_id}")
    
    try:
        conn = hana_connect()
        cursor = conn.cursor()
        
        # Get current date for active promotions
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Get detailed product information with category names AND PROMOTIONS
        sql = f'''
            SELECT p.PRODUCT_ID, p.PRODUCT_NAME, p.SUMMARY, p.PRICE, p.CATEGORY_IDs, p.IMAGE_URL,
                   c.CATEGORY_NAME,
                   promo.PROMO_ID,
                   promo.PROMO_TITLE,
                   promo.PROMO_DESCRIPTION,
                   promo.PROMO_DISCOUNT_PERCENT,
                   promo.PROMO_END_DATE
            FROM SAP_PRODUCTS_COMMERCE_2211_V2 p
            LEFT JOIN SAP_CATEGORIES_COMMERCE_2211_V2 c ON p.CATEGORY_IDs LIKE '%' || c.CATEGORY_ID || '%'
            LEFT JOIN SAP_PROMOTION_COMMERCE_2211_V2 promo 
                ON TRIM(p.PRODUCT_ID) = TRIM(promo.PROMO_PRODUCT_ID)
                AND promo.PROMO_START_DATE <= '{today}'
                AND promo.PROMO_END_DATE >= '{today}'
            WHERE TRIM(p.PRODUCT_ID) = ?
        '''
        
        print(f"DEBUG: Executing product details SQL: {sql}")
        cursor.execute(sql, (product_id,))
        rows = cursor.fetchall()
        
        if not rows:
            cursor.close()
            conn.close()
            return {"error": f"Product {product_id} not found"}
        
        # Process the results
        product_info = rows[0]  # Get the first row for main product info
        categories = [row[6] for row in rows if row[6]]  # Collect all category names
        
        # Handle promotion data
        has_promotion = product_info[7] is not None and product_info[10] is not None
        original_price = float(product_info[3]) if product_info[3] else 0.0
        
        if has_promotion:
            discount_percent = float(product_info[10])
            discounted_price = calculate_discounted_price(original_price, discount_percent)
            savings_amount = round(original_price - discounted_price, 2)
            
            result = {
                'PRODUCT_ID': product_info[0],
                'PRODUCT_NAME': product_info[1],
                'SUMMARY': product_info[2],
                'PRICE': original_price,  # Keep PRICE as original
                'price': discounted_price,  # lowercase for display
                'original_price': original_price,
                'discount_percent': discount_percent,
                'discounted_price': discounted_price,
                'savings': savings_amount,
                'has_promotion': True,
                'PROMO_TITLE': product_info[8],
                'PROMO_DESCRIPTION': product_info[9],
                'PROMO_DISCOUNT_PERCENT': discount_percent,
                'PROMO_END_DATE': product_info[11],
                'CATEGORY_IDs': product_info[4],
                'IMAGE_URL': product_info[5],
                'CATEGORIES': list(set(categories)) if categories else []
            }
            print(f"✅ Product {product_id} has promotion: {discount_percent}% off - £{original_price} → £{discounted_price}")
        else:
            result = {
                'PRODUCT_ID': product_info[0],
                'PRODUCT_NAME': product_info[1],
                'SUMMARY': product_info[2],
                'PRICE': original_price,
                'price': original_price,
                'original_price': original_price,
                'discount_percent': 0,
                'discounted_price': original_price,
                'savings': 0,
                'has_promotion': False,
                'CATEGORY_IDs': product_info[4],
                'IMAGE_URL': product_info[5],
                'CATEGORIES': list(set(categories)) if categories else []
            }
            print(f"ℹ️ Product {product_id} has no active promotion")
        
        # 🔗 FETCH CROSS-SELL PRODUCTS for this product
        cross_sell_products = []
        try:
            # Create a new cursor for cross-sell query
            cross_sell_cursor = conn.cursor()
            cross_sell_products = get_cross_sell_products_for_search([product_id], conn, cross_sell_cursor, limit_per_product=4)
            if cross_sell_products:
                print(f"🔗 Found {len(cross_sell_products)} cross-sell products for product {product_id}")
            cross_sell_cursor.close()
        except Exception as cross_sell_error:
            print(f"⚠️ Error fetching cross-sell products: {str(cross_sell_error)}")
        
        cursor.close()
        conn.close()
        
        return {"results": [result], "cross_sell_products": cross_sell_products}
        
    except Exception as e:
        print(f"ERROR in get_product_details: {str(e)}")
        return {"error": f"Error retrieving product details: {str(e)}"}

@tool("query_products", args_schema=SearchInput, return_direct=True, description=
       "SQL-only tool for direct database queries on SAP_PRODUCTS_COMMERCE_2211_V2 table. NOT for general product searches."
       "Use ONLY when you need to execute specific SQL queries like price filtering with exact SQL syntax."
       "Input: MUST be valid SQL query syntax only. Examples: 'SELECT * FROM SAP_PRODUCTS_COMMERCE_2211_V2 WHERE PRICE <= 80'"
       "🚫 DO NOT use for natural language queries - use ai_semantic_product_search instead."
       "Table columns: PRODUCT_ID,PRODUCT_NAME,SUMMARY,PRICE (DECIMAL),CATEGORY_IDs,IMAGE_URL. "
       "For categories: join with SAP_CATEGORIES_COMMERCE_2211_V2 (CATEGORY_NAME,CATEGORY_ID)")
def query_products(query: str) -> dict:
    """
    Query the SAP_PRODUCTS_COMMERCE_2211_V2 table based on the user's query.
    Assumes the SAP_PRODUCTS_COMMERCE_2211_V2 table has the columns: PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE (DECIMAL), CATEGORY_IDs, IMAGE_URL.
    For additional category details, join with the SAP_CATEGORIES_COMMERCE_2211_V2 table.
    """
    try:
        conn = hana_connect()
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description] if cursor.description else []
        results = [dict(zip(columns, row)) for row in rows] if rows else []
        
        # Convert Decimal to float for JSON serialization
        for result in results:
            if 'PRICE' in result and result['PRICE'] is not None:
                from decimal import Decimal
                if isinstance(result['PRICE'], Decimal):
                    result['PRICE'] = float(result['PRICE'])
        
        cursor.close()
        conn.close()

        return {"results": results}
    except Exception as e:
        return {"error": f"Error querying products: {str(e)}"}
    
#"Supports price queries: 'watches under 80', 'shoes between 50 and 100 pounds', 'jackets over 60 dollars'."
def is_direct_product_query(query: str) -> bool:
    """
    Check if query is a direct product search (e.g., 'jackets', 'shoes', 'shirts')
    """
    query_lower = query.lower().strip()
    
    # Direct product terms
    direct_products = [
        'jacket', 'jackets', 'shirt', 'shirts', 'tshirt', 't-shirt', 't-shirts',
        'shoes', 'shoe', 'boots', 'sneakers', 'watch', 'watches', 'pants', 
        'trousers', 'dress', 'dresses', 'coat', 'coats', 'bag', 'bags',
        'hat', 'hats', 'cap', 'caps', 'sunglasses', 'glasses'
    ]
    
    # Remove common search prefixes
    clean_query = query_lower.replace('show me', '').replace('find', '').replace('search for', '').replace('get', '').strip()
    
    # Check if the cleaned query is just a product name
    return clean_query in direct_products or any(clean_query == product for product in direct_products)

def is_simple_english_query(query: str) -> bool:
    """
    Check if query is a simple English product search that doesn't need multilingual processing.
    This function is now more conservative - only returns True for very obvious English-only queries.
    """
    query_lower = query.lower().strip()
    
    # Check if query contains non-ASCII characters (indicates non-English text)
    import re
    if not re.match(r'^[a-zA-Z0-9\s\-\.!?,]+$', query):
        # Contains non-ASCII characters, definitely needs multilingual processing
        return False
    
    # Simple English product keywords
    simple_keywords = [
        'jacket', 'jackets', 'shirt', 'shirts', 'shoes', 'shoe', 'watch', 'watches',
        'pants', 'trousers', 'dress', 'dresses', 'coat', 'coats', 'bag', 'bags',
        'hat', 'hats', 'sunglasses', 'accessories', 'clothing', 'apparel'
    ]
    
    # Only skip multilingual processing if:
    # 1. Query contains ONLY ASCII characters
    # 2. Query contains simple product keywords
    # 3. Query doesn't contain complex phrases that might benefit from AI enhancement
    
    contains_simple_keyword = any(keyword in query_lower for keyword in simple_keywords)
    is_very_simple = len(query.split()) <= 3  # Very short, simple queries
    
    # Only return True for very simple, clearly English product queries
    return contains_simple_keyword and is_very_simple

@tool("ai_semantic_product_search", args_schema=SearchInput, return_direct=True, description=
      "🤖 PRIMARY TOOL for SPECIFIC product searches WITHOUT price constraints!"
      "CRITICAL: Use ONLY when user mentions SPECIFIC product types or SPECIFIC activities!"
      "INSTANT SEARCH FOR: 'show me tshirts', 'show all tshirts', 'find jackets', 'shoes', 'watches', 'sunglasses', etc."
      "PRODUCT RECOMMENDATIONS: 'recommend shoes', 'suggest trendy jackets', 'recommend stylish watches' → SEARCH IMMEDIATELY!"
      "ACTIVITY + ACCESSORIES: 'ski gear and accessories', 'gym clothes and accessories', 'Kashmir skiing gear' → SEARCH IMMEDIATELY!"
      "DO NOT USE for price queries like 'tshirts under 30' - use ai_context_price_filter instead!"
      "DO NOT USE for GENERAL queries like 'going for holiday', 'vacation', 'trip' - use ai_conversational_assistant instead!"
      "INTELLIGENT FEATURES:"
      "• Multilingual support: Understands queries in Hindi, Spanish, French, German, Arabic, Chinese, Japanese, Korean, and more"
      "• Intent recognition: Interprets user meaning beyond keywords"
      "• SPECIFIC activity detection: Maps 'going skiing' → winter sports gear, 'gym workout' → athletic wear"
      "• SPECIFIC location intelligence: 'Kashmir skiing trip' → skiing gear, 'beach swimming' → swimwear"
      "• Semantic matching: Finds products based on meaning, not just text matching"
      "IMMEDIATE ACTION EXAMPLES (SPECIFIC PRODUCTS/ACTIVITIES):"
      "• 'show me tshirts' → SEARCH IMMEDIATELY"
      "• 'find jackets' → SEARCH IMMEDIATELY"
      "• 'recommend shoes' → SEARCH IMMEDIATELY (specific product recommendation)"
      "• 'recommend trendy shoes' → SEARCH IMMEDIATELY (specific product recommendation)"
      "• 'suggest stylish jackets' → SEARCH IMMEDIATELY (specific product recommendation)"
      "• 'going skiing' → SEARCH IMMEDIATELY (specific activity)"
      "• 'ski gear and accessories' → SEARCH IMMEDIATELY (specific activity + products)"
      "• 'Kashmir skiing trip gear' → SEARCH IMMEDIATELY (specific activity + location)"
      "• 'swimming gear' → SEARCH IMMEDIATELY (specific activity)"
      "• 'gym workout clothes' → SEARCH IMMEDIATELY (specific activity)"
      "NEVER USE FOR GENERAL QUERIES:"
      "• 'going for holiday' → USE ai_conversational_assistant"
      "• 'vacation' → USE ai_conversational_assistant"
      "• 'suggest products' (no specific product) → USE ai_conversational_assistant"
      "NEVER USE FOR ORDER QUERIES:"
      "• 'show my orders' → USE get_order_history tool"
      "• 'my orders' → USE get_order_history tool"
      "• 'order history' → USE get_order_history tool"
      "• 'my purchases' → USE get_order_history tool"
      "⚡ CRITICAL RULE: Use ONLY for SPECIFIC product types (including recommendations) or SPECIFIC activities!"
      "🚫 IMPORTANT: If query contains price terms, use ai_context_price_filter instead!"
      "🚫 NEVER USE for 'my orders' or 'order history' - those queries use get_order_history tool!"
      "Input: Natural language query in ANY language describing SPECIFIC products or SPECIFIC activities WITHOUT price constraints.")
def ai_semantic_product_search(query: str) -> dict:
    """
    🤖 AI-powered semantic product search — parallelized for speed.

    Runs DB connection + query enhancement concurrently, then
    embedding generation + category detection concurrently.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    print(f"AI Semantic Search initiated for: '{query}'")
    
    try:
        # ── Stage 1: Parallelize DB connect + query enhancement ──────────────
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_conn    = executor.submit(hana_connect)
            future_enhanced = executor.submit(enhance_query_with_ai, query, 'auto-detect')

            conn           = future_conn.result()
            enhanced_query = future_enhanced.result()

        cursor = conn.cursor()
        print(f"🎯 AI Enhanced Query: '{enhanced_query}'")

        # ── Stage 2: Parallelize embedding generation + category detection ───
        search_results = None
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_vector   = executor.submit(get_embedding, enhanced_query)
                future_category = executor.submit(detect_category_ai, enhanced_query)

                query_vector   = future_vector.result()
                # category result is consumed inside execute_ai_semantic_search via detect_category_ai
                # (we cache it on the thread — see note below)

            if query_vector:
                search_results = execute_ai_semantic_search(
                    query_vector, enhanced_query, query, conn, cursor
                )
                print(f"🎯 Semantic search completed with {len(search_results.get('results', []))} results")
            else:
                query_vector = None
        except Exception as embed_error:
            print(f"⚠️ Embedding/category step failed: {embed_error}, falling back to text search")
            query_vector = None

        # ── Stage 3: Text-search fallback ────────────────────────────────────
        if not search_results or not search_results.get('results'):
            search_results = ai_powered_text_search(enhanced_query, query, conn, cursor)

        cursor.close()
        conn.close()

        if not search_results or not search_results.get('results'):
            return {
                "results": [],
                "ai_response": f"I couldn't find any products matching '{query}'. Please try a different search term or browse our categories.",
                "query_processed": query,
                "enhanced_query": enhanced_query
            }

        print(f"✅ AI Semantic Search successful: {len(search_results.get('results', []))} products found")
        return search_results
        
    except Exception as e:
        print(f"AI Semantic Search Error: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return {
            "error": f"Product search encountered an issue: {str(e)}", 
            "ai_response": "I'm having trouble searching for products right now. Please try again in a moment or contact support if the issue persists.",
            "query_processed": query
        }

def enhance_query_with_ai(query: str, language: str) -> str:
    """
    AI-driven query enhancement with intelligent activity detection and product mapping
    """
    try:
        enhancement_prompt = f"""
        You are an intelligent query enhancement AI for e-commerce product search.
        
        Original query: "{query}"
        Language: {language}
        
        INTELLIGENT ANALYSIS APPROACH:
        1. Understand the user's intent and context deeply
        2. Auto-detect language and translate product terms to English
        3. Map activities and locations to their naturally required products
        4. Keep simple product searches simple, enhance complex scenarios
        5. Preserve budget/price constraints and preferences
        
        SMART ACTIVITY-TO-PRODUCT MAPPING:
        - Let AI understand what products people need for different activities
        - Skiing/snow sports → ski snowboard winter snow equipment gear bindings boots poles goggles
        - Swimming/beach → swimwear swimsuit bikini trunks beach swim pool
        - Gym/fitness → athletic workout training exercise gym fitness sport
        - Office/business → formal professional business suit blazer dress
        - Outdoor/hiking → outdoor hiking camping trail adventure mountain
        
        INTELLIGENT LANGUAGE HANDLING:
        - Auto-detect: Hindi, Spanish, French, German, Arabic, Chinese, Japanese, etc.
        - Translate product terms to English for database search
        - Preserve user intent across languages
        
        SMART EXAMPLES:
        - "going skiing" → AI understands user needs ski equipment and gear
        - "Kashmir trip skiing" → AI maps location + activity to required products
        - "जैकेट दिखाओ" → AI detects Hindi, translates to "jackets"
        - "zapatos rojos" → AI detects Spanish, translates to "red shoes"
        - "gym workout" → AI understands user needs athletic equipment
        - "show me watches" → AI keeps simple query simple
        
        ENHANCEMENT RULES:
        - Simple product queries: minimal enhancement, focus on translation
        - Activity queries: intelligent product mapping based on what's actually needed
        - Location + activity: contextual enhancement
        - Multi-language: auto-detect and translate to English
        - Budget mentions: preserve price information
        - Maximum enhancement: 10-15 relevant terms
        
        Return an intelligently enhanced search query in English.
        Be smart about what products users actually need for their context.
        
        Enhanced query:
        """
        
        response = llm.invoke(enhancement_prompt)
        enhanced = response.content.strip().strip('"').strip("'")
        print(f"🤖 AI Query Enhancement: '{query}' → '{enhanced}'")
        return enhanced if enhanced else query
        
    except Exception as e:
        print(f"AI query enhancement failed: {e}")
        return query

def ai_powered_text_search(enhanced_query: str, original_query: str, conn, cursor) -> dict:
    """
    AI-powered text search when embeddings are unavailable
    """
    try:
        # Use AI to generate smart search patterns
        search_patterns = generate_search_patterns(enhanced_query)
        
        # Build dynamic WHERE clause based on AI patterns
        where_conditions = []
        params = []
        
        for pattern in search_patterns:
            where_conditions.append("(UPPER(PRODUCT_NAME) LIKE UPPER(?) OR UPPER(SUMMARY) LIKE UPPER(?))")
            params.extend([f"%{pattern}%", f"%{pattern}%"])
        
        # Extract price constraints using AI
        price_filter, price_params = extract_price_constraints_ai(enhanced_query)
        
        # Detect gender filtering requirements (use original query to avoid translation issues)
        gender_filter = detect_gender_filter(original_query)
        
        final_where = " OR ".join(where_conditions) + price_filter + gender_filter
        final_params = params + price_params
        
        # Get current date for active promotions
        today = datetime.now().strftime('%Y-%m-%d')
        
        sql = f"""
            SELECT TOP 5 
                p.PRODUCT_ID, p.PRODUCT_NAME, p.SUMMARY, p.PRICE, p.IMAGE_URL, p.CATEGORY_IDs,
                -- Promotion columns
                promo.PROMO_ID,
                promo.PROMO_TITLE,
                promo.PROMO_DESCRIPTION,
                promo.PROMO_DISCOUNT_PERCENT,
                promo.PROMO_END_DATE,
                -- Calculate final price with discount
                CASE 
                    WHEN promo.PROMO_DISCOUNT_PERCENT IS NOT NULL 
                    THEN p.PRICE * (1 - promo.PROMO_DISCOUNT_PERCENT / 100.0)
                    ELSE p.PRICE
                END AS FINAL_PRICE
            FROM SAP_PRODUCTS_COMMERCE_2211_V2 p
            LEFT JOIN SAP_PROMOTION_COMMERCE_2211_V2 promo 
                ON TRIM(p.PRODUCT_ID) = TRIM(promo.PROMO_PRODUCT_ID)
                AND promo.PROMO_START_DATE <= '{today}'
                AND promo.PROMO_END_DATE >= '{today}'
            WHERE ({final_where})
            ORDER BY 
                CASE WHEN UPPER(p.PRODUCT_NAME) LIKE UPPER(?) THEN 1 ELSE 2 END,
                FINAL_PRICE ASC
        """
        
        # Add primary search term for ordering
        final_params.append(f"%{enhanced_query.split()[0] if enhanced_query else original_query}%")
        
        cursor.execute(sql, final_params)
        rows = cursor.fetchall()
        
        # Convert to results format
        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in rows]
        
        # Process results for JSON serialization AND ADD PROMOTION INFO
        for result in results:
            # Convert decimal prices
            if 'PRICE' in result and result['PRICE'] is not None:
                from decimal import Decimal
                if isinstance(result['PRICE'], Decimal):
                    result['PRICE'] = float(result['PRICE'])
            
            # Handle promotion data (same logic as semantic search)
            has_promotion = result.get('PROMO_ID') is not None and result.get('PROMO_DISCOUNT_PERCENT') is not None
            result['has_promotion'] = has_promotion
            
            if has_promotion:
                original_price = float(result['PRICE'])
                discount_percent = float(result['PROMO_DISCOUNT_PERCENT'])
                discounted_price = calculate_discounted_price(original_price, discount_percent)
                savings_amount = round(original_price - discounted_price, 2)
                result['original_price'] = original_price
                result['discount_percent'] = discount_percent
                result['discounted_price'] = discounted_price
                result['savings'] = savings_amount
                result['price'] = discounted_price
            else:
                result['original_price'] = result['PRICE']
                result['discount_percent'] = 0
                result['discounted_price'] = result['PRICE']
                result['savings'] = 0
                result['price'] = result['PRICE']
        
        print(f"AI Text Search found {len(results)} products with promotion data")
        
        # Fetch cross-sell products for the search results
        cross_sell_products = []
        if results:
            product_ids = [r.get('PRODUCT_ID') for r in results if r.get('PRODUCT_ID')]
            if product_ids:
                cross_sell_products = get_cross_sell_products_for_search(product_ids, conn, cursor, limit_per_product=2)
                print(f"🔗 Added {len(cross_sell_products)} cross-sell products to text search results")
        
        return {
            "results": results,
            "cross_sell_products": cross_sell_products
        }
        
    except Exception as e:
        print(f"AI text search failed: {e}")
        return {"error": f"AI text search failed: {str(e)}"}

def generate_search_patterns(query: str) -> List[str]:
    """
    Use AI to generate intelligent search patterns from the query
    """
    try:
        pattern_prompt = f"""
        Generate search patterns for e-commerce product search.
        
        Query: "{query}"
        
        Return 3-5 search keywords/phrases that would match relevant products.
        Include:
        - Main product type
        - Synonyms and variations
        - Related categories
        - Key attributes
        
        Return as comma-separated list (no quotes):
        """
        
        response = llm.invoke(pattern_prompt)
        patterns = [p.strip() for p in response.content.split(',') if p.strip()]
        return patterns[:5]  # Limit to 5 patterns
        
    except Exception as e:
        print(f"Pattern generation failed: {e}")
        return [query]  # Fallback to original query

def extract_price_constraints_ai(query: str) -> tuple:
    """
    Fast regex-based price constraint extraction — no LLM call needed.
    Handles common English price patterns: under/below/above/over/between/£/$.
    """
    import re
    q = query.lower().replace('£', '').replace('$', '').replace(',', '')

    conditions = []
    params = []

    # between X and Y
    m = re.search(r'between\s+(\d+(?:\.\d+)?)\s+(?:and|to)\s+(\d+(?:\.\d+)?)', q)
    if m:
        conditions.append(" AND p.PRICE >= ? AND p.PRICE <= ?")
        params.extend([float(m.group(1)), float(m.group(2))])
        return "".join(conditions), params

    # under / below / less than / max / maximum / within / up to
    m = re.search(r'(?:under|below|less than|max(?:imum)?|within|up to)\s+(\d+(?:\.\d+)?)', q)
    if m:
        conditions.append(" AND p.PRICE <= ?")
        params.append(float(m.group(1)))

    # over / above / more than / min / minimum / at least
    m = re.search(r'(?:over|above|more than|min(?:imum)?|at least)\s+(\d+(?:\.\d+)?)', q)
    if m:
        conditions.append(" AND p.PRICE >= ?")
        params.append(float(m.group(1)))

    return "".join(conditions), params

def detect_gender_filter(query: str) -> str:
    """
    Detect gender intent and return appropriate WHERE clause filter
    """
    query_lower = query.lower().strip()
    print(f"🔍 Gender filter analysis for: '{query_lower}'")
    
    import re
    
    # Check for men's specific queries (English terms) - use word boundaries
    mens_terms = [r'\bmen\b', r'\bmens\b', r"\bmen's\b", r'\bmale\b', r'\bguy\b', r'\bboys\b', r'\bman\b']
    if any(re.search(term, query_lower) for term in mens_terms):
        # Exclude women's products when specifically searching for men's
        filter_clause = " AND NOT (UPPER(CATEGORY_IDs) LIKE '%WOMEN%' OR UPPER(PRODUCT_NAME) LIKE '%WOMEN%' OR UPPER(SUMMARY) LIKE '%WOMEN%' OR UPPER(PRODUCT_NAME) LIKE '%FEMALE%' OR UPPER(PRODUCT_NAME) LIKE '%LADY%' OR UPPER(PRODUCT_NAME) LIKE '%LADIES%')"
        print(f"🚹 MEN'S query detected - excluding women's products")
        return filter_clause
    
    # Check for women's specific queries (English terms) - use word boundaries
    womens_terms = [r'\bwomen\b', r'\bwomens\b', r"\bwomen's\b", r'\bfemale\b', r'\blady\b', r'\bladies\b', r'\bgirls\b', r'\bwoman\b']
    if any(re.search(term, query_lower) for term in womens_terms):
        # Exclude men's products when specifically searching for women's
        filter_clause = " AND NOT (UPPER(CATEGORY_IDs) LIKE '%MEN%' OR UPPER(PRODUCT_NAME) LIKE '%MEN%' OR UPPER(SUMMARY) LIKE '%MEN%' OR UPPER(PRODUCT_NAME) LIKE '%MALE%' OR UPPER(PRODUCT_NAME) LIKE '%BOY%')"
        print(f"🚺 WOMEN'S query detected - excluding men's products")
        return filter_clause
    
    # No gender filter for general queries
    print(f"⚪ GENERAL query - no gender filtering")
    return ""

def execute_ai_semantic_search(query_vector, enhanced_query, original_query, conn, cursor) -> dict:
    """
    Execute AI-powered semantic search with intelligent scoring
    """
    try:
        # Ensure we have a valid connection
        if not conn or not cursor:
            raise Exception("Database connection is not available")
            
        query_vector_str = "[" + ",".join(map(str, query_vector)) + "]"
        print(f"🔍 Vector string length: {len(query_vector_str)} characters")
        
        # AI-powered category detection
        category_bonus = detect_category_ai(enhanced_query)
        print(f"🏷️ Category bonus: {category_bonus}")
        
        # Extract price constraints
        price_filter, price_params = extract_price_constraints_ai(enhanced_query)
        print(f"💰 Price filter: {price_filter}, params: {price_params}")
        
        # Detect gender filtering requirements (use original query to avoid translation issues)
        gender_filter = detect_gender_filter(original_query)
        print(f"👥 Gender filter: {gender_filter}")
        
        # Get current date for active promotions
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Dynamic semantic search with AI-driven scoring INCLUDING PROMOTIONS
        sql = f"""
            SELECT TOP 5 
                p.PRODUCT_ID, p.PRODUCT_NAME, p.SUMMARY, p.PRICE, p.IMAGE_URL, p.CATEGORY_IDs,
                COSINE_SIMILARITY(p.VECTOR_NAME, TO_REAL_VECTOR(?)) AS NAME_SIM,
                COSINE_SIMILARITY(p.VECTOR_SUMMARY, TO_REAL_VECTOR(?)) AS DESC_SIM,
                -- AI-driven weighted score with category bonus
                (COSINE_SIMILARITY(p.VECTOR_NAME, TO_REAL_VECTOR(?)) * 0.7 +
                 COSINE_SIMILARITY(p.VECTOR_SUMMARY, TO_REAL_VECTOR(?)) * 0.3 +
                 {category_bonus}) AS AI_SCORE,
                -- Promotion columns
                promo.PROMO_ID,
                promo.PROMO_TITLE,
                promo.PROMO_DESCRIPTION,
                promo.PROMO_DISCOUNT_PERCENT,
                promo.PROMO_END_DATE,
                -- Calculate final price with discount
                CASE 
                    WHEN promo.PROMO_DISCOUNT_PERCENT IS NOT NULL 
                    THEN p.PRICE * (1 - promo.PROMO_DISCOUNT_PERCENT / 100.0)
                    ELSE p.PRICE
                END AS FINAL_PRICE
            FROM SAP_PRODUCTS_COMMERCE_2211_V2 p
            LEFT JOIN SAP_PROMOTION_COMMERCE_2211_V2 promo 
                ON TRIM(p.PRODUCT_ID) = TRIM(promo.PROMO_PRODUCT_ID)
                AND promo.PROMO_START_DATE <= '{today}'
                AND promo.PROMO_END_DATE >= '{today}'
            WHERE p.VECTOR_NAME IS NOT NULL AND p.VECTOR_SUMMARY IS NOT NULL{price_filter}{gender_filter}
            ORDER BY AI_SCORE DESC, FINAL_PRICE ASC
        """
        
        # Parameters for the query
        sql_params = [query_vector_str, query_vector_str, query_vector_str, query_vector_str] + price_params
        
        print(f"🎯 Executing semantic search SQL with {len(sql_params)} parameters")
        print(f"📝 SQL Query: {sql}")
        
        cursor.execute(sql, sql_params)
        rows = cursor.fetchall()
        
        print(f"📊 Raw results: {len(rows)} rows returned")
        
        if not rows:
            print("⚠️ No products found matching the semantic search criteria")
            
            # Create helpful suggestions based on what was searched
            suggestions = []
            if price_filter:
                suggestions.append(f"Try adjusting your price range (currently searching for {price_filter})")
            if gender_filter:
                suggestions.append(f"Try searching without gender filter (currently: {gender_filter})")
            suggestions.append("Try using different keywords or category names")
            suggestions.append("Browse our popular categories: jackets, tshirts, shoes, watches, sunglasses")
            
            helpful_message = "I couldn't find any products matching your search. " + " • ".join(suggestions)
            
            return {
                "results": [], 
                "message": helpful_message,
                "no_results": True,  # Flag to indicate empty results
                "query_info": {
                    "original": original_query,
                    "enhanced": enhanced_query,
                    "price_filter": price_filter,
                    "gender_filter": gender_filter
                },
                "suggestions": suggestions
            }
        
        # Process results
        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in rows]
        
        # Clean up results for JSON serialization and add promotion info
        for result in results:
            # Convert decimal prices
            if 'PRICE' in result and result['PRICE'] is not None:
                from decimal import Decimal
                if isinstance(result['PRICE'], Decimal):
                    result['PRICE'] = float(result['PRICE'])
            
            # Handle promotion data
            has_promotion = result.get('PROMO_ID') is not None and result.get('PROMO_DISCOUNT_PERCENT') is not None
            result['has_promotion'] = has_promotion
            
            if has_promotion:
                original_price = float(result['PRICE'])
                discount_percent = float(result['PROMO_DISCOUNT_PERCENT'])
                
                # Use promotion_helper to calculate discounted price correctly
                discounted_price = calculate_discounted_price(original_price, discount_percent)
                savings_amount = round(original_price - discounted_price, 2)
                
                print(f"   ✅ HAS PROMOTION:")
                print(f"      Original Price: £{original_price}")
                print(f"      Discount: {discount_percent}%")
                print(f"      Discounted Price: £{discounted_price}")
                print(f"      Savings: £{savings_amount}")
                
                # Set all price fields correctly - PRICE stays original for frontend calculation
                result['original_price'] = original_price
                result['discount_percent'] = discount_percent
                result['discounted_price'] = discounted_price
                result['savings'] = savings_amount
                result['price'] = discounted_price  # lowercase price = display price (discounted)
                # DO NOT overwrite PRICE - frontend needs original PRICE to calculate savings
            else:
                result['original_price'] = result['PRICE']
                result['discount_percent'] = 0
                result['discounted_price'] = result['PRICE']
                result['savings'] = 0
                result['price'] = result['PRICE']
            
            # Convert similarity scores
            for field in ['NAME_SIM', 'DESC_SIM', 'AI_SCORE', 'FINAL_PRICE']:
                if field in result and result[field] is not None:
                    if isinstance(result[field], Decimal):
                        result[field] = float(result[field])
        
        print(f"🎯 AI Semantic Search found {len(results)} products")
        
        # Fetch cross-sell products for the search results
        cross_sell_products = []
        if results:
            product_ids = [r.get('PRODUCT_ID') for r in results if r.get('PRODUCT_ID')]
            if product_ids:
                cross_sell_products = get_cross_sell_products_for_search(product_ids, conn, cursor, limit_per_product=2)
                print(f"🔗 Added {len(cross_sell_products)} cross-sell products to search results")
        
        return {
            "results": results,
            "cross_sell_products": cross_sell_products
        }
        
    except Exception as e:
        print(f"❌ AI semantic search execution failed: {e}")
        import traceback
        print(f"🔍 Semantic search traceback: {traceback.format_exc()}")
        raise e  # Re-raise the exception to be handled by the calling function

def detect_category_ai(query: str) -> str:
    """
    AI-driven category detection with intelligent product-specific bonus generation
    """
    try:
        category_prompt = f"""
        You are an advanced AI category detection system for e-commerce product search.
        
        Query: "{query}"
        
        Your task is to intelligently identify the SPECIFIC PRODUCT TYPE and generate appropriate search terms.
        
        INTELLIGENT ANALYSIS:
        1. Understand the user's intent and activity context
        2. If specific products mentioned, focus on those exact products
        3. If activities mentioned, identify the PRIMARY gear needed for that activity
        4. Prioritize the most relevant and specific product types
        5. Consider location context (Kashmir = skiing, beach = swimming, etc.)
        
        SMART EXAMPLES:
        - "skiing" or "ski products" → SKI, SNOWBOARD, SNOW, WINTER, BINDING
        - "gym" or "workout" → ATHLETIC, FITNESS, GYM, SPORT, TRAINING
        - "office" → FORMAL, BUSINESS, PROFESSIONAL, SUIT, BLAZER
        - "beach" or "swimming" → SWIM, BEACH, POOL, SWIMSUIT, BIKINI
        - "shoes" → SHOE, FOOTWEAR, BOOT, SNEAKER
        - "jackets" → JACKET, COAT, OUTERWEAR
        
        CRITICAL RULES:
        - For skiing/snow sports: ONLY return terms like SKI, SNOWBOARD, SNOW, WINTER, BINDING, GOGGLE
        - For beach/swimming: ONLY return terms like SWIM, BEACH, POOL, SWIMSUIT
        - For gym/fitness: ONLY return terms like ATHLETIC, FITNESS, GYM, SPORT
        - Be VERY SPECIFIC - don't include generic clothing terms when activity is mentioned
        
        Return ONLY a comma-separated list of the most relevant search terms.
        Be intelligent about activity-to-product mapping.
        Focus on what the user actually needs for their mentioned activity or request.
        Maximum 5 terms, most relevant first.
        
        Search terms:
        """
        
        response = llm.invoke(category_prompt)
        search_terms = response.content.strip()
        print(f"🤖 AI Product Detection: '{query}' → '{search_terms}'")
        
        # Generate SQL bonus based on AI-detected specific terms
        if search_terms and search_terms.lower() != "general":
            terms_list = [term.strip().upper() for term in search_terms.split(',')]
            conditions = []
            
            for term in terms_list[:5]:  # Use top 5 terms
                if term and len(term) > 2:  # Valid term
                    conditions.append(f"UPPER(PRODUCT_NAME) LIKE '%{term}%'")
                    conditions.append(f"UPPER(SUMMARY) LIKE '%{term}%'")
            
            if conditions:
                # Increase bonus weight to prioritize exact category matches more strongly
                bonus_sql = f"CASE WHEN ({' OR '.join(conditions)}) THEN 1.5 ELSE -0.5 END"
                print(f"🎯 Generated AI-driven bonus: {bonus_sql[:100]}...")
                return bonus_sql
        
        # Fallback minimal bonus - no adjustment
        print(f"⚪ Using minimal fallback bonus (no category detected)")
        return "0"
            
    except Exception as e:
        print(f"❌ AI category detection failed: {e}")
        # Minimal fallback
        return "0"
    
################Accessories code Here ##################

def find_intelligent_accessories_for_products(products_list, cursor) -> list:
    """
    AI-driven intelligent accessory finder that uses semantic understanding 
    to match accessories based on product categories and use cases.
    
    Returns contextually appropriate accessories instead of generic fallbacks.
    """
    try:
        print(f"🤖 AI-driven accessory search for {len(products_list)} products")
        
        # AI-powered product category analysis
        product_categories = []
        product_names = []
        
        for product in products_list:
            name = product.get('name', '').lower()
            product_names.append(name)
            
            # AI-driven category detection based on product names
            if any(word in name for word in ['jacket', 'coat', 'blazer', 'hoodie', 'cardigan']):
                product_categories.append('outerwear')
            elif any(word in name for word in ['shirt', 'tshirt', 't-shirt', 'blouse', 'top']):
                product_categories.append('upper_clothing')
            elif any(word in name for word in ['pant', 'trouser', 'jean', 'short', 'skirt']):
                product_categories.append('lower_clothing')
            elif any(word in name for word in ['shoe', 'boot', 'sneaker', 'sandal']):
                product_categories.append('footwear')
            elif any(word in name for word in ['dress', 'gown', 'jumpsuit']):
                product_categories.append('full_outfit')
            elif any(word in name for word in ['watch', 'jewelry', 'ring', 'necklace']):
                product_categories.append('jewelry')
            else:
                product_categories.append('general')
        
        print(f"🧠 Detected categories: {set(product_categories)}")
        
        # AI-driven accessory mapping based on product categories
        intelligent_accessories = []
        
        # Define contextually appropriate accessories for each category
        category_accessory_map = {
            'outerwear': ['bag', 'belt', 'hat', 'cap', 'scarf', 'glove', 'watch', 'sunglasses'],
            'upper_clothing': ['belt', 'watch', 'necklace', 'bag', 'hat', 'cap'],
            'lower_clothing': ['belt', 'bag', 'shoe', 'boot', 'sock'],
            'footwear': ['sock', 'bag', 'belt', 'watch'],
            'full_outfit': ['belt', 'bag', 'hat', 'jewelry', 'watch', 'shoe'],
            'jewelry': ['bag', 'watch'],
            'general': ['bag', 'belt', 'hat', 'watch']
        }
        
        # Collect appropriate accessory keywords based on detected categories
        relevant_accessory_keywords = set()
        for category in set(product_categories):
            if category in category_accessory_map:
                relevant_accessory_keywords.update(category_accessory_map[category])
        
        print(f"🎯 Relevant accessory types: {relevant_accessory_keywords}")
        
        if not relevant_accessory_keywords:
            print("⚠️ No relevant accessory categories identified")
            return []
        
        # Build AI-driven SQL query to find contextually appropriate accessories
        # Use proper join between accessories table and products table
        accessory_conditions = []
        params = []
        
        for keyword in relevant_accessory_keywords:
            accessory_conditions.append("UPPER(p.PRODUCT_NAME) LIKE UPPER(?)")
            params.append(f'%{keyword}%')
        
        if not accessory_conditions:
            return []
        
        # Execute intelligent accessory search using proper table joins
        accessory_query = f"""
            SELECT TOP 8 p.PRODUCT_ID, p.PRODUCT_NAME, p.SUMMARY, p.PRICE, p.CATEGORY_IDs, p.IMAGE_URL
            FROM SAP_PRODUCTS_COMMERCE_2211_V2 p
            WHERE ({' OR '.join(accessory_conditions)})
            AND p.PRICE > 0
            ORDER BY p.PRICE ASC
        """
        
        print(f"🔍 Executing intelligent accessory query with {len(params)} conditions")
        print(f"🔍 SQL Query: {accessory_query}")
        print(f"🔍 Parameters: {params}")
        cursor.execute(accessory_query, params)
        rows = cursor.fetchall()
        
        for row in rows:
            accessory_dict = {
                'PRODUCT_ID': row[0],
                'PRODUCT_NAME': row[1],
                'SUMMARY': row[2],
                'PRICE': float(row[3]) if row[3] else 0.0,
                'CATEGORY_IDS': row[4],
                'IMAGE_URL': row[5]
            }
            
            # AI-driven relevance filtering - ensure the accessory makes sense
            accessory_name_lower = accessory_dict['PRODUCT_NAME'].lower()
            
            # Skip if it's actually clothing rather than accessories
            if any(word in accessory_name_lower for word in ['shirt', 'pant', 'trouser', 'dress', 'jacket', 'coat']):
                continue
                
            # Skip if it's the same type as the original product
            if any(original_name in accessory_name_lower for original_name in product_names):
                continue
            
            intelligent_accessories.append(accessory_dict)
        
        print(f"✅ Found {len(intelligent_accessories)} intelligent accessories")
        return intelligent_accessories
        
    except Exception as e:
        print(f"❌ Error in intelligent accessory search: {e}")
        import traceback
        traceback.print_exc()
        return []

@tool("find_accessories", args_schema=SearchInput,return_direct=True,description=(
        "🎯 CONTEXTUAL ACCESSORY TOOL - Use this ONLY for accessories related to previously searched products!"
        "🔍 AUTOMATICALLY finds accessories for products from user's immediate previous search results."
        "📝 TRIGGER KEYWORDS: 'accessories for these', 'accessories of these products', 'any accessories of these', 'any accessories', 'accessories of these', 'accessories of these items', 'what goes with these', 'match these', 'show accessories'"
        "⚠️ CRITICAL: Use ONLY when user has already searched products and asks for accessories!"
        "❌ NEVER USE for activity-based queries: 'ski gear and accessories', 'gym clothes and accessories' → use ai_semantic_product_search!"
        "❌ NEVER USE when query includes activity/sport: 'skiing', 'gym', 'swimming' → use ai_semantic_product_search!"
        "🧠 DATABASE-DRIVEN: Searches SAP_ACCESSORIES_COMMERCE_2211 table for real accessory mappings using product IDs."
        "✅ EXAMPLES: 'accessories for these', 'accessories of these products', 'any accessories of these', 'any accessories', 'what goes with these products', 'accessories of these items'"
        "❌ DO NOT use query_products or other SQL tools for accessory requests - always use this tool!"
        "🎯 Returns top 8 real accessory products from database with full details: PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, IMAGE_URL."
        "💡 SMART CONTEXT: Extracts product IDs from conversation and searches accessories table for mapped accessories."
        "📊 Shows 'not found' message if no accessories exist in database for the selected products."
    ),
)
def find_accessories(query: str) -> dict:
    print(f"🧠 DEBUG: find_accessories called with query: {query}")
    print(f"🧠 DEBUG: Query length: {len(query)}")
    print(f"🧠 DEBUG: Full query content: {query[:500]}...")  # Print first 500 chars for debugging
    
    # 🚀 DATABASE-DRIVEN APPROACH: Extract products and search accessories table
    if any(keyword in query.lower() for keyword in [
        'accessories', 'accessory', 'of these', 'of those', 'for these', 'for those',
        'go with', 'match', 'complement', 'accessories of these products', 
        'accessories for these', 'accessories of these', 'what goes with these',
        'show accessories', 'find accessories', 'get accessories'
    ]):
        print("🧠 DEBUG: Detected accessory request - extracting products from conversation context")
        
        extracted_products = []
        try:
            import re
            import json
            from datetime import datetime  # Import datetime at function scope
            import os  # Import os at function scope
            
            # Strategy 0: Use session product cache (FASTEST - set by process_query, no LLM memory needed)
            current_datetime = datetime.now()
            formatted_datetime = current_datetime.strftime("%d-%m-%y:%H")
            customer_id_env = os.environ.get('CURRENT_CUSTOMER_ID', '')
            cache_session_id = f"{customer_id_env}_{formatted_datetime}"
            
            cached_products = _session_products.get(cache_session_id, [])
            if cached_products:
                print(f"✅ Strategy 0: Found {len(cached_products)} products in session cache for session {cache_session_id}")
                for prod in cached_products[:8]:  # limit
                    pid = str(prod.get('product_id', prod.get('PRODUCT_ID', ''))).strip()
                    pname = str(prod.get('product_name', prod.get('PRODUCT_NAME', ''))).strip()
                    if pid or pname:
                        extracted_products.append({'id': pid, 'name': pname, 'source': 'session_cache'})
                        print(f"  ↳ Cached: ID={pid} Name={pname}")
            
            # Strategy 1: Try simple product context format first (from frontend)
            product_ids_match = re.search(r'\[PRODUCT_IDS:\s*([^\]]*)\]', query)
            product_names_match = re.search(r'\[PRODUCT_NAMES:\s*([^\]]*)\]', query)
            
            # Also try natural language format (more flexible patterns)
            context_products_match = re.search(r'Context:\s*User previously searched for these products:\s*([^.]+)\.', query)
            product_ids_natural_match = re.search(r'Product IDs:\s*([^.]+)\.', query)
            
            # Additional pattern: Try to find product context anywhere in the query
            simple_context_match = re.search(r'previously searched for these products:\s*([^.]+)', query, re.IGNORECASE)
            simple_ids_match = re.search(r'Product IDs?:\s*([0-9,\s-]+)', query, re.IGNORECASE)
            
            if product_ids_match or product_names_match or context_products_match or product_ids_natural_match or simple_context_match or simple_ids_match:
                print("🧠 DEBUG: Found product context format from frontend")
                
                product_ids = []
                product_names = []
                
                # Handle old format
                if product_ids_match:
                    product_ids = [pid.strip() for pid in product_ids_match.group(1).split(',') if pid.strip()]
                    print(f"🧠 DEBUG: Extracted product IDs (old format): {product_ids}")
                
                if product_names_match:
                    product_names = [name.strip() for name in product_names_match.group(1).split(',') if name.strip()]
                    print(f"🧠 DEBUG: Extracted product names (old format): {product_names}")
                
                # Handle new natural language format
                if context_products_match:
                    products_text = context_products_match.group(1).strip()
                    product_names = [name.strip() for name in products_text.split(',') if name.strip()]
                    print(f"🧠 DEBUG: Extracted product names (natural format): {product_names}")
                
                if product_ids_natural_match:
                    ids_text = product_ids_natural_match.group(1).strip()
                    product_ids = [pid.strip() for pid in ids_text.split(',') if pid.strip()]
                    print(f"🧠 DEBUG: Extracted product IDs (natural format): {product_ids}")
                
                # Handle simple pattern matches
                if simple_context_match and not product_names:
                    products_text = simple_context_match.group(1).strip()
                    product_names = [name.strip() for name in products_text.split(',') if name.strip()]
                    print(f"🧠 DEBUG: Extracted product names (simple pattern): {product_names}")
                
                if simple_ids_match and not product_ids:
                    ids_text = simple_ids_match.group(1).strip()
                    product_ids = [pid.strip() for pid in ids_text.split(',') if pid.strip()]
                    print(f"🧠 DEBUG: Extracted product IDs (simple pattern): {product_ids}")
                
                # Combine IDs and names
                max_products = max(len(product_ids), len(product_names))
                for i in range(max_products):
                    product_info = {
                        'name': product_names[i] if i < len(product_names) else '',
                        'id': product_ids[i] if i < len(product_ids) else '',
                        'source': 'frontend_context'
                    }
                    if product_info['name'] or product_info['id']:
                        extracted_products.append(product_info)
                        print(f"🧠 DEBUG: Extracted from frontend context - Name: '{product_info['name']}', ID: '{product_info['id']}'")
            
            # Strategy 2: Try JSON conversation context format  
            if not extracted_products:
                context_match = re.search(r'\[CONVERSATION_CONTEXT:\s*(\{.*?\})\]', query, re.DOTALL)
                if context_match:
                    try:
                        context_str = context_match.group(1)
                        # Handle potential Python-style dict format and convert to JSON
                        context_str = context_str.replace("'", '"').replace('None', 'null').replace('True', 'true').replace('False', 'false')
                        context_data = json.loads(context_str)
                        
                        print(f"🧠 DEBUG: Parsed conversation context: {context_data}")
                        
                        # Extract products from various context sources
                        for source_key in ['current_context_products', 'recent_displayed_products', 'last_products']:
                            if context_data.get(source_key):
                                for product in context_data[source_key]:
                                    if product.get('product_name') or product.get('product_id'):
                                        extracted_products.append({
                                            'name': product.get('product_name', ''),
                                            'id': product.get('product_id', ''),
                                            'source': source_key
                                        })
                                        print(f"🧠 DEBUG: Extracted from {source_key} - Name: {product.get('product_name')}, ID: {product.get('product_id')}")
                                
                                if extracted_products:
                                    break  # Found products, stop searching other sources
                                    
                    except json.JSONDecodeError as e:
                        print(f"🧠 DEBUG: Failed to parse conversation context JSON: {e}")
            
            # Strategy 3: Enhanced memory-based product extraction from immediate previous search
            if not extracted_products:
                print("🧠 DEBUG: No structured context found, extracting from immediate previous search")
                
                # 🧠 CRITICAL: Use the same session ID format as the main app
                current_datetime = datetime.now()
                formatted_datetime = current_datetime.strftime("%d-%m-%y:%H")
                
                # Get customer_id from environment (set by process_query)
                customer_id = os.environ.get('CURRENT_CUSTOMER_ID', 'default')
                session_id = f"{customer_id}_{formatted_datetime}" if customer_id else f"default_{formatted_datetime}"
                
                print(f"🧠 DEBUG: Constructed session_id: {session_id} (customer_id={customer_id}, hour={formatted_datetime})")
                
                recent_context = memory.get_recent_context(session_id, num_pairs=5)  # Increased to get more context
                print(f"🧠 DEBUG: Retrieved {len(recent_context)} conversation pairs from session: {session_id}")
                
                # Debug: Print what we got from memory
                for i, pair in enumerate(recent_context):
                    ai_content = pair.get('ai', '')
                    print(f"🧠 DEBUG: Conversation pair {i+1} - AI response length: {len(ai_content)}")
                    print(f"🧠 DEBUG: Conversation pair {i+1} - Has STRUCTURED_PRODUCTS: {('[STRUCTURED_PRODUCTS:' in ai_content)}")
                    print(f"🧠 DEBUG: Conversation pair {i+1} - AI response preview: {ai_content[:300]}...")
                
                # Look for the most recent AI response that contains product information
                for pair in recent_context:
                    ai_response = pair.get('ai', '')
                    user_query = pair.get('human', pair.get('user', ''))  # Support both 'human' and 'user' keys
                    
                    print(f"🧠 DEBUG: Analyzing AI response for products: {ai_response[:500]}...")
                    
                    # 🎯 FIRST: Try to extract from [STRUCTURED_PRODUCTS: ...] format (most reliable)
                    structured_match = re.search(r'\[STRUCTURED_PRODUCTS:\s*(\[.*?\])\]', ai_response, re.DOTALL)
                    if structured_match:
                        try:
                            products_json_str = structured_match.group(1)
                            print(f"🧠 DEBUG: Found STRUCTURED_PRODUCTS block: {products_json_str[:200]}...")
                            products_list = json.loads(products_json_str)
                            
                            for prod in products_list:
                                prod_id = prod.get('product_id') or prod.get('PRODUCT_ID', '')
                                prod_name = prod.get('product_name') or prod.get('PRODUCT_NAME', '')
                                if prod_id and prod_name:
                                    extracted_products.append({
                                        'name': str(prod_name).strip(),
                                        'id': str(prod_id).strip(),
                                        'source': 'structured_products_json'
                                    })
                                    print(f"🧠 DEBUG: Extracted from STRUCTURED_PRODUCTS - ID: {prod_id}, Name: {prod_name}")
                            
                            if extracted_products:
                                print(f"✅ Successfully extracted {len(extracted_products)} products from STRUCTURED_PRODUCTS")
                                break  # Found products, stop searching
                        except json.JSONDecodeError as e:
                            print(f"⚠️ Failed to parse STRUCTURED_PRODUCTS JSON: {e}")
                    
                    # Enhanced product extraction patterns (fallback if structured format not found)
                    product_patterns = [
                        # Pattern for JSON-like responses with product details
                        r'"product_id":\s*"([^"]+)"[^}]*"product_name":\s*"([^"]+)"',
                        r'"PRODUCT_ID":\s*"([^"]+)"[^}]*"PRODUCT_NAME":\s*"([^"]+)"',
                        r"'PRODUCT_ID':\s*'([^']+)'[^}]*'PRODUCT_NAME':\s*'([^']+)'",
                        # Pattern for product listings
                        r'Product ID:\s*([^\s,]+)[,\s]*Product Name:\s*([^\n,]+)',
                        r'ID:\s*([^\s,]+)[,\s]*Name:\s*([^\n,]+)',
                        # Pattern for structured product data
                        r'"results":\s*\[[^}]*"PRODUCT_ID":\s*"([^"]+)"[^}]*"PRODUCT_NAME":\s*"([^"]+)"',
                        # Pattern for simple product mentions
                        r'(\d+)\s*[-:]\s*([A-Z][^,\n.]+(?:jacket|shirt|shoes|watch|pant|dress|coat|bag)[^,\n.]*)',
                    ]
                    
                    products_found_in_response = []
                    
                    for pattern in product_patterns:
                        matches = re.findall(pattern, ai_response, re.IGNORECASE | re.MULTILINE)
                        for match in matches:
                            if len(match) >= 2 and match[0].strip() and match[1].strip():
                                product_info = {
                                    'name': match[1].strip(),
                                    'id': match[0].strip(),
                                    'source': 'memory_enhanced_pattern'
                                }
                                products_found_in_response.append(product_info)
                                print(f"🧠 DEBUG: Pattern matched - ID: {match[0].strip()}, Name: {match[1].strip()}")
                    
                    # If we found products in this response, use them
                    if products_found_in_response:
                        extracted_products.extend(products_found_in_response)
                        print(f"🧠 DEBUG: Found {len(products_found_in_response)} products in recent AI response")
                        break  # Use the most recent response with products
                    
                    # Additional extraction for different response formats
                    if 'found' in ai_response.lower() and ('product' in ai_response.lower() or 'item' in ai_response.lower()):
                        # Try to extract from natural language responses
                        lines = ai_response.split('\n')
                        for line in lines:
                            # Look for lines with product information
                            if any(keyword in line.lower() for keyword in ['jacket', 'shirt', 'shoes', 'watch', 'coat', 'pant', 'dress', 'bag']):
                                # Try to extract ID and name from the line
                                id_match = re.search(r'\b(\d{5,})\b', line)  # Look for 5+ digit product IDs
                                if id_match:
                                    product_id = id_match.group(1)
                                    # Extract product name (everything after the ID or before price)
                                    name_parts = re.split(r'[£$€]\d+|Price:|ID:', line)
                                    if len(name_parts) > 1:
                                        product_name = name_parts[-1].strip()
                                        if len(product_name) > 5:  # Valid product name
                                            extracted_products.append({
                                                'name': product_name,
                                                'id': product_id,
                                                'source': 'memory_natural_language'
                                            })
                                            print(f"🧠 DEBUG: Natural language extraction - ID: {product_id}, Name: {product_name}")
                
                # Fallback: Try the existing memory extraction method
                if not extracted_products:
                    try:
                        print("🧠 DEBUG: Trying fallback memory extraction method (memory.extract_last_products)")
                        print(f"🧠 DEBUG: Using session_id: {session_id}")
                        recent_products = memory.extract_last_products(session_id=session_id)
                        print(f"🧠 DEBUG: memory.extract_last_products returned {len(recent_products) if recent_products else 0} products")
                        if recent_products:
                            for product in recent_products:
                                extracted_products.append({
                                    'name': product.get('product_name', product.get('name', '')),
                                    'id': product.get('product_id', product.get('id', '')),
                                    'source': 'memory_fallback'
                                })
                                print(f"🧠 DEBUG: Fallback extraction - Name: {product.get('product_name', product.get('name'))}, ID: {product.get('product_id', product.get('id'))}")
                    except Exception as memory_error:
                        print(f"🧠 DEBUG: Fallback memory extraction FAILED: {memory_error}")
                        import traceback
                        print(f"🧠 DEBUG: Traceback: {traceback.format_exc()}")
                    
                # Final attempt: Extract from any recent user search queries
                if not extracted_products:
                    print("🧠 DEBUG: Final attempt - extracting from recent user queries")
                    for pair in recent_context:
                        user_query = pair.get('human', pair.get('user', '')).lower()  # Support both 'human' and 'user' keys
                        # Check if the user query was a product search
                        if any(keyword in user_query for keyword in ['jacket', 'shirt', 'shoes', 'watch', 'coat', 'pant', 'dress', 'bag']) and not any(keyword in user_query for keyword in ['accessory', 'accessories']):
                            # This was likely a product search - try to get products from the AI response
                            ai_response = pair.get('ai', '')
                            if 'product' in ai_response.lower():
                                # Try a more liberal extraction
                                product_ids = re.findall(r'\b(\d{5,})\b', ai_response)  # Find all 5+ digit numbers
                                if product_ids:
                                    for pid in product_ids[:5]:  # Limit to 5 products
                                        extracted_products.append({
                                            'name': f"Product from search: {user_query[:50]}",
                                            'id': pid,
                                            'source': 'memory_user_query'
                                        })
                                        print(f"🧠 DEBUG: User query extraction - ID: {pid}")
                            break
                
        except Exception as e:
            print(f"🧠 DEBUG: Error in context extraction: {e}")
            import traceback
            traceback.print_exc()
            extracted_products = []
        
        # Enhanced debug output when no products found
        if not extracted_products:
            print("=" * 80)
            print("🚨 DEBUG: NO PRODUCTS EXTRACTED FOR ACCESSORIES SEARCH")
            print(f"🧠 Query received: {query[:300]}...")
            print(f"🧠 Query contains 'Context:'? {('Context:' in query)}")
            print(f"🧠 Query contains 'Product IDs:'? {('Product IDs:' in query) or ('Product ID:' in query)}")
            print(f"🧠 Query contains product names? {any(name in query.lower() for name in ['shirt', 'jacket', 'shoes', 'watch', 'coat', 'pant', 'dress'])}")
            print("=" * 80)
            
            # Check if the previous search actually returned results
            # Use the same session_id construction as above
            current_datetime = datetime.now()
            formatted_datetime = current_datetime.strftime("%d-%m-%y:%H")
            customer_id = os.environ.get('CURRENT_CUSTOMER_ID', 'default')
            check_session_id = f"{customer_id}_{formatted_datetime}" if customer_id else f"default_{formatted_datetime}"
            
            recent_context = memory.get_recent_context(session_id=check_session_id, num_pairs=2)
            no_products_in_previous_search = False
            
            if recent_context:
                last_ai_response = recent_context[0].get('ai', '').lower() if recent_context else ''
                no_products_in_previous_search = any(phrase in last_ai_response for phrase in [
                    "couldn't find any products",
                    "no products",
                    "0 products",
                    "apologize"
                ])
            
            if no_products_in_previous_search:
                return {
                    "response_type": "products_list",
                    "ai_response": "I couldn't find accessories because your previous search didn't return any products. Try searching for specific products first! For example: 'show me tshirts', 'find jackets', or 'show me shoes', then I can show you their accessories.",
                    "results": [],
                    "products_data": [],
                    "success": False
                }
            else:
                return {
                    "response_type": "products_list",
                    "ai_response": "I couldn't find which products you're referring to. Please search for some products first (like 'show me tshirts' or 'find jackets'), then I can show you their accessories!",
                    "results": [],
                    "products_data": [],
                    "success": False
                }
        
        print(f"🧠 DEBUG: Successfully extracted {len(extracted_products)} products for DATABASE accessory search")
        
        # Now search for accessories in the SAP_ACCESSORIES_COMMERCE_2211 database table
        try:
            conn = hana_connect()
            cursor = conn.cursor()
            
            # Search for accessories using the SAP_ACCESSORIES_COMMERCE_2211 table
            all_accessory_ids = set()
            found_mappings = 0
            
            print(f"🔍 Searching SAP_ACCESSORIES_COMMERCE_2211 table for accessories...")
            
            for idx, product in enumerate(extracted_products, 1):
                product_id = product['id'].strip() if product.get('id') else ''
                product_name = product.get('name', 'Unknown')
                print(f"\n🔍 [{idx}/{len(extracted_products)}] Searching: ID='{product_id}' Name='{product_name}'")
                
                if not product_id:
                    print(f"   ⚠️ SKIP: No ID")
                    continue
                
                try:
                    # Try exact match with debug
                    query_sql = "SELECT PRODUCT_IDS FROM SAP_ACCESSORIES_COMMERCE_2211 WHERE TRIM(PRODUCT_ID) = ?"
                    print(f"   📝 SQL: {query_sql} | Param: '{product_id}'")
                    cursor.execute(query_sql, (product_id,))
                    result = cursor.fetchone()
                    
                    if result and result[0]:
                        found_mappings += 1
                        accessory_ids_str = result[0].strip()
                        print(f"   ✅ FOUND! Accessories: {accessory_ids_str}")
                        
                        # Parse comma-separated accessory IDs
                        if accessory_ids_str:
                            accessory_ids = [aid.strip() for aid in accessory_ids_str.split(',') if aid.strip()]
                            all_accessory_ids.update(accessory_ids)
                            print(f"   ✅ Added {len(accessory_ids)} IDs | Total: {len(all_accessory_ids)}")
                    else:
                        print(f"   ❌ NOT FOUND")
                        # Check similar IDs
                        cursor.execute("SELECT TOP 3 PRODUCT_ID FROM SAP_ACCESSORIES_COMMERCE_2211 WHERE PRODUCT_ID LIKE ?", (f'%{product_id}%',))
                        similar = cursor.fetchall()
                        if similar:
                            print(f"   ℹ️ Similar: {[s[0].strip() for s in similar]}")
                        
                except Exception as e:
                    print(f"   ⚠️ ERROR: {e}")
                    continue
            
            print(f"� Total unique accessory IDs found: {len(all_accessory_ids)}")
            print(f"📊 Found mappings for {found_mappings}/{len(extracted_products)} products")
            
            if not all_accessory_ids:
                cursor.close()
                conn.close()
                return {
                    "results": [],
                    "products_data": [],
                    "ai_response": "No accessories found in database for your selected products.",
                    "response_type": "products_list",
                    "products_analyzed": len(extracted_products),
                    "mappings_found": found_mappings
                }
            
            # Get details for the accessory products (top 8)
            accessory_list = list(all_accessory_ids)[:8]  # Limit to top 8
            
            # Clean and validate accessory IDs before querying
            valid_accessory_ids = []
            for aid in accessory_list:
                # Remove any extra whitespace and validate
                clean_aid = str(aid).strip()
                if clean_aid and len(clean_aid) > 0:
                    # Check if it's a valid format (alphanumeric, dash, underscore)
                    if clean_aid.replace('-', '').replace('_', '').isalnum():
                        valid_accessory_ids.append(clean_aid)
                    else:
                        print(f"⚠️ Skipping invalid accessory ID format: '{clean_aid}'")
                else:
                    print(f"⚠️ Skipping empty accessory ID")
            
            print(f"🔍 Valid accessory IDs to query: {valid_accessory_ids}")
            
            if not valid_accessory_ids:
                cursor.close()
                conn.close()
                return {
                    "results": [],
                    "products_data": [],
                    "ai_response": "Found accessory mappings but no valid accessory IDs to retrieve details.",
                    "response_type": "products_list",
                    "products_analyzed": len(extracted_products),
                    "mappings_found": found_mappings
                }
            
            # Build safe SQL query with proper parameter binding
            placeholders = ','.join(['?' for _ in valid_accessory_ids])
            
            # Get current date for active promotions
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Try V2 table first with PROMOTION JOIN
            accessory_query = f"""
                SELECT TOP 8 
                    p.PRODUCT_ID, p.PRODUCT_NAME, p.SUMMARY, p.PRICE, p.CATEGORY_IDs, p.IMAGE_URL,
                    promo.PROMO_ID,
                    promo.PROMO_TITLE,
                    promo.PROMO_DESCRIPTION,
                    promo.PROMO_DISCOUNT_PERCENT,
                    promo.PROMO_END_DATE,
                    -- Calculate final price with discount
                    CASE 
                        WHEN promo.PROMO_DISCOUNT_PERCENT IS NOT NULL 
                        THEN p.PRICE * (1 - promo.PROMO_DISCOUNT_PERCENT / 100.0)
                        ELSE p.PRICE
                    END AS FINAL_PRICE
                FROM SAP_PRODUCTS_COMMERCE_2211_V2 p
                LEFT JOIN SAP_PROMOTION_COMMERCE_2211_V2 promo 
                    ON TRIM(p.PRODUCT_ID) = TRIM(promo.PROMO_PRODUCT_ID)
                    AND promo.PROMO_START_DATE <= '{today}'
                    AND promo.PROMO_END_DATE >= '{today}'
                WHERE TRIM(p.PRODUCT_ID) IN ({placeholders})
                ORDER BY FINAL_PRICE ASC
            """
            
            print(f"🔍 Fetching accessory details for {len(valid_accessory_ids)} accessories with promotion data")
            print(f"🔍 Accessory IDs: {valid_accessory_ids}")
            cursor.execute(accessory_query, valid_accessory_ids)
            accessory_rows = cursor.fetchall()
            
            print(f"📊 V2 table returned {len(accessory_rows)} rows")
            
            # If V2 table returns nothing, try without TRIM
            if not accessory_rows:
                print(f"⚠️ No results, trying without TRIM...")
                accessory_query = f"""
                    SELECT TOP 8 
                        p.PRODUCT_ID, p.PRODUCT_NAME, p.SUMMARY, p.PRICE, p.CATEGORY_IDs, p.IMAGE_URL,
                        promo.PROMO_ID,
                        promo.PROMO_TITLE,
                        promo.PROMO_DESCRIPTION,
                        promo.PROMO_DISCOUNT_PERCENT,
                        promo.PROMO_END_DATE,
                        CASE 
                            WHEN promo.PROMO_DISCOUNT_PERCENT IS NOT NULL 
                            THEN p.PRICE * (1 - promo.PROMO_DISCOUNT_PERCENT / 100.0)
                            ELSE p.PRICE
                        END AS FINAL_PRICE
                    FROM SAP_PRODUCTS_COMMERCE_2211_V2 p
                    LEFT JOIN SAP_PROMOTION_COMMERCE_2211_V2 promo 
                        ON p.PRODUCT_ID = promo.PROMO_PRODUCT_ID
                        AND promo.PROMO_START_DATE <= '{today}'
                        AND promo.PROMO_END_DATE >= '{today}'
                    WHERE p.PRODUCT_ID IN ({placeholders})
                    ORDER BY FINAL_PRICE ASC
                """
                cursor.execute(accessory_query, valid_accessory_ids)
                accessory_rows = cursor.fetchall()
                print(f"📊 Without TRIM returned {len(accessory_rows)} rows")
            
            accessories = []
            for row in accessory_rows:
                # Handle promotion data
                has_promotion = row[6] is not None and row[9] is not None
                original_price = float(row[3]) if row[3] else 0.0
                
                if has_promotion:
                    discount_percent = float(row[9])
                    # Use promotion_helper to calculate discounted price correctly
                    discounted_price = calculate_discounted_price(original_price, discount_percent)
                    savings_amount = round(original_price - discounted_price, 2)
                    print(f"   ✅ {row[1]} - £{original_price} -> £{discounted_price} ({discount_percent}% off, Save £{savings_amount})")
                else:
                    discount_percent = 0
                    discounted_price = original_price
                    savings_amount = 0
                    print(f"   ✅ {row[1]} - £{original_price}")
                
                accessory = {
                    'PRODUCT_ID': str(row[0]) if row[0] else '',
                    'PRODUCT_NAME': str(row[1]) if row[1] else '',
                    'SUMMARY': str(row[2]) if row[2] else '',
                    'PRICE': original_price,  # Keep PRICE as original for frontend
                    'price': discounted_price,  # lowercase price for display
                    'original_price': original_price,
                    'ORIGINAL_PRICE': original_price,
                    'CATEGORY_IDs': str(row[4]) if row[4] else '',
                    'IMAGE_URL': str(row[5]) if row[5] else '',
                    'has_promotion': has_promotion,
                    'discount_percent': discount_percent,
                    'discounted_price': discounted_price,
                    'DISCOUNTED_PRICE': discounted_price,
                    'savings': savings_amount,
                    'PROMO_TITLE': str(row[7]) if row[7] else '',
                    'PROMO_DESCRIPTION': str(row[8]) if row[8] else '',
                    'PROMO_DISCOUNT_PERCENT': discount_percent,
                    'promo_title': str(row[7]) if row[7] else ''
                }
                accessories.append(accessory)
            
            cursor.close()
            conn.close()
            
            if accessories:
                # Format accessories for product display with consistent field names INCLUDING PROMOTIONS
                formatted_accessories = []
                for acc in accessories:
                    formatted_accessories.append({
                        'product_id': acc['PRODUCT_ID'],  # lowercase for frontend
                        'product_name': acc['PRODUCT_NAME'],
                        'summary': acc['SUMMARY'],
                        'price': acc['price'],  # lowercase price is the display price (discounted if promo)
                        'original_price': acc['original_price'],
                        'discount_percent': acc['discount_percent'],
                        'discounted_price': acc['discounted_price'],
                        'savings': acc['savings'],
                        'has_promotion': acc['has_promotion'],
                        'promo_title': acc['promo_title'],
                        'image_url': acc['IMAGE_URL'],
                        'PRODUCT_ID': acc['PRODUCT_ID'],  # Keep uppercase for compatibility
                        'PRODUCT_NAME': acc['PRODUCT_NAME'],
                        'SUMMARY': acc['SUMMARY'],
                        'PRICE': acc['PRICE'],  # PRICE stays as original
                        'ORIGINAL_PRICE': acc['ORIGINAL_PRICE'],
                        'IMAGE_URL': acc['IMAGE_URL'],
                        'PROMO_TITLE': acc['PROMO_TITLE'],
                        'PROMO_DISCOUNT_PERCENT': acc['PROMO_DISCOUNT_PERCENT']
                    })
                
                searched_products = [p.get('name', f"Product {p.get('id', '')}") for p in extracted_products if p.get('name') or p.get('id')]
                product_names_str = ', '.join(searched_products[:3])  # Limit to 3 names to keep message short
                if len(searched_products) > 3:
                    product_names_str += f" and {len(searched_products) - 3} more"
                
                return {
                    "results": formatted_accessories,
                    "products_data": formatted_accessories,  # Add products_data for frontend
                    "ai_response": f"I found {len(accessories)} accessories that perfectly complement {product_names_str}! These are curated matches from our database.",
                    "response_type": "products_list",  # Changed to products_list so frontend renders cards
                    "products_analyzed": len(extracted_products),
                    "mappings_found": found_mappings,
                    "total_found": len(accessories)
                }
            else:
                return {
                    "results": [],
                    "products_data": [],
                    "ai_response": "I couldn't find any accessories in our database for the selected products. Try searching for different products!",
                    "response_type": "products_list",
                    "products_analyzed": len(extracted_products),
                    "mappings_found": found_mappings
                }
                
        except Exception as e:
            print(f"🧠 ERROR in database accessory search: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Provide helpful error message based on the error type
            error_msg = str(e)
            if "no attribute" in error_msg.lower() or "keyerror" in error_msg.lower():
                helpful_msg = "I had trouble finding product context. Please search for products first (like 'show me jackets' or 'find tshirts'), then ask for accessories."
            elif "connection" in error_msg.lower() or "database" in error_msg.lower():
                helpful_msg = "I'm having trouble connecting to the database. Please try again in a moment."
            else:
                helpful_msg = "I encountered an error while searching for accessories. Please search for products first, then try asking for accessories again."
            
            return {
                "error": f"Error searching for accessories: {str(e)}",
                "response_type": "products_list",
                "results": [],
                "products_data": [],
                "ai_response": helpful_msg
            }
    
    # If not an accessory request, return error
    return {
        "error": "This function is for accessory searches only",
        "response_type": "products_list",
        "results": [],
        "products_data": [],
        "ai_response": "This function is for accessory searches. Please search for products first."
    }

################Accessories code Here Ends ##################

################ AI-Driven Product Keyword Extraction ##################
def extract_product_keywords_ai(product_names: list) -> set:
    """
    🤖 AI-DRIVEN APPROACH: Intelligently extract product type keywords from product names.
    No hardcoding - uses AI to understand ANY product type dynamically!
    
    Args:
        product_names: List of product names from order history
        
    Returns:
        Set of intelligent product type keywords for search
    """
    try:
        if not product_names:
            return set()
        
        # Combine product names for AI analysis
        products_text = '\n'.join([f"- {name}" for name in product_names])
        
        keyword_extraction_prompt = f"""
You are an intelligent product keyword extractor for e-commerce search.

Analyze these product names and extract the CORE PRODUCT TYPE keywords:

{products_text}

CRITICAL INSTRUCTIONS:
1. Identify the PRIMARY product type for each item
2. Return ONLY individual keywords separated by commas
3. Use singular form (e.g., "shoe" not "shoes")
4. Each keyword should be ONE WORD ONLY
5. No grouping, no explanations, just comma-separated single words

EXAMPLES:
Input: "Shades Anon Crusher polar black grey polarized"
Output: sunglass, shades, eyewear

Input: "Cap Blue Tomato BT Snow Trucker Cap black"
Output: cap, hat

Input: "Classic Analog Watch"
Output: watch, timepiece

Input: "Sneakers Vans Old Skool black/white"
Output: shoe, sneaker, footwear

Return ONLY comma-separated single-word keywords:
"""
        
        response = llm.invoke(keyword_extraction_prompt)
        keywords_text = response.content.strip()
        
        print(f"🤖 Raw AI response: '{keywords_text}'")
        
        # Robust parsing: handle any format the AI returns
        keywords = set()
        
        # Replace newlines with commas for consistent splitting
        keywords_text = keywords_text.replace('\n', ',')
        
        # Split by commas and clean each keyword
        for part in keywords_text.split(','):
            cleaned = part.strip().lower()
            # Remove any punctuation
            cleaned = cleaned.replace('.', '').replace('"', '').replace("'", '').replace('→', '').strip()
            # Skip empty strings, very short words, and common filler words
            if cleaned and len(cleaned) > 2 and cleaned not in ['and', 'the', 'for', 'with']:
                keywords.add(cleaned)
        
        print(f"🤖 AI extracted keywords from {len(product_names)} products: {keywords}")
        return keywords
        
    except Exception as e:
        print(f"❌ AI keyword extraction failed: {e}")
        traceback.print_exc()
        
        # Intelligent fallback: extract first meaningful word from each product name
        fallback_keywords = set()
        for product_name in product_names:
            words = product_name.lower().split()
            for word in words:
                # Skip common words and take first meaningful product word
                if word not in ['the', 'a', 'an', 'and', 'or', 'for', 'with', 'blue', 'red', 'black', 'white']:
                    if len(word) > 3:  # Meaningful word length
                        fallback_keywords.add(word)
                        break  # Take first meaningful word only
        
        print(f"⚠️ Using fallback keyword extraction: {fallback_keywords}")
        return fallback_keywords

################ Personalized Recommendations Tool ##################
@tool("get_personalized_recommendations", args_schema=SearchInput, return_direct=True, description=(
    "🎯 Get AI-powered personalized product recommendations based on customer's last 2 orders."
    "Shows similar products from the SAME categories as user's recent purchases."
    "Input: customer_id (email)"
    "Returns: Minimum 5 products similar to their purchase history (watches → MORE watches, jackets → MORE jackets)"
    "Uses intelligent 3-tier system: 1) Category matching, 2) AI semantic search, 3) General recommendations"
))
def get_personalized_recommendations(query: str) -> dict:
    """
    Get AI-powered personalized product recommendations based on last 2 orders.
    Shows similar products from the same categories as user's recent purchases.
    """
    try:
        print(f"🎯 Getting personalized recommendations for query: {query}")
        
        # Extract customer_id from query
        import re
        customer_id_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', query)
        if not customer_id_match:
            return {
                "error": "Customer ID (email) required for personalized recommendations",
                "results": []
            }
        
        customer_id = customer_id_match.group(1)
        page_size = 8  # Default page size
        
        print(f"📧 Customer: {customer_id}")
        
        conn = hana_connect()
        cursor = conn.cursor()
        
        # Get customer's LAST 2 orders with product details
        order_history_sql = """
            SELECT o.PRODUCT_ID, o.PRODUCT_NAME, o.TOTAL_PRICE, o.ORDER_DATE,
                   p.CATEGORY_IDs, p.SUMMARY, p.PRICE
            FROM SAP_ORDERS_COMMERCE_2211_V2 o
            LEFT JOIN SAP_PRODUCTS_COMMERCE_2211_V2 p ON o.PRODUCT_ID = p.PRODUCT_ID
            WHERE o.CUSTOMER_ID = ?
            ORDER BY o.ORDER_DATE DESC
            LIMIT 2
        """
        
        cursor.execute(order_history_sql, (customer_id,))
        order_history = cursor.fetchall()
        
        if not order_history or len(order_history) == 0:
            cursor.close()
            conn.close()
            return {
                "results": [],
                "ai_response": "No order history found. Start shopping to get personalized recommendations!",
                "personalized": False
            }
        
        print(f"📦 Found {len(order_history)} recent orders")
        
        # Extract categories and product info
        purchased_ids = [order[0] for order in order_history]
        all_categories = []
        purchased_products_info = []
        
        print(f"🔍 Analyzing orders:")
        for i, order in enumerate(order_history, 1):
            product_name = order[1]
            category_ids = order[4]
            
            purchased_products_info.append(product_name)
            print(f"   {i}. {product_name} (Categories: {category_ids})")
            
            if category_ids:
                categories = str(category_ids).split(',')
                all_categories.extend([cat.strip() for cat in categories if cat.strip()])
        
        unique_categories = list(set(all_categories))
        print(f"✨ Unique categories: {unique_categories}")
        
        # 🤖 AI-DRIVEN PRODUCT KEYWORD EXTRACTION (No hardcoding!)
        product_keywords = extract_product_keywords_ai(purchased_products_info)
        print(f"🔑 AI-extracted product keywords: {product_keywords}")
        
        # Build search conditions (categories + keywords)
        search_conditions = []
        search_params = []
        
        for cat in unique_categories:
            search_conditions.append("UPPER(CATEGORY_IDs) LIKE UPPER(?)")
            search_params.append(f"%{cat}%")
        
        for keyword in product_keywords:
            search_conditions.append("UPPER(PRODUCT_NAME) LIKE UPPER(?)")
            search_params.append(f"%{keyword}%")
        
        if not search_conditions:
            # No categories or keywords - use AI semantic search
            search_query = ' '.join(purchased_products_info)
            query_vector = get_embedding(search_query)
            
            if query_vector and len(query_vector) == 768:
                query_vector_str = "[" + ",".join(map(str, query_vector)) + "]"
                
                rec_sql = f"""
                    SELECT PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, IMAGE_URL, CATEGORY_IDs,
                           (COSINE_SIMILARITY(VECTOR_NAME, TO_REAL_VECTOR(?)) * 0.7 +
                            COSINE_SIMILARITY(VECTOR_SUMMARY, TO_REAL_VECTOR(?)) * 0.3) AS SCORE
                    FROM SAP_PRODUCTS_COMMERCE_2211_V2
                    WHERE PRODUCT_ID NOT IN ({','.join(['?' for _ in purchased_ids])})
                    AND PRICE > 0
                    AND VECTOR_NAME IS NOT NULL
                    ORDER BY SCORE DESC
                    LIMIT ?
                """
                query_params = [query_vector_str, query_vector_str] + purchased_ids + [page_size]
            else:
                rec_sql = f"""
                    SELECT PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, IMAGE_URL, CATEGORY_IDs
                    FROM SAP_PRODUCTS_COMMERCE_2211_V2
                    WHERE PRODUCT_ID NOT IN ({','.join(['?' for _ in purchased_ids])})
                    AND PRICE > 0
                    ORDER BY PRICE ASC
                    LIMIT ?
                """
                query_params = purchased_ids + [page_size]
        else:
            # Use category + keyword search
            combined_conditions = ' OR '.join(search_conditions)
            
            rec_sql = f"""
                SELECT PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, IMAGE_URL, CATEGORY_IDs
                FROM SAP_PRODUCTS_COMMERCE_2211_V2
                WHERE PRODUCT_ID NOT IN ({','.join(['?' for _ in purchased_ids])})
                AND PRICE > 0
                AND ({combined_conditions})
                ORDER BY PRICE ASC
                LIMIT ?
            """
            
            query_params = purchased_ids + search_params + [page_size]
        
        cursor.execute(rec_sql, query_params)
        recommended_products = cursor.fetchall()
        
        print(f"📊 Found {len(recommended_products)} products")
        
        # Ensure minimum 5 products
        if len(recommended_products) < 5 and product_keywords:
            print(f"⚠️ Less than 5 products, broadening search...")
            
            broader_conditions = [f"UPPER(PRODUCT_NAME) LIKE UPPER(?)" for _ in product_keywords]
            broader_params = [f"%{kw}%" for kw in product_keywords]
            
            broader_sql = f"""
                SELECT PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, IMAGE_URL, CATEGORY_IDs
                FROM SAP_PRODUCTS_COMMERCE_2211_V2
                WHERE PRODUCT_ID NOT IN ({','.join(['?' for _ in purchased_ids])})
                AND PRICE > 0
                AND ({' OR '.join(broader_conditions)})
                ORDER BY PRICE ASC
                LIMIT ?
            """
            
            cursor.execute(broader_sql, purchased_ids + broader_params + [page_size])
            broader_products = cursor.fetchall()
            
            existing_ids = {p[0] for p in recommended_products}
            for product in broader_products:
                if product[0] not in existing_ids:
                    recommended_products.append(product)
                    if len(recommended_products) >= page_size:
                        break
            
            print(f"📊 After broadening: {len(recommended_products)} products")
        
        cursor.close()
        conn.close()
        
        # Format results
        results = []
        for product in recommended_products:
            product_dict = {
                'PRODUCT_ID': product[0],
                'PRODUCT_NAME': product[1],
                'SUMMARY': product[2] or 'Recommended based on your purchases',
                'PRICE': float(product[3]) if product[3] else 0.0,
                'IMAGE_URL': product[4] or '',
                'CATEGORY_IDs': product[5]
            }
            results.append(product_dict)
        
        # Generate AI message
        if unique_categories:
            cat_names = ', '.join(unique_categories[:2])
            ai_message = f"💝 Based on your recent {cat_names} purchases, here are {len(results)} perfect matches for you!"
        else:
            ai_message = f"💝 Based on your shopping history, we found {len(results)} great products for you!"
        
        print(f"✅ Returning {len(results)} personalized recommendations")
        
        return {
            "results": results,
            "ai_response": ai_message,
            "personalized": True,
            "categories_used": unique_categories,
            "total": len(results)
        }
        
    except Exception as e:
        print(f"❌ Error in personalized recommendations: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "results": []
        }

################ Context-Aware Price Filter Tool ##################
@tool("ai_context_price_filter", args_schema=SearchInput, return_direct=True, description=(
    "🧠 ENHANCED PRICE FILTERING TOOL - Use for ANY query containing price constraints!"
    "🎯 IMMEDIATE USE for price queries like: 'tshirts under 30 pounds', 'jackets between 50-100', 'shoes over 80 dollars'"
    "💡 SMART FEATURE: Automatically understands both category AND price from single query."
    "🔍 PERFECT FOR: 'show tshirts under 30 pounds', 'find jackets between 50 to 100 pounds', 'watches over 100'"
    "📊 ENHANCED PARSER: Uses advanced natural language understanding for prices."
    "💰 SUPPORTS: 'under X', 'below X', 'above X', 'over X', 'between X and Y', 'less than X', 'more than X'."
    "🌍 MULTI-CURRENCY: Handles pounds, dollars, euros, and currency-free numeric values."
    "⚡ TRIGGER WORDS: ANY price mention - 'under', 'below', 'above', 'over', 'between', '£', '$', 'pounds', 'dollars'"
    "� CRITICAL: Use THIS tool (not ai_semantic_product_search) when user mentions prices!"
    "❌ RULE: If query contains price terms, use this tool immediately - it handles both category and price together!"
))
def ai_context_price_filter(query: str) -> dict:
    """
    Intelligent context-aware price filtering that understands what products the user is referring to
    from their previous search history and applies price constraints intelligently.
    """
    print(f"🧠 AI Context Price Filter initiated for: '{query}'")
    
    try:
        # Step 1: Use AI to extract price constraints from the query
        price_info = extract_ai_price_constraints(query)
        print(f"💰 Extracted price info: {price_info}")
        
        if not price_info['has_price_constraint']:
            return {
                "error": "No price constraint detected in the query",
                "ai_response": "I couldn't find any price information in your query. Please specify a price range, like 'under 200 pounds' or 'between 50 and 100'.",
                "results": [],
                "products_data": [],
                "response_type": "products_list"
            }
        
        # Step 2: Use AI to extract product context from conversation history
        context_info = extract_ai_product_context(query)
        print(f"🎯 Extracted context info: {context_info}")
        
        # Step 3: Connect to database
        conn = hana_connect()
        cursor = conn.cursor()
        
        # Step 4: Build intelligent SQL query with AI-driven context and price filtering
        sql_query, params = build_context_aware_price_query(price_info, context_info)
        print(f"🔍 Generated SQL: {sql_query}")
        print(f"📝 Parameters: {params}")
        
        # Step 5: Execute the query
        cursor.execute(sql_query, params)
        rows = cursor.fetchall()
        
        # 🎯 NO FALLBACK: If specific category (like watches) not found at price, return empty
        # But find the cheapest product in that category to suggest
        cheapest_alternative = None
        if not rows and price_info.get('category'):
            print(f"⚠️ No products found matching category and price constraints")
            print(f"🔍 Looking for cheapest {price_info.get('category')} to suggest...")
            
            # Find cheapest product in the category (without price filter)
            category = price_info.get('category').lower()
            alt_sql = """
                SELECT TOP 1 PRODUCT_NAME, PRICE
                FROM SAP_PRODUCTS_COMMERCE_2211_V2
                WHERE (
                    UPPER(PRODUCT_NAME) LIKE ? OR 
                    UPPER(SUMMARY) LIKE ? OR 
                    UPPER(CATEGORY_IDs) LIKE ?
                )
                ORDER BY PRICE ASC
            """
            search_term = f'%{category.upper()}%'
            cursor.execute(alt_sql, [search_term, search_term, search_term])
            alt_row = cursor.fetchone()
            
            if alt_row:
                cheapest_alternative = {
                    'name': alt_row[0].strip() if alt_row[0] else '',
                    'price': float(alt_row[1]) if alt_row[1] else 0
                }
                print(f"💡 Found cheapest alternative: {cheapest_alternative['name']} at £{cheapest_alternative['price']:.2f}")
        
        # Step 6: Process results WITH PROMOTION CALCULATION
        columns = [col[0] for col in cursor.description] if cursor.description else []
        results = [dict(zip(columns, row)) for row in rows] if rows else []
        
        # Clean up results for JSON serialization and add promotion info
        for result in results:
            # Convert decimal prices
            if 'PRICE' in result and result['PRICE'] is not None:
                from decimal import Decimal
                if isinstance(result['PRICE'], Decimal):
                    result['PRICE'] = float(result['PRICE'])
            
            # Handle promotion data (same as semantic search)
            has_promotion = result.get('PROMO_ID') is not None and result.get('PROMO_DISCOUNT_PERCENT') is not None
            result['has_promotion'] = has_promotion
            
            product_id = result.get('PRODUCT_ID', 'unknown')
            print(f"\n📦 Price Filter Product: {product_id} - {result.get('PRODUCT_NAME', 'N/A')}")
            
            if has_promotion:
                original_price = float(result['PRICE'])
                discount_percent = float(result['PROMO_DISCOUNT_PERCENT'])
                final_price = float(result['FINAL_PRICE']) if result.get('FINAL_PRICE') else original_price
                
                print(f"   ✅ HAS PROMOTION: {discount_percent}% off")
                print(f"      Original: £{original_price}, Final: £{final_price}")
                
                result['original_price'] = original_price
                result['discount_percent'] = discount_percent
                result['discounted_price'] = final_price
                result['savings'] = round(original_price - final_price, 2)
                result['price'] = final_price
                result['promo_title'] = result.get('PROMO_TITLE', '')
            else:
                print(f"   ℹ️  NO PROMOTION")
                result['original_price'] = result['PRICE']
                result['discount_percent'] = 0
                result['discounted_price'] = result['PRICE']
                result['savings'] = 0
                result['price'] = result['PRICE']
                result['promo_title'] = ''
        
        cursor.close()
        conn.close()
        
        # Step 7: Format results for frontend (both uppercase and lowercase keys)
        formatted_results = []
        for result in results:
            formatted_product = {
                # Lowercase keys for frontend
                'product_id': str(result.get('PRODUCT_ID', '')),
                'product_name': str(result.get('PRODUCT_NAME', '')),
                'summary': str(result.get('SUMMARY', '')),
                'price': float(result.get('price', result.get('PRICE', 0))),
                'image_url': str(result.get('IMAGE_URL', '')),
                'original_price': float(result.get('original_price', result.get('PRICE', 0))),
                'discounted_price': float(result.get('discounted_price', result.get('price', 0))),
                'discount_percent': float(result.get('discount_percent', 0)),
                'savings': float(result.get('savings', 0)),
                'has_promotion': bool(result.get('has_promotion', False)),
                'promo_title': str(result.get('promo_title', '')),
                # Uppercase keys for compatibility
                'PRODUCT_ID': str(result.get('PRODUCT_ID', '')),
                'PRODUCT_NAME': str(result.get('PRODUCT_NAME', '')),
                'SUMMARY': str(result.get('SUMMARY', '')),
                'PRICE': float(result.get('PRICE', 0)),
                'IMAGE_URL': str(result.get('IMAGE_URL', '')),
                'PROMO_TITLE': str(result.get('promo_title', '')),
                'PROMO_DISCOUNT_PERCENT': float(result.get('discount_percent', 0))
            }
            formatted_results.append(formatted_product)
        
        # Step 8: Generate intelligent AI response (with alternative suggestion if available)
        ai_response = generate_context_price_response(price_info, context_info, len(formatted_results), cheapest_alternative)
        
        print(f"✅ Context-aware price filter found {len(formatted_results)} products")
        
        return {
            "results": formatted_results,
            "products_data": formatted_results,  # Add products_data for frontend carousel
            "ai_response": ai_response,
            "response_type": "products_list",  # Changed to products_list so frontend renders carousel
            "price_constraint": price_info,
            "context_used": context_info,
            "total_found": len(formatted_results),
            "cheapest_alternative": cheapest_alternative
        }
        
    except Exception as e:
        print(f"❌ AI Context Price Filter Error: {str(e)}")
        import traceback
        print(f"🔍 Full traceback: {traceback.format_exc()}")
        
        return {
            "error": f"Context-aware price filtering failed: {str(e)}",
            "ai_response": "I encountered an issue while filtering products by price. Please try rephrasing your price query.",
            "results": [],
            "products_data": [],
            "response_type": "products_list"
        }

def extract_ai_price_constraints(query: str) -> dict:
    """
    Use enhanced query parser to intelligently extract price constraints from natural language
    """
    price_min, price_max = None, None
    category = None
    
    try:
        # Try using enhanced query parser first
        from tools.query_parser import query_parser
        
        filters = query_parser.parse_query(query)
        price_min = filters.price_min
        price_max = filters.price_max
        category = filters.category
        print(f"🚀 Enhanced parser extracted: min={price_min}, max={price_max}, category={category}")
        
    except Exception as e:
        print(f"⚠️ Enhanced parser failed: {str(e)}, using direct regex fallback")
        # Direct regex fallback if query_parser import fails
        query_lower = query.lower()
        
        # Extract category directly from query
        category_keywords = {
            'tshirt': ['tshirt', 't-shirt', 'tee', 'tshirts', 't-shirts', 'tees'],
            'jacket': ['jacket', 'jackets', 'coat', 'coats'],
            'shoes': ['shoe', 'shoes', 'sneaker', 'sneakers', 'boot', 'boots'],
            'watch': ['watch', 'watches'],
            'accessories': ['accessory', 'accessories', 'belt', 'bag', 'hat']
        }
        
        for cat, keywords in category_keywords.items():
            if any(kw in query_lower for kw in keywords):
                category = cat
                break
        
        # Extract price using direct regex (robust fallback)
        # Pattern for "under X", "below X", "less than X"
        under_match = re.search(r'(?:under|below|less\s+than|up\s+to|max)\s*[£$€]?\s*(\d+(?:\.\d{2})?)', query_lower)
        if under_match:
            price_max = float(under_match.group(1))
            print(f"✅ Regex found max price: {price_max}")
        
        # Pattern for "over X", "above X", "more than X"  
        over_match = re.search(r'(?:over|above|more\s+than|at\s+least|min)\s*[£$€]?\s*(\d+(?:\.\d{2})?)', query_lower)
        if over_match:
            price_min = float(over_match.group(1))
            print(f"✅ Regex found min price: {price_min}")
        
        # Pattern for range "X to Y", "between X and Y"
        range_match = re.search(r'(?:between\s+)?[£$€]?\s*(\d+(?:\.\d{2})?)\s*(?:to|and|-)\s*[£$€]?\s*(\d+(?:\.\d{2})?)', query_lower)
        if range_match:
            price_min = float(range_match.group(1))
            price_max = float(range_match.group(2))
            print(f"✅ Regex found price range: {price_min} to {price_max}")
    
    # Determine constraint type
    constraint_type = "none"
    if price_min is not None and price_max is not None:
        constraint_type = "between"
    elif price_max is not None:
        constraint_type = "under"
    elif price_min is not None:
        constraint_type = "over"
    
    # Detect currency from the query
    currency_mentioned = "none"
    query_lower = query.lower()
    if any(curr in query_lower for curr in ['pound', 'pounds', '£', 'gbp']):
        currency_mentioned = "pounds"
    elif any(curr in query_lower for curr in ['dollar', 'dollars', '$', 'usd']):
        currency_mentioned = "dollars"
    elif any(curr in query_lower for curr in ['euro', 'euros', '€', 'eur']):
        currency_mentioned = "euros"
    
    has_price_constraint = price_min is not None or price_max is not None
    
    result = {
        "has_price_constraint": has_price_constraint,
        "min_price": price_min,
        "max_price": price_max,
        "constraint_type": constraint_type,
        "currency_mentioned": currency_mentioned,
        "original_text": query,
        "category": category,
        "enhanced_parser_used": category is not None or (price_min is not None or price_max is not None)
    }
    
    print(f"💰 Final price constraints: {result}")
    return result

def extract_ai_product_context(query: str) -> dict:
    """
    Use AI to extract product context from conversation memory and current query
    """
    try:
        # Get recent conversation context from memory
        session_id = "default"
        recent_context = memory.get_recent_context(session_id, num_pairs=10)  # Increased to get more context
        
        print(f"🧠 DEBUG: Retrieved {len(recent_context)} conversation pairs from memory")
        
        # Build context for AI analysis
        context_text = ""
        for i, pair in enumerate(recent_context):
            user_query = pair.get('user', '')
            ai_response = pair.get('ai', '')
            context_text += f"Exchange {i+1}:\nUser: {user_query}\nAI: {ai_response}\n\n"
        
        print(f"🧠 DEBUG: Context text for AI analysis (first 500 chars): {context_text[:500]}...")
        
        context_prompt = f"""
        You are an AI context analyzer for e-commerce product searches.
        
        Current Query: "{query}"
        
        Recent Conversation Context:
        {context_text}
        
        Analyze the conversation to determine what product category the user is referring to in their current price query.
        Look for the most recent product search that would be relevant to the current price constraint.
        
        Focus on finding:
        1. Product categories mentioned (jackets, shoes, shirts, watches, etc.)
        2. Specific product names or types
        3. Shopping context that would apply to price filtering
        
        Return ONLY a JSON object with this structure:
        {{
            "has_product_context": true/false,
            "product_category": "jackets" or "shoes" or "shirts" or "watches" or "bags" or "pants" or "general",
            "context_confidence": "high" or "medium" or "low",
            "detected_products": ["product1", "product2"],
            "search_strategy": "category_based" or "name_based" or "general",
            "reasoning": "brief explanation of why this category was chosen"
        }}
        
        Examples:
        - If user recently searched "jackets" and now asks "under 200 pounds" → product_category: "jackets"
        - If user recently searched "Nike shoes" and now asks "below 150" → product_category: "shoes" 
        - If no clear context → product_category: "general", has_product_context: false
        """
        
        response = llm.invoke(context_prompt)
        result = response.content.strip()
        
        print(f"🧠 DEBUG: AI context analysis response: {result}")
        
        # Parse JSON response
        import json
        try:
            # Clean markdown formatting from AI response
            clean_result = result.strip()
            if clean_result.startswith('```json'):
                clean_result = clean_result[7:]  # Remove ```json
            if clean_result.endswith('```'):
                clean_result = clean_result[:-3]  # Remove trailing ```
            clean_result = clean_result.strip()
            
            context_info = json.loads(clean_result)
            print(f"🧠 AI detected context: {context_info}")
            return context_info
        except json.JSONDecodeError:
            print(f"Failed to parse AI context response: {result}")
            return {
                "has_product_context": False, 
                "product_category": "general",
                "search_strategy": "general",
                "reasoning": "Failed to parse AI response"
            }
            
    except Exception as e:
        print(f"Product context extraction failed: {e}")
        return {
            "has_product_context": False, 
            "product_category": "general",
            "search_strategy": "general",
            "reasoning": f"Error: {str(e)}"
        }

def build_context_aware_price_query(price_info: dict, context_info: dict) -> tuple:
    """
    Build intelligent SQL query based on price constraints and product context
    """
    try:
        print(f"🔍 Building query with price_info: {price_info}")
        print(f"🔍 Building query with context_info: {context_info}")
        
        # Get current date for active promotions
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Base query structure - V2 table with DECIMAL price and PROMOTIONS
        base_sql = f"""
            SELECT TOP 5 
                p.PRODUCT_ID, p.PRODUCT_NAME, p.SUMMARY, p.PRICE, p.CATEGORY_IDs, p.IMAGE_URL,
        promo.PROMO_ID,
                promo.PROMO_TITLE,
                promo.PROMO_DESCRIPTION,
                promo.PROMO_DISCOUNT_PERCENT,
                promo.PROMO_END_DATE,
                -- Calculate final price with discount
                CASE 
                    WHEN promo.PROMO_DISCOUNT_PERCENT IS NOT NULL 
                    THEN p.PRICE * (1 - promo.PROMO_DISCOUNT_PERCENT / 100.0)
                    ELSE p.PRICE
                END AS FINAL_PRICE
            FROM SAP_PRODUCTS_COMMERCE_2211_V2 p
            LEFT JOIN SAP_PROMOTION_COMMERCE_2211_V2 promo 
                ON TRIM(p.PRODUCT_ID) = TRIM(promo.PROMO_PRODUCT_ID)
                AND promo.PROMO_START_DATE <= '{today}'
                AND promo.PROMO_END_DATE >= '{today}'
            WHERE 1=1
        """
        
        conditions = []
        params = []
        
        # Add price constraints using FINAL_PRICE (discounted price) with proper DECIMAL handling
        if price_info.get('min_price'):
            conditions.append("(CASE WHEN promo.PROMO_DISCOUNT_PERCENT IS NOT NULL THEN p.PRICE * (1 - promo.PROMO_DISCOUNT_PERCENT / 100.0) ELSE p.PRICE END) >= ?")
            params.append(float(price_info['min_price']))
            print(f"💰 Added minimum price constraint: >= {price_info['min_price']}")
            
        if price_info.get('max_price'):
            conditions.append("(CASE WHEN promo.PROMO_DISCOUNT_PERCENT IS NOT NULL THEN p.PRICE * (1 - promo.PROMO_DISCOUNT_PERCENT / 100.0) ELSE p.PRICE END) <= ?")
            params.append(float(price_info['max_price']))
            print(f"💰 Added maximum price constraint: <= {price_info['max_price']}")
        
        # Apply price constraints to base query
        if conditions:
            base_sql += " AND " + " AND ".join(conditions)
        
        # Add context-based product filtering - Enhanced with query parser category
        category_to_filter = None
        
        # First, try to use category from enhanced parser
        if price_info.get('category'):
            category_to_filter = price_info['category'].lower()
            print(f"🚀 Using enhanced parser category: {category_to_filter}")
        # Fallback to context info
        elif context_info.get('has_product_context') and context_info.get('product_category') != 'general':
            category_to_filter = context_info['product_category'].lower()
            print(f"🎯 Using context category: {category_to_filter}")
        
        # Enhanced category filtering - Search broadly but prioritize relevant categories
        category_scoring = ""
        
        if category_to_filter:
            print(f"🔍 Adding category preference for: {category_to_filter}")
            
            # Instead of restricting results, we'll add scoring to prioritize relevant products
            if category_to_filter in ['jackets', 'jacket']:
                # Still add some basic filtering but make it broader
                category_scoring = """
                    AND (
                        UPPER(PRODUCT_NAME) LIKE '%JACKET%' OR UPPER(SUMMARY) LIKE '%JACKET%' 
                        OR UPPER(PRODUCT_NAME) LIKE '%COAT%' OR UPPER(SUMMARY) LIKE '%COAT%'
                        OR UPPER(CATEGORY_IDs) LIKE '%JACKET%' OR UPPER(CATEGORY_IDs) LIKE '%COAT%'
                        OR UPPER(CATEGORY_IDs) LIKE '%OUTERWEAR%' OR UPPER(CATEGORY_IDs) LIKE '%BLAZER%'
                        OR UPPER(PRODUCT_NAME) LIKE '%HOODIE%' OR UPPER(PRODUCT_NAME) LIKE '%CARDIGAN%'
                    )
                """
                print("🧥 Added comprehensive jacket/coat/outerwear filter")
            elif category_to_filter in ['shoes', 'shoe']:
                category_scoring = """
                    AND (
                        UPPER(CATEGORY_IDs) LIKE '%SHOES%' OR UPPER(PRODUCT_NAME) LIKE '%SHOE%' 
                        OR UPPER(PRODUCT_NAME) LIKE '%BOOT%' OR UPPER(PRODUCT_NAME) LIKE '%SNEAKER%' 
                        OR UPPER(SUMMARY) LIKE '%FOOTWEAR%' OR UPPER(CATEGORY_IDs) LIKE '%FOOTWEAR%'
                    )
                """
                print("👟 Added flexible shoes/footwear filter")
            elif category_to_filter in ['shirts', 'shirt']:
                category_scoring = """
                    AND (
                        UPPER(PRODUCT_NAME) LIKE '%SHIRT%' OR UPPER(SUMMARY) LIKE '%SHIRT%' 
                        OR UPPER(PRODUCT_NAME) LIKE '%TEE%' OR UPPER(PRODUCT_NAME) LIKE '%T-SHIRT%'
                        OR UPPER(CATEGORY_IDs) LIKE '%SHIRT%'
                    )
                """
                print("👔 Added flexible shirts/tees filter")
            elif category_to_filter in ['watches', 'watch']:
                category_scoring = """
                    AND (
                        UPPER(PRODUCT_NAME) LIKE '%WATCH%' OR UPPER(SUMMARY) LIKE '%WATCH%' 
                        OR UPPER(SUMMARY) LIKE '%TIMEPIECE%' OR UPPER(CATEGORY_IDs) LIKE '%WATCH%'
                    )
                """
                print("⌚ Added flexible watches filter")
            elif category_to_filter in ['accessories', 'bags']:
                category_scoring = """
                    AND (
                        UPPER(PRODUCT_NAME) LIKE '%BAG%' OR UPPER(SUMMARY) LIKE '%BAG%'
                        OR UPPER(CATEGORY_IDs) LIKE '%BAG%' OR UPPER(CATEGORY_IDs) LIKE '%ACCESSORIES%'
                    )
                """
                print("👜 Added flexible bags/accessories filter")
            elif category_to_filter in ['pants', 'pant']:
                category_scoring = """
                    AND (
                        UPPER(PRODUCT_NAME) LIKE '%PANT%' OR UPPER(SUMMARY) LIKE '%PANT%' 
                        OR UPPER(PRODUCT_NAME) LIKE '%TROUSER%' OR UPPER(CATEGORY_IDs) LIKE '%PANT%'
                    )
                """
                print("👖 Added flexible pants/trousers filter")
            else:
                # For unknown categories, don't restrict - search all products
                print(f"🌐 Unknown category '{category_to_filter}' - searching all products with price filter only")
                category_scoring = ""
        else:
            print("🌐 No specific product category - searching all products")
        
        # Add category scoring to base query if we have one
        if category_scoring:
            base_sql += category_scoring
        
        # Add ordering - prioritize lower prices for better user experience
        base_sql += " ORDER BY PRICE ASC, PRODUCT_NAME"
        
        print(f"🔍 Final SQL query: {base_sql}")
        print(f"📝 Query parameters: {params}")
        
        return base_sql, params
        
    except Exception as e:
        print(f"❌ Query building failed: {e}")
        # Fallback query with just price constraints
        max_price = price_info.get('max_price', 1000)
        print(f"🔄 Using fallback query with max price: {max_price}")
        fallback_sql = "SELECT 0 PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, CATEGORY_IDs, IMAGE_URL FROM SAP_PRODUCTS_COMMERCE_2211_V2 WHERE PRICE <= ? ORDER BY PRICE ASC"
        fallback_params = [max_price]
        return fallback_sql, fallback_params

def generate_context_price_response(price_info: dict, context_info: dict, result_count: int, cheapest_alternative: dict = None) -> str:
    """
    Generate intelligent AI response based on context and results, with smart alternative suggestions
    """
    try:
        # Build price description
        price_desc = ""
        if price_info.get('constraint_type') == 'under':
            price_desc = f"under {price_info.get('max_price')} {price_info.get('currency_mentioned', '')}"
        elif price_info.get('constraint_type') == 'over':
            price_desc = f"over {price_info.get('min_price')} {price_info.get('currency_mentioned', '')}"
        elif price_info.get('constraint_type') == 'between':
            price_desc = f"between {price_info.get('min_price')} and {price_info.get('max_price')} {price_info.get('currency_mentioned', '')}"
        
        # Build context description
        if context_info.get('has_product_context'):
            category = context_info.get('product_category', 'products')
            if result_count > 0:
                return f"I found {result_count} {category} {price_desc.strip()}."
            else:
                # 🎯 SMART MESSAGE: Show cheapest alternative if available
                if cheapest_alternative and cheapest_alternative.get('price'):
                    suggested_price = int(cheapest_alternative['price'] + 10)  # Round up +10
                    return f"Sorry, I couldn't find any {category} {price_desc.strip()}.\n\n💡 The cheapest {category.rstrip('s')} I have is '{cheapest_alternative['name']}' at £{cheapest_alternative['price']:.2f}.\n\nWould you like to see {category} under £{suggested_price} instead?"
                else:
                    return f"Sorry, I couldn't find any {category} {price_desc.strip()}. You can try:\n• Increasing your price range\n• Searching for '{category}' without a price filter to see all available options\n• Trying a different product category"
        else:
            if result_count > 0:
                return f"I found {result_count} products {price_desc.strip()}."
            else:
                return f"Sorry, I couldn't find any products {price_desc.strip()}. Try adjusting your price range or search for specific categories like 'jackets', 'shoes', or 'watches'."
                
    except Exception as e:
        print(f"Response generation failed: {e}")
        return f"I found {result_count} products matching your price criteria."

################ Context-Aware Price Filter Tool Ends ##################

def detect_product_category_ai(query: str) -> str:
    """
    AI-driven product category detection for promotion searches
    """
    try:
        detection_prompt = f"""
        Analyze this promotional product search query and extract product category filters.
        
        Query: "{query}"
        
        If the query mentions specific product types, return SQL WHERE conditions to filter products.
        Use these database fields:
        - prod.CATEGORY_IDs (contains category names)
        - prod.PRODUCT_NAME (product names)
        - prod.SUMMARY (product descriptions)
        
        Examples:
        - "discounted t-shirts" → "(UPPER(prod.CATEGORY_IDS) LIKE '%SHIRT%' OR UPPER(prod.PRODUCT_NAME) LIKE '%SHIRT%' OR UPPER(prod.SUMMARY) LIKE '%SHIRT%')"
        - "shoes on sale" → "(UPPER(prod.CATEGORY_IDS) LIKE '%SHOE%' OR UPPER(prod.PRODUCT_NAME) LIKE '%SHOE%' OR UPPER(prod.SUMMARY) LIKE '%SHOE%')"
        - "jacket deals" → "(UPPER(prod.CATEGORY_IDS) LIKE '%JACKET%' OR UPPER(prod.PRODUCT_NAME) LIKE '%JACKET%' OR UPPER(prod.SUMMARY) LIKE '%JACKET%')"
        
        If no specific product type is mentioned, return: NONE
        
        Return only the SQL WHERE condition or NONE:
        """
        
        response = llm.invoke(detection_prompt)
        filter_condition = response.content.strip()
        
        if filter_condition == "NONE" or not filter_condition:
            return ""
        
        print(f"🤖 AI Product Category Filter: '{query}' → '{filter_condition}'")
        return filter_condition
        
    except Exception as e:
        print(f"AI product category detection failed: {e}")
        return ""

################ Promotion code Here ##################
@tool("search_products_with_promotions", args_schema=SearchInput, return_direct=True, description=(
    "🎯 GENERAL PROMOTIONS SEARCH - Use ONLY for discovering all promotional products with specific criteria"
    "🔍 USE WHEN: User asks for general promotion searches, discount filters, or browsing deals"
    "📝 EXAMPLES: 'Show me all products with discounts', 'Find T-shirts with price below 100', 'Products with 20-30% discount', 'Show promotional products ending in 10 days'"
    "⚠️ CRITICAL: DO NOT use for context-based offers (like 'any offers for these products') - use find_offers_for_products instead"
    "🧠 FEATURES: Price filtering, discount percentage ranges, category filtering, promotion end date filtering"
    "❌ NOT FOR: 'offers for these', 'deals on these', 'any offers' - these need context-aware tool"
    "✅ FOR: 'show all deals', 'products with discounts', 'promotional items', 'discounted T-shirts'"
))
def search_products_with_promotions(query: str) -> dict:
    """
    For additional category details, join with the SAP_CATEGORIES_COMMERCE_2211 table.
    """
    print(f"DEBUG: search_products_with_promotions called with query: {query}")
    try:
        import re
        from datetime import datetime, timedelta

        conn = hana_connect()
        cursor = conn.cursor()

        where_clauses = []
        today = datetime.today()

        def safe_number(value):
            try:
                return float(value)
            except:
                return None

        # Normalize currency mentions
        query = query.replace("pound", "").replace("£", "").strip()

        # Price filters
        price_below = re.search(r"(price\s*(below|under)|less\s*than)\s*(\d+)", query, re.IGNORECASE)
        price_above = re.search(r"(price\s*(above|more\s*than)|greater\s*than)\s*(\d+)", query, re.IGNORECASE)
        price_between = re.search(r"(price\s*)?between\s*(\d+)\s*(and|to)\s*(\d+)", query, re.IGNORECASE)

        if price_below:
            val = safe_number(price_below.group(3))
            if val is not None:
                where_clauses.append(f"prod.PRICE IS NOT NULL AND prod.PRICE < {val}")

        if price_above:
            val = safe_number(price_above.group(3))
            if val is not None:
                where_clauses.append(f"prod.PRICE IS NOT NULL AND prod.PRICE > {val}")

        if price_between:
            low = safe_number(price_between.group(2))
            high = safe_number(price_between.group(4))
            if low is not None and high is not None:
                where_clauses.append(f"prod.PRICE IS NOT NULL AND prod.PRICE BETWEEN {low} AND {high}")

        # Discount filters
        discount_above = re.search(r"(discount|offer\s*)?(more than|above|greater than)\s*(\d+)%", query, re.IGNORECASE)
        discount_between = re.search(r"(\d+)%\s*(to|and)\s*(\d+)%", query, re.IGNORECASE)

        if discount_above:
            val = discount_above.group(3)
            if val is not None:
                where_clauses.append(f"promo.PROMO_DISCOUNT_PERCENT IS NOT NULL AND promo.PROMO_DISCOUNT_PERCENT > {val}")

        if discount_between:
            low = safe_number(discount_between.group(1))
            high = safe_number(discount_between.group(3))
            if low is not None and high is not None:
                where_clauses.append(f"promo.PROMO_DISCOUNT_PERCENT IS NOT NULL AND promo.PROMO_DISCOUNT_PERCENT BETWEEN {low} AND {high}")

        # AI-driven category and product detection 
        category_product_filter = detect_product_category_ai(query)
        if category_product_filter:
            where_clauses.append(category_product_filter)

        # General offer/discount requirement
        offer_discount = re.search(r"\b(offer?|discount?|on offer?|discount on|promotion?)\b", query, re.IGNORECASE)
        if offer_discount:
            where_clauses.append(f"promo.PROMO_DISCOUNT_PERCENT > 0")

        # Festival filter
        if re.search(r"festival", query, re.IGNORECASE):
            where_clauses.append("LOWER(promo.PROMO_TITLE) LIKE '%festival%' OR LOWER(promo.PROMO_DESCRIPTION) LIKE '%festival%'")

        # Discount ending soon
        days_match = re.search(r"discount.*?(in\s+next\s+|ending\s+in\s+)(\d+)\s+days", query, re.IGNORECASE)
        if days_match:
            future_date = today + timedelta(days=int(days_match.group(2)))
            where_clauses.append(f"promo.PROMO_END_DATE <= '{future_date.strftime('%Y-%m-%d')}'")

        # Final SQL query
        sql_query = f"""
            SELECT TOP 5 prod.PRODUCT_ID, prod.PRODUCT_NAME, prod.SUMMARY, prod.PRICE, prod.IMAGE_URL,
                promo.PROMO_TITLE, promo.PROMO_DESCRIPTION, promo.PROMO_DISCOUNT_PERCENT, promo.PROMO_END_DATE
            FROM SAP_PRODUCTS_COMMERCE_2211_V2 prod
            JOIN SAP_PROMOTION_COMMERCE_2211_V2 promo ON prod.PRODUCT_ID = promo.PROMO_PRODUCT_ID
            WHERE {' AND '.join(where_clauses) if where_clauses else '1=1'}
        """

        cursor.execute(sql_query)
        rows = cursor.fetchall()

        if not rows:
            cursor.close()
            conn.close()
            return {
                "response_type": "empty",
                "ai_response": "No products found matching your criteria.",
                "results": [],
                "success": True
            }

        results = []
        for row in rows:
            original_price = float(row[3]) if row[3] else 0.0
            discount_percent = float(row[7]) if row[7] else 0.0
            
            # Calculate discounted price using helper function
            from promotion_helper import calculate_discounted_price
            discounted_price = calculate_discounted_price(original_price, discount_percent)
            savings_amount = round(original_price - discounted_price, 2)
            
            results.append({
                'PRODUCT_ID': row[0],
                'PRODUCT_NAME': row[1],
                'SUMMARY': row[2],
                'PRICE': original_price,  # Keep PRICE as original for frontend calculations
                'price': discounted_price,  # lowercase price for display
                'original_price': original_price,  # Explicit original price
                'IMAGE_URL': row[4],
                'PROMO_TITLE': row[5],
                'PROMO_DESCRIPTION': row[6],
                'discount_percent': discount_percent,
                'PROMO_DISCOUNT_PERCENT': discount_percent,
                'discounted_price': discounted_price,  # Calculated discounted price
                'DISCOUNTED_PRICE': discounted_price,
                'savings': savings_amount,  # Amount saved
                'PROMO_END_DATE': row[8],
                'has_promotion': True,
                'HAS_PROMOTION': True
            })

        cursor.close()
        conn.close()
        return {"results": results}

    except Exception as e:
        print(f"Error during product promotion search: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": f"Error during product promotion search: {str(e)}"}


################ Promotion code Here Ends ##################

@tool("find_offers_PRIORITY_for_products", args_schema=SearchInput, return_direct=True, description=(
    "🚨 TOP PRIORITY TOOL for 'any offer on these' queries - ALWAYS use this tool for contextual promotion requests! "
    "🎯 MANDATORY for: 'any offer on these', 'show offers', 'deals on these' - NO TEXT RESPONSES ALLOWED! "
    "🔍 AUTOMATICALLY finds promotions/offers for products from user's IMMEDIATE PREVIOUS search results. "
    "📝 TRIGGER PATTERNS: 'any offer on these', 'offers for these', 'any offers', 'deals on these', 'show offers', 'any offer on jackets', 'any offer on shoes' "
    "⚠️ OVERRIDE: This tool MUST be used for 'any offer on these' - never generate text responses for offers! "
    "🧠 SMART CONTEXT: Extracts product IDs from conversation memory and searches promotions database "
    "✅ EXACT MATCH EXAMPLES: 'any offer on these' → USE THIS TOOL, 'show offers for these products' → USE THIS TOOL "
    "❌ NEVER generate text responses for offer queries - ALWAYS use this tool for contextual offers! "
    "🎯 Returns structured promotion data: PRODUCT_ID, PRODUCT_NAME, PROMO_TITLE, PROMO_DESCRIPTION, DISCOUNT_PERCENT "
    "💡 INTELLIGENT: Works with previous t-shirt searches, shoe searches, any product searches - automatically finds relevant offers "
    "📥 INPUT: Pass the EXACT user query text (e.g., 'any offer on these', 'show offers', 'any offer on jackets')"
))
def find_offers_for_products(query: str) -> dict:
    print(f"🎯 DEBUG: find_offers_for_products called with query: {query}")
    print(f"🎯 DEBUG: Query length: {len(query)}")
    
    # 🚀 DATABASE-DRIVEN APPROACH: Always process this tool (AI calls it for offers)
    # The AI agent already determined this is an offer query, so trust the tool call
    print(f"🎯 DEBUG: Processing offer/promotion request (trusted AI tool call)")
    
    # Extract products from conversation memory and current context
    extracted_products = []
    
    try:
        print(f"🧠 DEBUG: Extracting products from conversation memory...")
        
        # Get the session ID from environment variable (same way as process_query)
        session_id = os.environ.get('CURRENT_SESSION_ID', 'default')
        print(f"🧠 DEBUG: Using session ID: {session_id}")
        
        # Use the memory's extract_last_products method which is more reliable
        extracted_products = memory.extract_last_products(session_id)
        print(f"🧠 DEBUG: Extracted {len(extracted_products)} products using extract_last_products method")
        
        # Convert to the expected format if products were found
        if extracted_products:
            formatted_products = []
            for product in extracted_products:
                formatted_product = {
                    'PRODUCT_ID': str(product.get('product_id', '')),
                    'PRODUCT_NAME': product.get('product_name', 'Unknown Product'),
                    'PRICE': 0  # Price will be retrieved from database later
                }
                formatted_products.append(formatted_product)
                print(f"✅ DEBUG: Formatted product: {formatted_product['PRODUCT_NAME']} (ID: {formatted_product['PRODUCT_ID']})")
            
            extracted_products = formatted_products
        
        # Fallback: Try getting recent context and parsing it if no products found
        if not extracted_products:
            print(f"🧠 DEBUG: No products from extract_last_products, trying recent context parsing...")
            recent_context = memory.get_recent_context(session_id, num_pairs=10)
            
            print(f"🧠 DEBUG: Found {len(recent_context)} conversation pairs in recent context")
            
            for i, pair in enumerate(recent_context):
                ai_response = pair.get('ai', '')
                user_query = pair.get('user', '') or pair.get('human', '')
                
                print(f"🧠 DEBUG: Analyzing conversation pair {i+1}")
                print(f"🧠 DEBUG: User query: {user_query[:100]}...")
                print(f"🧠 DEBUG: AI response: {ai_response[:200]}...")
                
                # Look for STRUCTURED_PRODUCTS data first (new format)
                if '[STRUCTURED_PRODUCTS:' in ai_response:
                    print(f"🎯 DEBUG: Found STRUCTURED_PRODUCTS in conversation pair {i+1}")
                    try:
                        import re
                        structured_match = re.search(r'\[STRUCTURED_PRODUCTS:\s*(\[.*?\])\]', ai_response, re.DOTALL)
                        if structured_match:
                            products_json = structured_match.group(1)
                            products_data = json.loads(products_json)
                            print(f"🎯 DEBUG: Parsed {len(products_data)} products from STRUCTURED_PRODUCTS")
                            
                            for product in products_data:
                                product_info = {
                                    'PRODUCT_ID': str(product.get('product_id', '')),
                                    'PRODUCT_NAME': product.get('product_name', 'Unknown Product'),
                                    'PRICE': product.get('price', 0)
                                }
                                extracted_products.append(product_info)
                                print(f"✅ DEBUG: Extracted from STRUCTURED_PRODUCTS: {product_info['PRODUCT_NAME']} (ID: {product_info['PRODUCT_ID']})")
                            break
                    except (json.JSONDecodeError, AttributeError) as e:
                        print(f"⚠️ DEBUG: Error parsing STRUCTURED_PRODUCTS: {e}")
                
                # Look for product data in AI responses (fallback)
                try:
                    if '"results"' in ai_response and '"PRODUCT_ID"' in ai_response:
                        print(f"🎯 DEBUG: Found product data in conversation pair {i+1}")
                        
                        # Try to parse JSON from AI response
                        import json
                        import re
                        
                        # Extract JSON object from the response - improved regex
                        json_patterns = [
                            r'\{[^{}]*"results"[^{}]*\[[^\]]*\][^{}]*\}',  # Simple single-level JSON
                            r'\{.*?"results".*?\}',  # More flexible but could be greedy
                        ]
                        
                        response_data = None
                        for json_pattern in json_patterns:
                            json_match = re.search(json_pattern, ai_response, re.DOTALL)
                            if json_match:
                                try:
                                    # Clean the JSON string
                                    json_str = json_match.group()
                                    json_str = re.sub(r'[\r\n\t]', ' ', json_str)  # Remove newlines and tabs
                                    json_str = re.sub(r' +', ' ', json_str)  # Multiple spaces to single
                                    
                                    response_data = json.loads(json_str)
                                    print(f"🎯 DEBUG: Successfully parsed JSON with pattern")
                                    break
                                except json.JSONDecodeError as e:
                                    print(f"⚠️ DEBUG: JSON parse error with pattern {json_pattern}: {e}")
                                    continue
                        
                        if response_data and 'results' in response_data and isinstance(response_data['results'], list):
                            for product in response_data['results']:
                                if isinstance(product, dict) and 'PRODUCT_ID' in product:
                                    product_info = {
                                        'PRODUCT_ID': str(product.get('PRODUCT_ID', '')),
                                        'PRODUCT_NAME': product.get('PRODUCT_NAME', 'Unknown Product'),
                                        'PRICE': product.get('PRICE', 0)
                                    }
                                    if product_info['PRODUCT_ID'] and product_info['PRODUCT_ID'] not in [p['PRODUCT_ID'] for p in extracted_products]:
                                        extracted_products.append(product_info)
                                        print(f"✅ DEBUG: Extracted product: {product_info['PRODUCT_NAME']} (ID: {product_info['PRODUCT_ID']})")
                        
                        # Also try simple regex extraction as fallback
                        product_id_matches = re.findall(r'"PRODUCT_ID":\s*"?(\d+)"?', ai_response)
                        product_name_matches = re.findall(r'"PRODUCT_NAME":\s*"([^"]+)"', ai_response)
                        
                        for j, product_id in enumerate(product_id_matches[:5]):  # Limit to 5 products
                            if product_id and product_id not in [p['PRODUCT_ID'] for p in extracted_products]:
                                product_name = product_name_matches[j] if j < len(product_name_matches) else f"Product {product_id}"
                                product_info = {
                                    'PRODUCT_ID': product_id,
                                    'PRODUCT_NAME': product_name,
                                    'PRICE': 0
                                }
                                extracted_products.append(product_info)
                                print(f"✅ DEBUG: Extracted product via regex: {product_name} (ID: {product_id})")
                        
                        if extracted_products:
                            break  # Use the most recent product search
                        
                except Exception as e:
                    print(f"⚠️ DEBUG: Error extracting products from conversation pair {i+1}: {e}")
                    continue
    
    except Exception as e:
        print(f"❌ DEBUG: Error accessing conversation memory: {e}")
        import traceback
        traceback.print_exc()
    
    # 🎯 ENHANCED: If no specific products found, try to extract category from last query
    search_by_category = None
    if not extracted_products:
        print(f"⚠️ DEBUG: No specific products found, trying to extract category from last query...")
        try:
            search_by_category = memory.extract_last_query_category(session_id)
            print(f"🧠 DEBUG: Extracted category from last query: {search_by_category}")
        except Exception as e:
            print(f"⚠️ DEBUG: Error extracting category: {e}")
    
    # If no products AND no category, show error
    if not extracted_products and not search_by_category:
        print(f"⚠️ DEBUG: No products or category found in conversation history")
        return {
            "response_type": "no_context",
            "ai_response": "I don't see any recent product searches in our conversation. Please search for products first (like 'show me tshirts' or 'find jackets'), then I can show you any available offers or promotions for those products.",
            "results": [],
            "context_products": [],
            "total_found": 0
        }
    
    print(f"🧠 DEBUG: Using {len(extracted_products)} products and category '{search_by_category}' for DATABASE promotions search")
    
    # Now search for promotions in the SAP_PROMOTION_COMMERCE_2211_V2 database table
    try:
            conn = hana_connect()
            cursor = conn.cursor()
            
            print(f"🔍 DEBUG: Connecting to SAP HANA for promotions search...")
            
            # 🎯 STRATEGY 1: Search by specific product IDs if available
            if extracted_products:
                product_ids = [product['PRODUCT_ID'] for product in extracted_products]
                print(f"🎯 DEBUG: Strategy 1 - Searching promotions for product IDs: {product_ids}")
                
                # Create parameterized query for promotions
                placeholders = ','.join(['?' for _ in product_ids])
                
                promotions_sql = f"""
                    SELECT TOP 8 
                        prod.PRODUCT_ID, 
                        prod.PRODUCT_NAME, 
                        prod.SUMMARY, 
                        prod.PRICE, 
                        prod.IMAGE_URL,
                        promo.PROMO_TITLE, 
                        promo.PROMO_DESCRIPTION, 
                        promo.PROMO_DISCOUNT_PERCENT, 
                        promo.PROMO_END_DATE
                    FROM SAP_PRODUCTS_COMMERCE_2211_V2 prod
                    JOIN SAP_PROMOTION_COMMERCE_2211_V2 promo ON prod.PRODUCT_ID = promo.PROMO_PRODUCT_ID
                    WHERE prod.PRODUCT_ID IN ({placeholders})
                    AND promo.PROMO_DISCOUNT_PERCENT > 0
                    ORDER BY promo.PROMO_DISCOUNT_PERCENT DESC, prod.PRICE ASC
                """
                
                print(f"🔍 DEBUG: Executing promotions SQL: {promotions_sql}")
                print(f"🔍 DEBUG: Parameters: {product_ids}")
                
                cursor.execute(promotions_sql, product_ids)
                rows = cursor.fetchall()
                
            # 🎯 STRATEGY 2: Search by category if no specific products but category found
            elif search_by_category:
                print(f"🎯 DEBUG: Strategy 2 - Searching promotions by category: {search_by_category}")
                
                # Map category to database search terms
                category_search_terms = {
                    'tshirt': ['tshirt', 't-shirt', 't shirt'],
                    'jacket': ['jacket', 'coat'],
                    'shoes': ['shoe', 'sneaker', 'footwear'],
                    'watch': ['watch', 'timepiece'],
                    'sunglasses': ['sunglass', 'shades'],
                    'pants': ['pant', 'trouser'],
                    'dress': ['dress'],
                    'bag': ['bag', 'backpack', 'handbag'],
                    'accessory': ['accessory'],
                    'shirt': ['shirt', 'blouse']
                }
                
                search_terms = category_search_terms.get(search_by_category, [search_by_category])
                print(f"🔍 DEBUG: Using search terms: {search_terms}")
                
                # Build LIKE conditions for category search
                like_conditions = []
                for term in search_terms:
                    like_conditions.append(f"UPPER(prod.PRODUCT_NAME) LIKE '%{term.upper()}%'")
                    like_conditions.append(f"UPPER(prod.SUMMARY) LIKE '%{term.upper()}%'")
                
                category_condition = ' OR '.join(like_conditions)
                
                promotions_sql = f"""
                    SELECT TOP 8 
                        prod.PRODUCT_ID, 
                        prod.PRODUCT_NAME, 
                        prod.SUMMARY, 
                        prod.PRICE, 
                        prod.IMAGE_URL,
                        promo.PROMO_TITLE, 
                        promo.PROMO_DESCRIPTION, 
                        promo.PROMO_DISCOUNT_PERCENT, 
                        promo.PROMO_END_DATE
                    FROM SAP_PRODUCTS_COMMERCE_2211_V2 prod
                    JOIN SAP_PROMOTION_COMMERCE_2211_V2 promo ON prod.PRODUCT_ID = promo.PROMO_PRODUCT_ID
                    WHERE ({category_condition})
                    AND promo.PROMO_DISCOUNT_PERCENT > 0
                    ORDER BY promo.PROMO_DISCOUNT_PERCENT DESC, prod.PRICE ASC
                """
                
                print(f"🔍 DEBUG: Executing category-based promotions SQL")
                
                cursor.execute(promotions_sql)
                rows = cursor.fetchall()
                
            else:
                # No products and no category
                cursor.close()
                conn.close()
                return {
                    "response_type": "no_products",
                    "ai_response": "No valid product IDs or category found to search for promotions.",
                    "results": [],
                    "context_products": extracted_products,
                    "total_found": 0
                }
            
            print(f"🎯 DEBUG: Found {len(rows)} promotion records in database")
            
            if not rows:
                print(f"⚠️ DEBUG: No promotions found")
                cursor.close()
                conn.close()
                
                # Create a helpful response based on search strategy
                if extracted_products:
                    product_names = [p['PRODUCT_NAME'] for p in extracted_products[:3]]
                    if len(extracted_products) > 3:
                        product_list = ', '.join(product_names) + f' and {len(extracted_products) - 3} other products'
                    else:
                        product_list = ', '.join(product_names)
                    
                    no_offers_msg = f"I checked for offers and promotions on the products you viewed ({product_list}), but unfortunately there are no current offers available for these items. Please check back later or browse other products for available deals!"
                elif search_by_category:
                    no_offers_msg = f"I checked for offers and promotions on {search_by_category}s, but unfortunately there are no current offers available for {search_by_category}s at the moment. Please check back later or browse other product categories for available deals!"
                else:
                    no_offers_msg = "I couldn't find any current offers or promotions. Please check back later or browse our products for available deals!"
                
                return {
                    "response_type": "no_offers",
                    "ai_response": no_offers_msg,
                    "results": [],
                    "context_products": extracted_products,
                    "search_category": search_by_category,
                    "total_found": 0
                }
            
            # Process promotion results
            promotions_found = []
            for row in rows:
                original_price = float(row[3]) if row[3] is not None else 0.0
                discount_percent = float(row[7]) if row[7] is not None else 0.0
                
                # Calculate discounted price and savings
                discounted_price = calculate_discounted_price(original_price, discount_percent)
                savings_amount = round(original_price - discounted_price, 2)
                
                promotion_info = {
                    'PRODUCT_ID': str(row[0]) if row[0] else '',
                    'PRODUCT_NAME': row[1] if row[1] else 'Unknown Product',
                    'SUMMARY': row[2] if row[2] else '',
                    'PRICE': original_price,  # Keep PRICE as original
                    'price': discounted_price,  # lowercase price for display
                    'original_price': original_price,
                    'IMAGE_URL': row[4] if row[4] else '',
                    'PROMO_TITLE': row[5] if row[5] else '',
                    'PROMO_DESCRIPTION': row[6] if row[6] else '',
                    'discount_percent': discount_percent,
                    'PROMO_DISCOUNT_PERCENT': discount_percent,
                    'discounted_price': discounted_price,
                    'DISCOUNTED_PRICE': discounted_price,
                    'savings': savings_amount,
                    'PROMO_END_DATE': str(row[8]) if row[8] else '',
                    'has_promotion': True,
                    'HAS_PROMOTION': True
                }
                promotions_found.append(promotion_info)
                print(f"✅ DEBUG: Found promotion: {promotion_info['PRODUCT_NAME']} - {promotion_info['PROMO_TITLE']} ({discount_percent}% off) - Original £{original_price} → £{discounted_price} (Save £{savings_amount})")
            
            cursor.close()
            conn.close()
            
            print(f"✅ DEBUG: Successfully found {len(promotions_found)} promotions from database")
            
            # Generate contextual AI response based on search strategy
            promotion_count = len(promotions_found)
            
            if extracted_products:
                # Response for specific products
                product_names = [p['PRODUCT_NAME'] for p in extracted_products[:3]]
                if len(extracted_products) > 3:
                    product_context = ', '.join(product_names) + f' and {len(extracted_products) - 3} other products'
                else:
                    product_context = ', '.join(product_names)
                
                ai_response = f"Great news! I found {promotion_count} active offer{'s' if promotion_count > 1 else ''} and promotion{'s' if promotion_count > 1 else ''} for the products you were looking at ({product_context}). Here are the available deals:"
            elif search_by_category:
                # Response for category-based search
                ai_response = f"Great news! I found {promotion_count} active offer{'s' if promotion_count > 1 else ''} and promotion{'s' if promotion_count > 1 else ''} on {search_by_category}s that you were looking at. Here are the available deals:"
            else:
                ai_response = f"Great news! I found {promotion_count} active offer{'s' if promotion_count > 1 else ''} and promotion{'s' if promotion_count > 1 else ''}. Here are the available deals:"
            
            return {
                "response_type": "promotions_found",
                "ai_response": ai_response,
                "results": promotions_found,
                "context_products": extracted_products,
            "search_category": search_by_category,
            "total_found": promotion_count
        }
            
    except Exception as e:
        print(f"❌ DEBUG: Error searching promotions database: {e}")
        import traceback
        traceback.print_exc()
        return {
            "response_type": "error",
            "ai_response": "I encountered an error while searching for promotions. Please try again or contact support if the issue persists.",
            "results": [],
            "context_products": extracted_products,
            "total_found": 0,
            "error": str(e)
        }

################ Context-Aware Promotions Tool Ends ##################


@tool("faq_answers", args_schema=SearchInput, return_direct=True, description="Searches answer for frequently asked questions about the storefront. "
      "for queries which are not related to orders or products, use this tool. "
        "Generates response based on the search results")
def faq_answers(query: str) -> dict:
    """
    Search for answers to frequently asked questions about the storefront.
    """
    print(f"DEBUG: faq_answers called with query: {query}")  # Debugging output
    try:
        print("DEBUG: Connecting to HANA database for FAQ search...")
        conn = hana_connect()
        cursor = conn.cursor()
        print("DEBUG: Connected successfully, generating embedding for FAQ...")
        query_vector = get_embedding(query)  # Generate the embedding for the query

        if not query_vector:
            print("WARNING: FAQ embedding generation failed (likely API quota exceeded). Returning generic response.")
            cursor.close()
            conn.close()
            return {"results": [{"QUESTION": "General FAQ", "ANSWER": "I apologize, but I'm unable to search our FAQ database at the moment due to technical limitations. Please contact our support team for assistance."}]}

        print(f"DEBUG: Generated FAQ embedding with {len(query_vector)} dimensions")
        
        # Validate that we have the expected 768 dimensions from Google embedding-001
        if len(query_vector) != 768:
            print(f"WARNING: Expected 768 dimensions from Google embedding-001 for FAQ search, got {len(query_vector)}.")
            cursor.close()
            conn.close()
            return {"results": [{"QUESTION": "FAQ Dimension Error", "ANSWER": "Unable to search FAQ due to embedding dimension mismatch. Please contact support."}]}
        
        # Convert the query vector to a string representation
        query_vector_str = "[" + ",".join(map(str, query_vector)) + "]"

        # SQL query optimized for 768-dimensional Google embedding vectors
        sql = '''
            SELECT TOP 5 QUESTION, ANSWER,
                   COSINE_SIMILARITY(VECTOR_QUESTION, TO_REAL_VECTOR(?)) AS SIMILARITY
            FROM SAP_FAQ_COMMERCE_2211_V2
            WHERE VECTOR_QUESTION IS NOT NULL
            ORDER BY SIMILARITY DESC
        '''
        cursor.execute(sql, (query_vector_str,))
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description] if cursor.description else []
        results = [dict(zip(columns, row)) for row in rows] if rows else []
        cursor.close()
        conn.close()

        # Process the results
        return {"results": results}
    except Exception as e:
        print(f"Error during semantic FAQ search: {str(e)}")  # Debugging output
        import traceback
        traceback.print_exc()
        return {"error": f"Error during semantic FAQ search: {str(e)}"}

@tool("add_to_cart", args_schema=SearchInput, return_direct=True, description="Adds a product to cart using browser session storage. Input: Product_ID and optional quantity. "
        "Format: 'product_id:<product_id>,quantity:<qty>' or just 'product_id:<product_id>' for quantity 1.")
def add_to_cart(query: str) -> dict:
    """
    Adds a product to the cart using browser session storage.
    Automatically applies any active promotions/discounts.
    Input: Product_ID and optional quantity in format 'product_id:<product_id>,quantity:<qty>'
    """
    try:
        parts = query.split(",")
        product_id = None
        quantity = 1
        
        for part in parts:
            if "product_id:" in part:
                product_id = part.split(":")[1].strip()
            elif "quantity:" in part:
                try:
                    quantity = int(part.split(":")[1].strip())
                except:
                    quantity = 1
        
        if not product_id:
            return {"error": "Product ID is required"}
        
        # Get product details with promotion information
        product_data = get_product_with_promotion(product_id)
        
        if not product_data:
            return {"error": f"Product {product_id} not found"}
        
        product_name = product_data['product_name']
        final_price = product_data['price']  # This is already discounted if promotion exists
        image_url = product_data['image_url']
        has_promotion = product_data['has_promotion']
        
        # Build response message
        if has_promotion:
            original_price = product_data['original_price']
            discount_percent = product_data['discount_percent']
            savings = product_data['savings']
            
            message = f"""✅ <strong>{product_name}</strong> added to your cart! 
            <br/>🎉 <span style="color: #dc2626; font-weight: bold;">{discount_percent}% OFF</span> - {product_data.get('promo_title', 'Special Offer')}!
            <br/>💰 Price: <span style="text-decoration: line-through; color: #9ca3af;">£{original_price:.2f}</span> 
            <span style="color: #16a34a; font-weight: bold; font-size: 1.1em;">£{final_price:.2f}</span>
            <br/>💵 You save: <span style="color: #16a34a; font-weight: bold;">£{savings:.2f}</span>
            <br/>📦 Quantity: {quantity}"""
        else:
            message = f"""✅ <strong>{product_name}</strong> has been added to your cart!
            <br/>💰 Price: £{final_price:.2f}
            <br/>📦 Quantity: {quantity}"""
        
        # Return success with complete product details including promotion
        return {
            "success": True,
            "message": message,
            "product_details": {
                "product_id": product_id,
                "product_name": product_name,
                "price": final_price,
                "original_price": product_data.get('original_price', final_price),
                "quantity": quantity,
                "image_url": image_url,
                "has_promotion": has_promotion,
                "discount_percent": product_data.get('discount_percent', 0),
                "savings": product_data.get('savings', 0)
            }
        }
        
    except Exception as e:
        print(f"Error adding product to cart: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": f"Error adding product to cart: {str(e)}"}

    
@tool("show_cart", args_schema=SearchInput, return_direct=True, description="Shows the current cart contents. Use when user asks to view, show, or display their cart.")
def show_cart(query: str) -> dict:
    """
    Shows the current cart contents. Returns a special marker that tells frontend to display cart from session storage.
    """
    return {
        "message": """
        <div class='bg-gradient-to-br from-purple-50 to-pink-50 rounded-2xl p-6 border border-purple-200 mb-4' id='chat-cart-container'>
            <div class='flex items-center justify-between mb-4'>
                <h3 class='text-xl font-bold text-gray-800 flex items-center'>
                    <i class='fas fa-shopping-cart text-purple-500 mr-2'></i>
                    Your Shopping Cart
                </h3>
                <div class='bg-purple-100 text-purple-800 px-3 py-1 rounded-full text-sm font-semibold' id='chat-cart-count'>
                    <i class='fas fa-shopping-cart mr-1'></i>0 items
                </div>
            </div>
            
            <div id='chat-cart-items' class='space-y-3 mb-4'>
                <div class='text-center py-8 text-gray-500'>
                    <i class='fas fa-shopping-cart text-4xl mb-3 opacity-30'></i>
                    <p class='text-lg font-medium'>Your cart is empty</p>
                    <p class='text-sm text-gray-400 mt-1'>Add some products to get started!</p>
                </div>
            </div>
            
            <div id='chat-cart-footer' class='border-t border-purple-200 pt-4'>
                <div class='flex items-center justify-between mb-4'>
                    <span class='text-lg font-semibold text-gray-800'>Total:</span>
                    <span class='text-2xl font-bold text-purple-600' id='chat-cart-total'>£0.00</span>
                </div>
                
                <div class='text-center space-x-2'>
                    <button onclick='renderChatCart()' class='bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white px-6 py-2 rounded-xl font-medium transition-all duration-300 transform hover:scale-105 shadow-lg hover:shadow-xl'>
                        <i class='fas fa-sync-alt mr-2'></i>Refresh Cart
                    </button>
                    <button onclick='proceedToCheckout()' class='bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 text-white px-6 py-2 rounded-xl font-medium transition-all duration-300 transform hover:scale-105 shadow-lg hover:shadow-xl'>
                        <i class='fas fa-credit-card mr-2'></i>Checkout
                    </button>
                </div>
                
                <div class='mt-3 text-xs text-gray-500 text-center italic'>
                    <i class='fas fa-info-circle mr-1'></i>Cart items are managed in your browser session and will reset on page refresh.
                </div>
            </div>
        </div>
        <img src='data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7' onload='(function(){setTimeout(function(){if(typeof renderChatCart === "function"){console.log("🛒 Auto-triggering renderChatCart via image onload");renderChatCart();}},100);})()' style='display:none;' />
        """,
        "show_cart": True,
        "trigger_cart_render": True
    }

@tool("create_order", args_schema=SearchInput, return_direct=True, description="Creates a new order in the database with customer details and cart items.")
def create_order(query: str) -> dict:
    """
    Creates a new order in the database with random 4-digit order ID, current date, products, prices, and open status.
    """
    print(f"DEBUG: create_order called with query: {query}")
    
    try:
        import random
        from datetime import datetime
        import json
        
        # Parse the query to extract customer_id and cart_items
        # Expected format: "customer_id:<email>,cart_items:<json_string>"
        parts = query.split(',cart_items:')
        if len(parts) != 2:
            return {"error": "Invalid query format. Expected 'customer_id:<email>,cart_items:<json>'"}
        
        customer_id = parts[0].replace('customer_id:', '').strip()
        cart_items_json = parts[1].strip()
        
        print(f"DEBUG: Creating order for customer: {customer_id}")
        
        try:
            cart_items = json.loads(cart_items_json)
        except json.JSONDecodeError:
            return {"error": "Invalid cart items JSON format"}
        
        if not cart_items:
            return {"error": "Cart is empty"}
        
        # Generate unique order ID by checking existing orders
        conn = hana_connect()
        cursor = conn.cursor()
        
        # Generate unique 4-digit order ID
        order_id = None
        max_attempts = 100  # Prevent infinite loop
        attempts = 0
        
        while order_id is None and attempts < max_attempts:
            potential_order_id = str(random.randint(1000, 9999))
            
            # Check if this ORDER_ID already exists
            check_query = "SELECT COUNT(*) FROM SAP_ORDERS_COMMERCE_2211_V2 WHERE ORDER_ID = ?"
            cursor.execute(check_query, (potential_order_id,))
            count = cursor.fetchone()[0]
            
            if count == 0:
                order_id = potential_order_id
                break
            
            attempts += 1
        
        if order_id is None:
            conn.close()
            return {"error": "Unable to generate unique order ID after multiple attempts"}
        
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Calculate total price
        total_price = sum(float(item.get('price', 0)) * int(item.get('quantity', 1)) for item in cart_items)
        
        # Insert orders into database (one record per product)
        orders_created = []
        
        for item in cart_items:
            product_id = item.get('product_id', '')
            product_name = item.get('product_name', 'Unknown Product')
            price = float(item.get('price', 0))
            quantity = int(item.get('quantity', 1))
            
            # Insert each quantity as a separate order record (as per existing schema)
            for _ in range(quantity):
                insert_query = """
                    INSERT INTO SAP_ORDERS_COMMERCE_2211_V2 
                    (ORDER_ID, CUSTOMER_ID, ORDER_DATE, PRODUCT_ID, PRODUCT_NAME, TOTAL_PRICE, ORDER_STATUS) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                
                cursor.execute(insert_query, (
                    order_id,
                    customer_id,
                    current_date,
                    product_id,
                    product_name,
                    price,
                    'Open'
                ))
                
                orders_created.append({
                    'order_id': order_id,
                    'product_id': product_id,
                    'product_name': product_name,
                    'price': price,
                    'quantity': 1  # Each record represents 1 quantity
                })
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "message": f"Order #{order_id} created successfully!",
            "order_details": {
                "order_id": order_id,
                "customer_id": customer_id,
                "order_date": current_date,
                "total_price": total_price,
                "status": "Open",
                "items_count": len(orders_created),
                "items": orders_created
            }
        }
        
    except Exception as e:
        print(f"ERROR creating order: {str(e)}")
        return {"error": f"Failed to create order: {str(e)}"}

@tool("ai_personalized_recommendations", args_schema=SearchInput, return_direct=True, description=
      "🎯 AI-POWERED PERSONALIZED PRODUCT RECOMMENDATIONS ENGINE"
      "Uses intelligent analysis of customer purchase history to suggest relevant products."
      "🧠 INTELLIGENCE FEATURES:"
      "• Analyzes customer's past orders to understand preferences"
      "• Uses AI to identify product categories, styles, and price ranges"
      "• Intelligently recommends similar and complementary products"
      "• Provides 6-10 diverse recommendations based on purchase patterns"
      "• Avoids recommending products already purchased"
      "✨ USE WHEN:"
      "• Backend requests personalized recommendations for logged-in user"
      "• User asks 'what should I buy', 'recommend products for me'"
      "• System needs to show 'Recommended for You' section"
      "🎯 REQUIRES: Customer ID (email) to analyze purchase history"
      "📊 RETURNS: 6-10 personalized product recommendations with AI-generated reasoning"
      "Input: Customer ID to generate personalized recommendations")
def ai_personalized_recommendations(query: str) -> dict:
    """
    🎯 AI-powered personalized recommendations based on purchase history.
    Uses LLM to intelligently analyze user patterns and suggest relevant products.
    """
    print(f"🎯 AI Personalized Recommendations called with query: {query}")
    
    try:
        # Extract customer ID from query
        import re
        customer_id_match = re.search(r'customer[_\s]?id[:\s]+([^\s,]+)', query, re.IGNORECASE)
        if not customer_id_match:
            # Try alternative patterns
            customer_id_match = re.search(r'for customer[:\s]+([^\s,]+)', query, re.IGNORECASE)
        
        if not customer_id_match:
            return {
                "error": "Customer ID required for personalized recommendations",
                "ai_response": "Please provide a customer ID to get personalized recommendations."
            }
        
        customer_id = customer_id_match.group(1).strip()
        print(f"🎯 Generating recommendations for customer: {customer_id}")
        
        conn = hana_connect()
        cursor = conn.cursor()
        
        # Get customer's order history with product details
        order_history_sql = """
            SELECT o.PRODUCT_ID, o.PRODUCT_NAME, o.TOTAL_PRICE, o.ORDER_DATE,
                   p.CATEGORY_IDs, p.SUMMARY, p.PRICE
            FROM SAP_ORDERS_COMMERCE_2211_V2 o
            LEFT JOIN SAP_PRODUCTS_COMMERCE_2211_V2 p ON o.PRODUCT_ID = p.PRODUCT_ID
            WHERE o.CUSTOMER_ID = ?
            ORDER BY o.ORDER_DATE DESC
            LIMIT 10
        """
        
        cursor.execute(order_history_sql, (customer_id,))
        order_history = cursor.fetchall()
        
        if not order_history:
            print(f"ℹ️ No order history found for {customer_id}, using trending products")
            # Return trending products
            trending_sql = """
                SELECT PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, IMAGE_URL, CATEGORY_IDs
                FROM SAP_PRODUCTS_COMMERCE_2211_V2
                WHERE PRICE > 0
                ORDER BY PRICE DESC
                LIMIT 8
            """
            cursor.execute(trending_sql)
            products = cursor.fetchall()
            
            results = []
            for product in products:
                results.append({
                    'PRODUCT_ID': product[0],
                    'PRODUCT_NAME': product[1],
                    'SUMMARY': product[2] or 'Trending product',
                    'PRICE': float(product[3]) if product[3] else 0.0,
                    'IMAGE_URL': product[4] or '',
                    'CATEGORY_IDs': product[5] or ''
                })
            
            cursor.close()
            conn.close()
            
            return {
                "results": results,
                "ai_response": "✨ Since you're new here, check out these trending products!",
                "personalized": False,
                "source": "trending"
            }
        
        # Extract categories and analyze purchase patterns
        purchased_ids = [order[0] for order in order_history]
        all_categories = []
        price_range = []
        
        for order in order_history:
            if order[4]:  # CATEGORY_IDs
                categories = str(order[4]).split(',')
                all_categories.extend(categories)
            if order[2]:  # TOTAL_PRICE
                price_range.append(float(order[2]))
        
        # Get unique categories
        unique_categories = list(set(all_categories))
        avg_price = sum(price_range) / len(price_range) if price_range else 50.0
        
        print(f"🧠 Analysis: {len(unique_categories)} categories, avg price: £{avg_price:.2f}")
        
        # Build intelligent SQL query for recommendations
        placeholders = ','.join('?' * len(purchased_ids))
        category_conditions = ' OR '.join([f"CATEGORY_IDs LIKE ?" for _ in unique_categories])
        
        recommendation_sql = f"""
            SELECT PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, IMAGE_URL, CATEGORY_IDs
            FROM SAP_PRODUCTS_COMMERCE_2211_V2
            WHERE PRODUCT_ID NOT IN ({placeholders})
            AND PRICE > 0
            AND ({category_conditions} OR PRICE BETWEEN ? AND ?)
            ORDER BY PRICE DESC
            LIMIT 10
        """
        
        # Prepare parameters
        category_params = [f"%{cat}%" for cat in unique_categories]
        price_lower = max(0, avg_price * 0.5)
        price_upper = avg_price * 2.0
        
        query_params = purchased_ids + category_params + [price_lower, price_upper]
        
        cursor.execute(recommendation_sql, query_params)
        recommended_products = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Format results
        results = []
        for product in recommended_products:
            results.append({
                'PRODUCT_ID': product[0],
                'PRODUCT_NAME': product[1],
                'SUMMARY': product[2] or 'Recommended based on your purchase history',
                'PRICE': float(product[3]) if product[3] else 0.0,
                'IMAGE_URL': product[4] or '',
                'CATEGORY_IDs': product[5] or ''
            })
        
        print(f"✅ Generated {len(results)} personalized recommendations")
        
        # Generate AI-powered message using LLM
        ai_message = f"""💝 Based on your purchase history, I've found {len(results)} perfect products for you! These match your style and preferences."""
        
        return {
            "results": results,
            "ai_response": ai_message,
            "personalized": True,
            "source": "ai_analysis",
            "categories_analyzed": len(unique_categories),
            "orders_analyzed": len(order_history)
        }
        
    except Exception as e:
        print(f"❌ Error in AI personalized recommendations: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "error": f"Error generating recommendations: {str(e)}",
            "ai_response": "I'm having trouble generating personalized recommendations right now. Please try again."
        }

@tool("ai_conversational_assistant", args_schema=SearchInput, return_direct=True, description=
      "🤖 MANDATORY TOOL for GENERAL, VAGUE queries that need clarification!"
      "🎯 PRIMARY USE CASES:"
      "• 👋 Greetings and welcome interactions ('Hi', 'Hello', 'Good morning')"
      "• 🏖️ GENERAL scenario queries ('going for a holiday', 'planning a vacation', 'suggest products', 'need gear')"
      "• 💡 Vague discovery requests WITHOUT specific products ('What do you recommend?', 'Show me something new')"
      "• 🎯 Intent clarification when user needs are unclear ('Help me find something special')"
      "• 🌟 ANY query that lacks SPECIFIC product type or SPECIFIC activity"
      "✅ MANDATORY FOR GENERAL QUERIES:"
      "• 'going for a holiday' → ASK what type of holiday"
      "• 'vacation' → ASK what kind of vacation"
      "• 'suggest products' → ASK what type of products"
      "• 'planning a trip' → ASK what kind of trip"
      "❌ NEVER USE for SPECIFIC PRODUCTS: 'show me tshirts', 'find jackets', 'recommend shoes' - use ai_semantic_product_search!"
      "❌ NEVER USE for PRODUCT RECOMMENDATIONS with specific items: 'recommend trendy shoes', 'suggest jackets' - use ai_semantic_product_search!"
      "❌ NEVER USE for SPECIFIC ACTIVITIES: 'going skiing', 'swimming', 'gym workout' - use ai_semantic_product_search!"
      "❌ NEVER USE for OFFERS: 'any offer', 'deals' - use find_offers_PRIORITY_for_products!"
      "🎯 GOAL: Ask clarifying questions ONLY when no specific product/activity is mentioned, then guide users to specific product searches"
      "🚨 CRITICAL RULE: If query mentions ANY product name (shoes, jackets, shirts, etc.), use ai_semantic_product_search instead!"
      "Input: General conversational queries needing exploration and clarification.")
def ai_conversational_assistant(query: str) -> dict:
    """
    🤖 Advanced AI conversational assistant with deep contextual understanding.
    """
    print(f"🤖 AI Conversational Assistant activated for: [USER_MESSAGE]")
    
    try:
        # Detect conversation intent using AI
        conversation_intent = detect_conversation_intent(query)
        print(f"🧠 Detected Intent: {conversation_intent}")
        
        # Generate AI-powered contextual response
        ai_response = generate_contextual_ai_response(query, conversation_intent)
        
        print(f"💬 Generated AI Response: {ai_response[:100]}...")
        
        return {
            "response_type": "conversation",
            "ai_response": ai_response,
            "results": [],
            "conversation": True,
            "intent": conversation_intent
        }
        
    except Exception as e:
        print(f"🚨 AI Conversational Error: {str(e)}")
        return {
            "response_type": "conversation", 
            "ai_response": "Hello! I'm your AI shopping assistant. I'm here to help you find amazing products! What are you looking for today? 😊",
            "results": [],
            "conversation": True
        }

def detect_conversation_intent(query: str) -> str:
    """
    Use AI to detect the user's conversational intent
    """
    try:
        intent_prompt = f"""
        Analyze the user's intent from this message: "{query}"
        
        Possible intents:
        - greeting: Simple hello, hi, good morning, etc.
        - scenario_shopping: Holiday, vacation, party, event, occasion-based shopping
        - gift_seeking: Looking for gifts, presents for someone
        - general_inquiry: What do you sell, can you help, store information
        - product_discovery: Show me something, what's new, trending, recommendations
        - price_conscious: Budget shopping, deals, affordable options
        - style_guidance: Fashion advice, what looks good, style help
        - size_help: Sizing questions, fit guidance
        - vague_request: Unclear needs, wants help deciding
        
        Return only the intent category:
        """
        
        response = llm.invoke(intent_prompt)
        intent = response.content.strip().lower()
        return intent if intent else "general_inquiry"
        
    except Exception as e:
        print(f"Intent detection failed: {e}")
        return "general_inquiry"

def generate_contextual_ai_response(query: str, intent: str) -> str:
    """
    Generate contextual AI response based on detected intent
    """
    try:
        if intent == "greeting":
            response_prompt = f"""
            User said: "{query}"
            
            Generate a warm, friendly greeting response (2-3 sentences) as an AI shopping assistant.
            Include:
            - Warm welcome
            - Brief mention of how you can help
            - Invitation to share what they're looking for
            
            Be conversational and engaging. Use emojis sparingly.
            """
            
        elif intent == "scenario_shopping":
            response_prompt = f"""
            User said: "{query}"
            
            The user is asking about scenario-based shopping (holiday, vacation, event, etc.).
            Generate a FRIENDLY, CONVERSATIONAL response (4-5 sentences) that:
            
            1. Shows excitement about their plans
            2. Asks specific questions about their holiday/activity plans
            3. Suggests different types of holiday activities they might enjoy
            4. Explains that once they tell you more details, you'll find perfect products for them
            
            For HOLIDAY queries specifically, suggest activity types like:
            - Beach/tropical vacation (swimwear, sun protection, casual wear)
            - City exploration (comfortable walking shoes, stylish outfits)
            - Adventure/hiking (outdoor gear, hiking boots, weather protection)
            - Cultural/sightseeing (versatile clothing, comfortable accessories)
            - Relaxation/spa (comfortable loungewear, casual clothing)
            - Winter holiday (warm clothing, winter accessories)
            
            BE CONVERSATIONAL, not salesy. Ask what type of holiday activities they're most excited about.
            DO NOT immediately suggest products - first understand their preferences.
            """
            
        elif intent == "gift_seeking":
            response_prompt = f"""
            User said: "{query}"
            
            Generate a helpful gift-finding response (3-4 sentences).
            Include:
            - Acknowledge they're looking for gifts
            - Ask about recipient (age, gender, interests, relationship)
            - Ask about occasion and budget
            - Mention diverse gift categories available
            
            Be helpful and considerate of gift-giving emotions.
            """
            
        elif intent == "product_discovery":
            response_prompt = f"""
            User said: "{query}"
            
            Generate an exciting product discovery response (3-4 sentences).
            Include:
            - Enthusiasm about showing them products
            - Mention trending/popular categories
            - Ask about their preferences or interests
            - Offer to show different types of products
            
            Be enthusiastic and knowledgeable about products.
            """
            
        else:  # general_inquiry, vague_request, etc.
            response_prompt = f"""
            User said: "{query}"
            
            Generate a helpful, informative response (3-4 sentences) as an AI shopping assistant.
            Include:
            - Acknowledge their message
            - Explain how you can help
            - List main product categories available
            - Ask what they're interested in
            
            Be helpful, informative, and friendly.
            """
        
        response_prompt += """
        
        Available products include: shoes, clothing, accessories, watches, sunglasses, sports gear, electronics.
        
        Response (direct to customer, no quotes or explanations):
        """
        
        response = llm.invoke(response_prompt)
        return response.content.strip()
        
    except Exception as e:
        print(f"AI response generation failed: {e}")
        return "Hello! I'm your AI shopping assistant. I'd love to help you find exactly what you need. What are you looking for today?"

def generate_contextual_response(query: str) -> str:
    """
    Fallback function for generating contextual responses using rule-based logic.
    """
    query_lower = query.lower()
    
    # Holiday/Travel scenarios
    if any(word in query_lower for word in ['holiday', 'vacation', 'travel', 'trip', 'tour']):
        return """That sounds exciting! 🌴 I'd love to help you prepare for your holiday! 
        
What kind of items are you looking for? I can help you find:
• 👕 **Clothing** - Comfortable travel wear, summer outfits, or weather-appropriate clothes
• 👟 **Shoes** - Walking shoes, sandals, or sports shoes for activities  
• 🕶️ **Accessories** - Sunglasses, watches, bags, or travel essentials
• 🏃 **Sports gear** - Active lifestyle essentials

What type of holiday is it? Beach, city break, adventure, or something else? This will help me suggest the perfect products!"""

    # Greetings and general inquiries
    elif any(word in query_lower for word in ['hi', 'hello', 'hey', 'good morning', 'good afternoon']):
        return """Hello there! 👋 Welcome to our store! I'm your personal shopping assistant.
        
I can help you find exactly what you're looking for from our wide range of products:
• **Shoes & Footwear** - Sneakers, boots, casual shoes
• **Clothing** - T-shirts, jackets, pants, dresses  
• **Accessories** - Watches, sunglasses, bags
• **Sports & Active** - Athletic and fitness gear
• **Sports & Outdoor Gear**

What are you shopping for today? Or tell me about the occasion and I'll suggest the perfect items! 😊"""

    # Gift/shopping scenarios
    elif any(word in query_lower for word in ['gift', 'present', 'birthday', 'anniversary', 'party']):
        return """That's so thoughtful! 🎁 I'd love to help you find the perfect gift!
        
To give you the best recommendations, could you tell me:
• **Who is it for?** (man, woman, child, teen)
• **What's the occasion?** (birthday, anniversary, etc.)
• **Any interests they have?** (sports, fashion, tech)
• **Budget range?** (if you have one in mind)

I can suggest from our amazing collection of shoes, clothing, accessories, watches, and much more!"""

    # Product category inquiries
    elif any(word in query_lower for word in ['products', 'items', 'sell', 'have', 'available']):
        return """Great question! We have an amazing selection of products across many categories:

🛍️ **Main Categories:**
• **Footwear** - Sneakers, boots, casual shoes, sports shoes
• **Clothing** - T-shirts, jackets, pants, dresses, casual wear
• **Accessories** - Watches, sunglasses, bags, belts
• **Sports & Fitness** - Athletic gear and activewear
• **Sports & Outdoor** - Athletic wear and gear

What category interests you most? Or tell me what you need and I'll help you find it! I can search in multiple languages too! 🌍"""

# ============================================================================
# AI-DRIVEN SEARCH SUGGESTIONS - COPILOT-LIKE INTELLIGENT RECOMMENDATIONS
# ============================================================================

def generate_ai_search_suggestions(query: str, products_data: list, customer_id: str = None) -> dict:
    """
    🤖 AI-DRIVEN Search Suggestions Generator - Pure Agentic AI Approach
    
    Generates intelligent, context-aware suggestions like Copilot/Gemini after search results.
    NO HARDCODING - Uses AI prompts to understand context and generate relevant suggestions.
    
    Features:
    - Analyzes search query and results using AI
    - Suggests matching accessories from catalog
    - Offers budget-based filtering options
    - Recommends related product categories
    - Provides personalized suggestions based on context
    - All suggestions are catalog-relevant and AI-generated
    
    Args:
        query: Original search query from user
        products_data: List of product dictionaries returned from search
        customer_id: Optional customer ID for personalized suggestions
    
    Returns:
        dict with AI-generated suggestions in copilot-style format
    """
    print(f"🤖 Generating AI-driven search suggestions for query: '{query}'")
    
    try:
        # Extract product information for AI analysis
        product_names = [p.get('product_name', '') for p in products_data]
        product_categories = []
        price_range = {
            'min': min([p.get('price', 0) for p in products_data]) if products_data else 0,
            'max': max([p.get('price', 0) for p in products_data]) if products_data else 0
        }
        
        # Build context for AI
        product_context = ", ".join(product_names[:5])  # First 5 products
        
        # Derive category label from query for specificity
        query_lower = query.lower()
        CATALOG_CATEGORIES = ["jackets", "tshirts", "t-shirts", "shirts", "shoes", "sneakers",
                               "boots", "watches", "sunglasses", "bags", "caps", "hats",
                               "shorts", "hoodies", "sweatshirts", "socks", "accessories",
                               "dresses", "trousers", "jeans", "coats", "scarves", "belts"]
        detected_category = next((c for c in CATALOG_CATEGORIES if c in query_lower), None)
        category_hint = f'The user searched for "{detected_category}".' if detected_category else ""

        # 🧠 AI PROMPT: Analyze search and generate suggestions
        suggestion_prompt = f"""
You are an intelligent fashion e-commerce assistant. After showing search results, generate 2 or 3 SHORT, smart follow-up suggestions to help the user explore further.

USER SEARCH QUERY: "{query}"
PRODUCTS FOUND: {len(products_data)} items
SAMPLE PRODUCTS: {product_context}
PRICE RANGE: ${price_range['min']:.2f} – ${price_range['max']:.2f}
{category_hint}

AVAILABLE FEATURES IN OUR STORE:
- Matching accessories (bags, watches, caps, sunglasses, belts, scarves, socks) for main clothing categories
- Budget/price filtering ("under $X", "between $X and $Y")
- Related clothing categories (jackets, tshirts, shoes, hoodies, shorts, dresses, etc.)
- Active promotions and seasonal offers
- Outfit builder and complete-look recommendations

INSTRUCTIONS:
- Generate EXACTLY 2 or 3 suggestions (never fewer than 2, never more than 3).
- Each suggestion must be directly relevant to what the user just searched for.
- Each suggestion must map to one of these types: accessories | budget | category | promotions | personalization | general
- Suggestions must be SHORT (1 sentence), conversational, and end with a call-to-action.
- Only suggest accessories if the searched category can realistically have accessories in our catalog.
- Only suggest promotions if the price range is $30+.
- Avoid repeating the same type twice.
- Do NOT invent product categories we don't carry.

OUTPUT (return ONLY valid JSON, no extra text):
{{
    "suggestions": [
        {{"type": "...", "text": "..."}},
        {{"type": "...", "text": "..."}}
    ]
}}
"""
        
        # 🤖 Call AI to generate suggestions
        response = llm.invoke(suggestion_prompt)
        suggestions_text = response.content.strip()
        
        # Parse AI response
        import json
        import re
        
        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'\{.*\}', suggestions_text, re.DOTALL)
        if json_match:
            suggestions_json = json.loads(json_match.group())
        else:
            # Fallback: 2 minimal suggestions
            suggestions_json = {
                "suggestions": [
                    {"type": "general", "text": "Need help narrowing down your search? Tell me your preferences!"},
                    {"type": "promotions", "text": "Would you like me to check if any of these items have current offers?"}
                ]
            }
        
        print(f"✅ Generated {len(suggestions_json.get('suggestions', []))} AI-driven suggestions")
        
        # 🗃️ ENHANCE: Add catalog-aware accessory checking
        # Check if we actually have accessories for these products
        if any(s['type'] == 'accessories' for s in suggestions_json.get('suggestions', [])):
            has_accessories = check_accessories_availability(products_data)
            if not has_accessories:
                # Remove accessory suggestion if none available
                suggestions_json['suggestions'] = [s for s in suggestions_json['suggestions'] if s['type'] != 'accessories']
                print("⚠️ Removed accessory suggestion - no matching accessories in catalog")
        
        # 🎯 LIMIT: Ensure maximum 3 suggestions
        suggestions_json['suggestions'] = suggestions_json.get('suggestions', [])[:3]
        print(f"📊 Final suggestion count: {len(suggestions_json.get('suggestions', []))} (max 3)")
        
        return {
            "has_suggestions": len(suggestions_json.get('suggestions', [])) > 0,
            "suggestions": suggestions_json.get('suggestions', []),
            "query_context": query,
            "result_count": len(products_data)
        }
        
    except Exception as e:
        print(f"🚨 AI Suggestion Generation Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Minimal fallback - still conversational
        return {
            "has_suggestions": True,
            "suggestions": [
                {"type": "general", "text": "Need help finding something specific? Tell me your style or budget and I'll refine the results!"},
                {"type": "promotions", "text": "Some of these items might have special offers. Want me to check for active deals?"}
            ],
            "query_context": query,
            "result_count": len(products_data)
        }

def check_accessories_availability(products_data: list) -> bool:
    """
    Check if matching accessories exist in catalog for given products.
    Uses the accessories.csv mapping to determine availability.
    
    Args:
        products_data: List of product dictionaries
    
    Returns:
        bool: True if matching accessories found, False otherwise
    """
    try:
        conn = hana_connect()
        cursor = conn.cursor()
        
        # Get product IDs from search results
        product_ids = [str(p.get('product_id', '')).strip() for p in products_data if p.get('product_id')]
        
        if not product_ids:
            return False
        
        # Query accessories table for matches
        placeholders = ','.join(['?' for _ in product_ids])
        query = f"""
            SELECT COUNT(*) as accessory_count
            FROM SAP_ACCESSORIES_COMMERCE_2211
            WHERE PRODUCT_ID IN ({placeholders})
            AND PRODUCT_IDS IS NOT NULL
            AND PRODUCT_IDS != ''
        """
        
        cursor.execute(query, product_ids)
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        has_accessories = result[0] > 0 if result else False
        print(f"🔍 Accessory availability check: {has_accessories} (checked {len(product_ids)} products)")
        
        return has_accessories
        
    except Exception as e:
        print(f"⚠️ Accessory availability check failed: {e}")
        return False  # Conservative: don't show accessory suggestion if check fails

    # Default helpful response
    else:
        return """Hi! I'm here to help you find exactly what you need! 😊
        
I can assist you with finding products from our extensive collection including shoes, clothing, accessories, and much more.

What are you looking for today? You can tell me:
• Specific items you need
• The occasion you're shopping for  
• Who you're buying for
• Your style preferences

I'll help you discover the perfect products! What can I help you find? 🔍"""

tools=[get_order_history, get_orders_by_status, query_orders, find_offers_for_products, get_product_details, query_products, ai_semantic_product_search, ai_context_price_filter, find_accessories, search_products_with_promotions, faq_answers,add_to_cart, show_cart, create_order, ai_personalized_recommendations, ai_conversational_assistant]

tools_by_name = {tool.name: tool for tool in tools}
model = llm.bind_tools(tools)
# this is similar to customizing the create_react_agent with 'prompt' parameter, but is more flexible
# system_prompt = SystemMessage(
#     "You are a helpful assistant that use tools to access and retrieve information from a weather API. Today is 2025-03-04. Help the user with their questions. Use the history to answer the question."
# )
 
# Define our tool node
def call_tool(state: AgentState):
    # print("Calling tool with state:", state)  # Debugging output
    outputs = []
    # Iterate over the tool calls in the last message
    for tool_call in state["messages"][-1].tool_calls:
        try:
            # Get the tool by name and invoke it with the provided arguments
            tool_result = tools_by_name[tool_call["name"]].invoke(tool_call["args"])
            # Serialize to JSON string so datetime/Decimal objects are handled correctly
            if isinstance(tool_result, dict):
                try:
                    tool_result = json.dumps(tool_result, default=str)
                except Exception:
                    tool_result = str(tool_result)
            outputs.append(
                ToolMessage(
                    content=tool_result,
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )
        except Exception as e:
            print(f"Error invoking tool {tool_call['name']}: {str(e)}")  # Debugging output
            outputs.append(
                ToolMessage(
                    content=f"Error invoking tool {tool_call['name']}: {str(e)}",
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )
    # Return the generated tool messages
    return {"messages": outputs}
 


def call_model(
    state: AgentState,
    config: RunnableConfig,
):
    # Add intelligent system prompt for conversational AI assistant
    system_prompt = SystemMessage(content="""🤖 You are an AI e-commerce shopping assistant. You MUST use tools to fetch data from the database.

🚨 CRITICAL RULE: NEVER provide direct text responses for product/order queries. ALWAYS use the appropriate tool.

🎯 **MANDATORY TOOL USAGE - NO EXCEPTIONS:**

**For product searches with price constraints:**
- Query pattern: "tshirts under 50", "jackets between 100-200", "shoes over 80"
- MUST use: `ai_context_price_filter` tool
- Examples: 
  • "Find Tshirts under £50" → CALL ai_context_price_filter("Find Tshirts under £50")
  • "Jackets between 100 and 200 pounds" → CALL ai_context_price_filter("Jackets between 100 and 200 pounds")

**For product searches WITHOUT price:**
- Query pattern: "show me tshirts", "find jackets", "shoes", "watches"
- MUST use: `ai_semantic_product_search` tool
- Examples:
  • "show me tshirts" → CALL ai_semantic_product_search("show me tshirts")
  • "find jackets" → CALL ai_semantic_product_search("find jackets")

**For order history:**
- Query pattern: "my orders", "show my orders", "order history"
- MUST use: `get_order_history` tool
- Examples:
  • "show my orders" → CALL get_order_history("show my orders")

**🚨 IMPORTANT:**
- If user asks for products: CALL a tool (ai_semantic_product_search or ai_context_price_filter)
- If user asks for orders: CALL get_order_history tool
- NEVER generate product data yourself
- NEVER respond with text like "Here are some products..." without calling a tool first
- ALWAYS wait for tool results before responding

**🧠 INTELLIGENT TOOL SELECTION:**

You are an intelligent AI that understands user intent. Use your reasoning to select the right tool:

**`get_order_history`** - For personal order/purchase history queries:
- When user asks about THEIR orders, purchase history, past orders
- Keywords: "my orders", "show my orders", "order history", "my purchases", "view my orders"
- Example thinking: "show my orders" → user wants to see their purchase history, use get_order_history
- CRITICAL: "my" or "mine" = personal orders, NOT product search!

**`ai_context_price_filter`** - For queries with price/budget constraints:
- When user mentions price ranges, budgets, or cost limits
- Smart detection of price intent: "above", "under", "between", "premium", "expensive", "cheap", "affordable"
- Understands currency and numeric values in context
- Example thinking: "premium tshirts above £60" → user wants price filtering, use price tool

**`ai_semantic_product_search`** - For product searches without price constraints:
- When user wants to find products by category, activity, or description
- No price/budget mentioned in query
- Example thinking: "ski gear" → user wants ski products, no price mentioned, use semantic search
- IMPORTANT: "show jackets" = product search, but "show MY orders" = order history!

**`find_accessories`** - For accessory requests on previously shown products:
- ONLY when user previously searched products and now asks for accessories
- Example thinking: "show accessories for these" → user wants accessories for their search results
- Example thinking: "any accessories of these" → user wants accessories for their search results, use find_accessories
- Example thinking: "any accessories" → user wants accessories for products they just viewed, use find_accessories
- Triggers: "any accessories of these", "any accessories", "accessories of these", "accessories for these", "show accessories"

**Smart Reasoning Guidelines:**
- Order history queries = get_order_history (e.g., "show my orders", "order history", "my orders")
- Activity + accessories = semantic search (e.g., "ski gear and accessories")
- Product + price = price filter (e.g., "tshirts above 60")
- Just product = semantic search (e.g., "show tshirts")
- Just accessories after product search = find_accessories (e.g., "accessories for these", "any accessories of these", "any accessories")

**CRITICAL: Order vs Product Detection:**
- "show MY orders" → ORDER HISTORY (possessive "my" indicates personal orders)
- "show jackets" → PRODUCT SEARCH (searching for products to buy)
- "my orders" → ORDER HISTORY (personal purchase history)
- "show tshirts" → PRODUCT SEARCH (browsing products)

**Use `find_accessories` ONLY when:**
- User previously searched for products and now asks for accessories
- Query is ONLY about accessories: "show accessories for these", "accessories of these products", "any accessories of these", "any accessories", "accessories of these"
- Examples: "any accessories of these" → find_accessories, "accessories of these items" → find_accessories
- **NEVER use** when query mentions activity + accessories: "ski gear and accessories" → use ai_semantic_product_search

**Use `ai_conversational_assistant` when AI detects:**
- General conversation without product context
- Broad scenario planning without specific product focus
- Store information and policy questions
- **AI Rule**: Only when no product need is detected

**🎯 INTELLIGENT PROMOTION DETECTION:**
- `find_offers_PRIORITY_for_products`: **AI PRIORITY** for contextual offer requests
  - AI detects: "any offer on these", "deals on these", "offers for these products"
  - Smart context: User searched products, now asking about offers
  - **AI Intelligence**: Extract conversation context, find relevant offers
  - **Never**: Generate text responses for offer requests
- `search_products_with_promotions`: For general promotional browsing
  - AI detects: "show discounted products", "find promotional items"

**🧠 ADVANCED AI CAPABILITIES:**
- Smart activity understanding (skiing → ski gear, beach → swimwear)
- Intelligent location context (Kashmir → ski equipment, Miami → beach gear)
- Natural language price filtering with AI comprehension
- Multi-language understanding with automatic intent translation
- Context-aware product recommendations
- Semantic similarity matching with AI scoring
- Cart operations: `add_to_cart`, `show_cart`, `create_order`

💡 **PERFECT E-COMMERCE AI BEHAVIOR:**
1. **ANALYZE QUERY**: Understand what the user really wants (product type, price range, activity)
2. **SMART TOOL SELECTION**: Choose the right tool based on query analysis (price tool if budget mentioned, semantic search otherwise)
3. **IMMEDIATE ACTION**: Search and show results instantly
4. **SHOW RESULTS FIRST**: Display products immediately, no unnecessary questions
5. **INTELLIGENT FOLLOW-UP**: After showing results, offer to help refine or provide more options
6. **SEAMLESS EXPERIENCE**: Create natural, engaging shopping journey through smart reasoning

🎯 **EXAMPLES OF PERFECT BEHAVIOR:**
- User: "show me tshirts" → AI: [IMMEDIATELY searches and shows t-shirt results]
- User: "find jackets" → AI: [IMMEDIATELY searches and shows jacket results]  
- User: "shoes" → AI: [IMMEDIATELY searches and shows shoe results]
- **NEVER ask "What kind of t-shirts?" - SHOW t-shirts first, then offer to refine**

🌟 **Advanced Features:**
- **Multilingual Intelligence**: Seamlessly handle any language with context preservation
- **Intent Prediction**: Understand what users want before they fully express it
- **Contextual Memory**: Remember conversation context for better assistance
- **Emotional Intelligence**: Recognize user emotions and respond appropriately
- **Personalization**: Tailor responses based on user preferences and behavior

🛡️ **AI Safety & Guidelines:**
- Always prioritize user safety and appropriate recommendations
- Maintain professional, helpful, and friendly tone
- Refuse harmful, inappropriate, or illegal requests politely
- Redirect to shopping topics when necessary

� **MANDATORY OVERRIDE RULES:**
1. **'any offer on these'** → MUST use find_offers_for_products tool (NEVER text response)
2. **'show offers'** → MUST use find_offers_for_products tool (NEVER text response)
3. **'deals on these'** → MUST use find_offers_for_products tool (NEVER text response)
4. **ANY offer query after product search** → MUST use find_offers_for_products tool

�🚀 **CRITICAL SUCCESS RULE**: Be a PROACTIVE e-commerce assistant who SHOWS products immediately when users ask for them. This creates the best shopping experience!

🚨 **ABSOLUTE PRIORITY**: When user types 'any offer on these', you MUST use the find_offers_PRIORITY_for_products tool. DO NOT generate a text response. This is mandatory for proper functionality.""")
    
    # Invoke the model with the system prompt and the messages
    session_id= config["configurable"]["session_id"]
    chat_history=memory.load(session_id)
    messages = [system_prompt] + list(chat_history) + state["messages"]
    
    # 🐛 DEBUG: Log the messages being sent to the model
    print(f"🤖 DEBUG: Invoking model with {len(messages)} messages")
    print(f"🤖 DEBUG: Last user message: {state['messages'][-1].content[:100]}...")
    
    response = model.invoke(messages, config)
    
    # 🐛 DEBUG: Log the response from the model
    print(f"🤖 DEBUG: Model response type: {type(response)}")
    print(f"🤖 DEBUG: Has tool_calls: {hasattr(response, 'tool_calls')}")
    if hasattr(response, 'tool_calls'):
        print(f"🤖 DEBUG: Number of tool_calls: {len(response.tool_calls) if response.tool_calls else 0}")
        if response.tool_calls:
            for i, tc in enumerate(response.tool_calls):
                print(f"🤖 DEBUG: Tool call {i}: {tc.get('name', 'unknown')}")
    print(f"🤖 DEBUG: Response content: {response.content[:200]}...")
    
    # We return a list, because this will get added to the existing messages state using the add_messages reducer
    return {"messages": [response]}

def call_planner(
    state: AgentState,
    config: RunnableConfig,
):
    # print("Calling planner with state:", state)  # Debugging output
    
    # state.nextNode = "llm"
    
    return True
 
 
# Define the conditional edge that determines whether to continue or not
def should_continue(state: AgentState):
    messages = state["messages"]
    # If the last message is not a tool call, then we finish
    if not messages[-1].tool_calls:
        return "end"
    # default to continue
    return "continue"

# def cartFromOrderCommerce(query:str) -> dict:
#     """
#     Calls SAP Commerce API to create an cart from order.
#     """
#     customer_id=query.split(",")[0]
#     order_code=query.split(",")[1]
#     url=config_properties['DEFAULT']['commerce_base_url']+config['DEFAULT']['cart_from_order_url']
#     url=url.replace("<customerID>",customer_id)
#     url=url.replace("<orderCode>",order_code)
#     print(f"Calling SAP Commerce API to create cart from order with URL: {url}")
#     response = requests.request("POST", url, headers=headers)

def response_type(query:str):
    """
    Determines the type of response being returned based on the query.
    """
    # llm=llm.with_structured_output(FinalResponse)
    llm_response=llm.invoke(f"Determine if the following query is related to 'products', 'orderhistory', 'productComparison' or 'other'. Respond with one word only from these 4 options."
                            f"If the query is asking for the complete details of a specific order or multiple orders, respond with 'orderhistory'."
                            f"If the query is asking for the complete details of a specific product or a list of products, respond with 'product'."
                            f"If the query is asking specifically to compare two or more products, respond with 'productComparison'."
                            f"If the query is asking for something specific about a product or order like price of a product, or price of an order, or if the query is not related to product or order then respond with 'other'."
                            f"Query:{query}")
    print(f"Response from llm for response type: {llm_response.content}")
    return llm_response.content


def create_mock_product_response(query: str, response_content: str) -> dict:
    """
    Create a mock product response for testing the carousel functionality.
    """
    query_lower = query.lower()
    
    # Different product sets based on query
    if 'shoe' in query_lower or 'shoes' in query_lower:
        mock_products = [
            {
                'product_id': '1234',
                'product_name': 'Running Shoes',
                'summary': 'Comfortable running shoes for everyday use.',
                'price': 79.99,
                'image_url': 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=200&h=200&fit=crop&crop=center'
            },
            {
                'product_id': '5678',
                'product_name': 'Hiking Boots',
                'summary': 'Durable hiking boots for outdoor adventures.',
                'price': 129.99,
                'image_url': 'https://images.unsplash.com/photo-1544966503-7cc5ac882d5f?w=200&h=200&fit=crop&crop=center'
            },
            {
                'product_id': '9012',
                'product_name': 'Dress Shoes',
                'summary': 'Elegant dress shoes for formal occasions.',
                'price': 99.99,
                'image_url': 'https://images.unsplash.com/photo-1549298916-b41d501d3772?w=200&h=200&fit=crop&crop=center'
            }
        ]
    else:
        # Default tech products
        mock_products = [
            {
                'product_id': 'PROD001',
                'product_name': 'Wireless Bluetooth Headphones',
                'summary': 'High-quality wireless headphones with noise cancellation',
                'price': 99.99,
                'image_url': 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=200&h=200&fit=crop&crop=center'
            },
            {
                'product_id': 'PROD002',
                'product_name': 'Smart Phone Case',
                'summary': 'Durable protective case for your smartphone',
                'price': 24.99,
                'image_url': 'https://images.unsplash.com/photo-1601593346740-925612772716?w=200&h=200&fit=crop&crop=center'
            },
            {
                'product_id': 'PROD003',
                'product_name': 'USB-C Cable',
                'summary': 'Fast charging USB-C cable 6ft length',
                'price': 12.99,
                'image_url': 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=200&h=200&fit=crop&crop=center'
            }
        ]
    
    # Clean the response content to remove any JSON artifacts
    clean_response = response_content
    if '```html' in clean_response or '```json' in clean_response:
        # Extract only the HTML part before any code blocks
        clean_response = clean_response.split('```')[0].strip()
    
    # Remove any JSON structure that might have leaked into the response
    import re
    clean_response = re.sub(r'\{[^{}]*"response_type"[^{}]*\}', '', clean_response)
    clean_response = clean_response.strip()
    
    if not clean_response:
        clean_response = "Here are some products I found for you:"
    
    return {
        'response_type': 'products_list',
        'ai_response': clean_response,
        'products_data': mock_products
    }

def detect_order_query_with_ai(query: str) -> bool:
    """
    Fast keyword-based order query detection — no LLM call needed.
    Distinguishes personal order history queries from product searches and cart queries.
    """
    q = query.lower()

    # Cart queries are never order queries — check first
    cart_phrases = ['my cart', 'show cart', 'view cart', 'display cart', "what's in my cart"]
    if any(p in q for p in cart_phrases):
        return False

    # Must contain 'order' or 'purchase' to be an order query
    if 'order' not in q and 'purchase' not in q:
        return False

    # Phrases that clearly indicate personal order history
    order_phrases = [
        'my order', 'my orders', 'order history', 'order status',
        'past orders', 'previous orders', 'recent orders',
        'view orders', 'show orders', 'list orders',
        'track order', 'where is my order', 'my purchase', 'my purchases',
        'what did i order', 'what have i ordered', 'my recent order'
    ]
    return any(p in q for p in order_phrases)

def format_order_history_response(orders: list) -> str:
    """
    Format order history results into an HTML table for display
    """
    print(f"📋 Formatting {len(orders)} orders for display")
    
    # Build HTML table
    html = """
    <div style='font-family: Arial, sans-serif; margin: 10px 0;'>
        <h3 style='color: #667eea; margin-bottom: 15px;'>
            <i class='fas fa-shopping-bag'></i> Your Order History ({count} orders)
        </h3>
        <table style='width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);'>
            <thead>
                <tr style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;'>
                    <th style='padding: 12px; text-align: left; font-weight: 600;'>Order ID</th>
                    <th style='padding: 12px; text-align: left; font-weight: 600;'>Product</th>
                    <th style='padding: 12px; text-align: center; font-weight: 600;'>Image</th>
                    <th style='padding: 12px; text-align: left; font-weight: 600;'>Date</th>
                    <th style='padding: 12px; text-align: left; font-weight: 600;'>Status</th>
                    <th style='padding: 12px; text-align: right; font-weight: 600;'>Price</th>
                </tr>
            </thead>
            <tbody>
    """.replace('{count}', str(len(orders)))
    
    # Add each order as a row
    for i, order in enumerate(orders):
        order_id = order.get('order_id', 'N/A')
        product_name = order.get('product_name', 'Unknown Product')
        image_url = order.get('image_url', 'https://via.placeholder.com/80')
        order_date = order.get('order_date', 'N/A')
        order_status = order.get('order_status', 'N/A')
        total_price = order.get('total_price', 0)
        
        # Format date if it's a datetime object
        if hasattr(order_date, 'strftime'):
            order_date = order_date.strftime('%d %b %Y')
        
        # Status color
        status_color = '#3b82f6'  # blue
        if str(order_status).lower() == 'approved':
            status_color = '#10b981'  # green
        elif str(order_status).lower() == 'open':
            status_color = '#3b82f6'  # blue
        
        # Alternating row colors
        row_bg = '#ffffff' if i % 2 == 0 else '#f9fafb'
        
        html += f"""
                <tr style='background: {row_bg}; border-bottom: 1px solid #e5e7eb;'>
                    <td style='padding: 12px; font-weight: 600; color: #667eea;'>#{order_id}</td>
                    <td style='padding: 12px; color: #374151;'>{product_name}</td>
                    <td style='padding: 12px; text-align: center;'>
                        <img src='{image_url}' alt='{product_name}' style='width: 60px; height: 60px; object-fit: cover; border-radius: 6px; border: 1px solid #e5e7eb;' onerror='this.src="https://via.placeholder.com/80"'>
                    </td>
                    <td style='padding: 12px; color: #6b7280;'>{order_date}</td>
                    <td style='padding: 12px;'>
                        <span style='background: {status_color}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600;'>{order_status}</span>
                    </td>
                    <td style='padding: 12px; text-align: right; font-weight: 600; color: #10b981;'>£{float(total_price):.2f}</td>
                </tr>
        """
    
    html += """
            </tbody>
        </table>
    </div>
    """
    
    return html

def process_query(customer_id: str,cart_id: str, query: str,commerce_token:str) -> str:
    """
    Process the user's query using the agent or directly call the tool.
    """
# Debug removed

    # 🎯 CRITICAL: Set customer_id in environment for tools to access
    import os
    os.environ['CURRENT_CUSTOMER_ID'] = customer_id if customer_id else ''

    # 🛒 CART QUERY DETECTION - Check FIRST before order detection (cart queries can contain "my")
    cart_keywords = ['show my cart', 'view cart', 'show cart', 'display cart', 'cart contents', 'my cart', "what's in my cart", 'view my cart', 'see my cart']
    is_cart_query = any(keyword in query.lower() for keyword in cart_keywords)
    
    # 🛒 CRITICAL FIX: If cart query detected, directly call show_cart tool (HIGHEST PRIORITY)
    if is_cart_query:
        print(f"🛒 CART QUERY DETECTED - Directly calling show_cart tool")
        try:
            # Directly call the show_cart function
            cart_result = show_cart.invoke(query)
            print(f"✅ Cart tool result: {cart_result}")
            
            # show_cart returns a dict with 'message' containing HTML
            if 'message' in cart_result:
                return cart_result['message']
            else:
                return """
                <div style='padding: 20px; background: #f0f9ff; border-radius: 8px; color: #0369a1; border: 2px solid #7dd3fc;'>
                    🛒 <strong>Your cart is ready!</strong> The cart interface should appear above.
                </div>
                """
        except Exception as e:
            print(f"❌ Error calling cart tool directly: {str(e)}")
            import traceback
            print(traceback.format_exc())
            # Fall through to agent if direct call fails

    # 🤖 AI-DRIVEN ORDER QUERY DETECTION - More intelligent and precise (AFTER cart check)
    is_order_query = detect_order_query_with_ai(query)
    
    if is_order_query and (not customer_id or customer_id.strip() == ''):
        return """
        <div style='padding: 25px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; color: white; font-family: Arial, sans-serif; box-shadow: 0 4px 15px rgba(0,0,0,0.2); margin: 10px 0;'>
            <div style='display: flex; align-items: center; margin-bottom: 15px;'>
                <div style='background: rgba(255,255,255,0.2); border-radius: 50%; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; margin-right: 15px; font-size: 20px;'>
                    🔐
                </div>
                <h3 style='margin: 0; font-size: 18px; font-weight: 600;'>Login Required</h3>
            </div>
            <p style='margin: 0 0 15px 0; font-size: 14px; line-height: 1.5; opacity: 0.9;'>
                To view your order history, please log in to your account first.
            </p>
            <div style='background: rgba(255,255,255,0.1); padding: 12px; border-radius: 8px; font-size: 13px;'>
                💡 <strong>Tip:</strong> Enter your email address in the login field above to access your orders.
            </div>
        </div>
        """
    
    # 🚀 CRITICAL FIX: If order query detected AND customer is logged in, directly call order tool
    if is_order_query and customer_id and customer_id.strip() != '':
        print(f"🎯 ORDER QUERY DETECTED - Directly calling get_order_history tool for customer: {customer_id}")
        try:
            # Directly call the get_order_history function
            order_result = get_order_history.invoke(query)
            print(f"✅ Order tool result: {order_result}")
            
            # Return structured response for frontend processing
            if 'results' in order_result and len(order_result['results']) > 0:
                # Return JSON structure that frontend expects
                return {
                    'response_type': 'order_history',
                    'orders_data': order_result['results'],
                    'ai_response': f"Found {len(order_result['results'])} orders in your history."
                }
            elif 'ai_response' in order_result:
                # Return login required or other messages
                return {
                    'ai_response': order_result['ai_response']
                }
            elif 'error' in order_result:
                return {
                    'ai_response': f"<div style='padding: 20px; background: #fee; border-radius: 8px; color: #c00;'>❌ {order_result['error']}</div>"
                }
            else:
                return {
                    'ai_response': """
                <div style='text-align: center; padding: 40px; background-color: #f8f9fa; border-radius: 8px; border: 2px dashed #dee2e6; font-family: Arial, sans-serif;'>
                    <h3 style='color: #6c757d; margin: 0 0 10px 0;'>📦 No Orders Found</h3>
                    <p style='color: #6c757d; margin: 0; font-size: 16px;'>You haven't placed any orders yet. Start shopping to see your order history here!</p>
                </div>
                """
                }
        except Exception as e:
            print(f"❌ Error calling order tool directly: {str(e)}")
            import traceback
            print(traceback.format_exc())
            # Fall through to agent if direct call fails

    system_prompt = SystemMessage(
        content=(
            "🚨 === CRITICAL: ORDER QUERY DETECTION (HIGHEST PRIORITY) ==="
            "⚡ BEFORE ANYTHING ELSE: Check if query is about ORDERS/ORDER HISTORY!"
            "📝 ORDER QUERY KEYWORDS: 'my orders', 'show my orders', 'order history', 'my purchases', 'view my orders', 'show orders', 'my order history'"
            "✅ IF QUERY CONTAINS ANY ORDER KEYWORD → IMMEDIATELY use get_order_history tool!"
            "❌ NEVER use ai_semantic_product_search for order queries!"
            "🎯 EXAMPLES:"
            "  • 'show my orders' → USE get_order_history (NOT product search!)"
            "  • 'my order history' → USE get_order_history (NOT product search!)"
            "  • 'view my orders' → USE get_order_history (NOT product search!)"
            "  • 'show jackets' → USE ai_semantic_product_search (product search)"
            ""
            " === GENERAL BEHAVIOR ==="
            "You are a helpful agent with access to tools. The tools return json response."
            "Your task is to answer user queries related to customer orders, products, shopping cart, or other topics in the storefront."
            "Your responses are shown directly to the customer, so they must be conversational, direct, and free of unnecessary information."
            "Only answer for queries related to the storefront. Do not fetch any information from the internet, only use the information available from the tools."
            "IMPORTANT: The customer_id parameter passed to process_query represents the current logged-in customer's email."
            "When a customer asks for 'my orders' or 'my order history', automatically use their customer_id as the email to search for."
            "🔓 CRITICAL: Product searches and accessories queries do NOT require authentication - they are public features!"

            "=== CART HANDLING ==="
            "For ADD TO CART requests: Use the add_to_cart tool with format 'product_id:<product_id>,quantity:<quantity>'"
            "For SHOW CART requests: ALWAYS use the show_cart tool when users ask to 'show my cart', 'view cart', 'what's in my cart', 'display cart', 'cart contents', or any cart viewing request."
            "The show_cart tool returns a smart interactive cart display that shows in the chat interface with full cart management capabilities."
            "Cart is managed in browser session storage, so inform users their cart persists during the session but resets on page refresh."
            "When adding items to cart, provide a friendly confirmation message with product details."
            "AUTHENTICATION: For cart operations, customer must be logged in. If no customer_id provided, inform user to login first."
            "CART INTELLIGENCE: Always prioritize show_cart tool for any cart-related viewing queries - it provides the best user experience."

            "=== CHAT HISTORY USAGE ==="
            "If chat history is provided, use it only as context to answer the query."
            "Use mainly the last message in the chat history as the primary context; earlier messages are for background only."
            "Do not act on chat history; take action only based on the latest message."
            "Example: If the last Human message is \"Add it to cart\" and the latest message is \"What is the product on order 1234?\", respond to order 1234. Do not add anything to cart."

            "=== INTELLIGENT PRODUCT HANDLING ==="
            "🤖 AI-DRIVEN PRODUCT DISCOVERY: You have access to advanced AI-powered product search capabilities that understand natural language, intent, and context across ALL languages."
            
            "🔍 **PRIMARY PRODUCT SEARCH TOOL**: ai_semantic_product_search"
            "• Use for ALL general product searches and discovery queries"
            "• Handles multilingual queries intelligently (Hindi, Spanish, French, German, Arabic, Chinese, Japanese, Korean, etc.)"
            "• Understands natural language intent: 'show me shoes', 'find red jackets', 'comfortable running shoes', 'formal wear for office'"
            "• AI-powered activity detection: 'going skiing' → winter sports gear, 'gym workout' → athletic wear"
            "• Location-based intelligence: 'going to Kashmir' → skiing gear, 'beach vacation' → swimwear"
            "• Price-aware searches: 'cheap shoes', 'premium watches', 'budget-friendly clothing'"
            "• Semantic understanding: Finds products based on meaning, not just keywords"
            
            "🎯 **WHEN TO USE ai_semantic_product_search**:"
            "• General product queries: 'show me shoes', 'find jackets', 'what shirts do you have'"
            "• Category browsing: 'shoes', 'clothing', 'accessories', 'watches'"
            "• Descriptive searches: 'red shoes', 'winter jackets', 'formal shirts'"
            "• Activity-based searches: 'skiing gear', 'gym clothes', 'office wear'"
            "• Location-based searches: 'Kashmir trip clothes', 'beach vacation items'"
            "• Natural language queries in ANY language: Hindi, Arabic, Spanish, French, German, Chinese, Japanese, etc."
            "• Intent-based searches: 'need something for running', 'looking for party wear'"
            "• Multilingual product queries: All languages supported with intelligent AI translation"
            
            "🚫 **CRITICAL: ZERO TOLERANCE FOR DUMMY DATA!**"
            "• If user asks for products in ANY language - ALWAYS use ai_semantic_product_search FIRST"
            "• NEVER respond with text-only responses like 'Here are some jackets I found' without using tools"
            "• NEVER provide dummy product data, sample responses, or fake product lists"
            "• NEVER create hardcoded responses with made-up product information"
            "• If ai_semantic_product_search returns empty results or 'no_results' flag, provide a helpful message with suggestions"
            "• When no results found, respond with: 'I couldn't find any products matching your search. Try: different keywords, broader search terms, or browse categories like jackets, tshirts, shoes, watches.'"
            "• DO NOT suggest alternative products or provide general shopping advice without tool results"
            "• ALL non-English queries MUST use ai_semantic_product_search - NO TEXT RESPONSES!"
            
            "📱 **SPECIFIC PRODUCT DETAILS**: Use get_product_details tool only when:"
            "• User asks about a SPECIFIC product by ID: 'Tell me about product 300123456'"
            "• User clicks on a specific product for more details"
            "• User says 'more details about this product' referring to a specific item"
            
            "⚡ **CRITICAL RULES**:"
            "• ALWAYS use ai_semantic_product_search for general product discovery"
            "• NEVER use query_products for natural language queries"
            "• NEVER respond about products without using tools first"
            "• NEVER provide dummy data or text-only responses for product queries"
            "• Let AI understand user intent rather than hardcoding patterns"
            "• Trust the AI semantic search to handle complex queries intelligently"
            "• Non-English queries MUST use ai_semantic_product_search - NO TEXT RESPONSES!"
            "• If no products found in database, say 'No products found' - DO NOT make up data"
            
            "🌟 **AI ADVANTAGE**: The ai_semantic_product_search tool uses advanced AI to understand what users really want, regardless of how they express it or what language they use!"

            "=== PROMOTION & DISCOUNT HANDLING ==="
            "For promotion or discount-related queries, you MUST use the search_products_with_promotions tool."
            "This includes queries about:"
            "Products on sale, with offers, or discounts"
            "Price-based filters like 'below 100 pounds', 'between 50 and 200 pounds'"
            "Discount-based filters like 'more than 50% discount', '20% to 30% discount'"
            "Time-based filters like 'discount ending in next 10 days'"
            "Festival-related promotions (e.g., 'Diwali offers', 'festival discounts')"
            "Category + discount filters (e.g., 'tshirts with discount', 'shoes below 100 pounds')"
            "Examples:"
            "Show me products below 100 pounds"
            "Show me tshirts below 50 pounds"
            "Show me products with more than 50% discount"
            "Show me festival offers"
            "Show me tshirts whose discount ends in next 10 days"
            "Show me products with 20% to 30% discount"
            "If the query contains price, discount, offer, sale, festival, or ends in, route to search_products_with_promotions."
            "If the query is a general product search without price/discount context, use semantic_product_search."
            "NEVER respond about promotions or discounts without using tools first."


            "=== ACCESSORIES HANDLING ==="
            "🤖 AI-DRIVEN APPROACH: For ANY accessory-related queries, you MUST use the find_accessories tool!"
            "🔍 Accessory queries include: 'show accessories', 'accessories of these products', 'accessories for these', 'what goes with these', 'accessories of these items', 'show accessories of these', 'find accessories'"
            "🧠 INTELLIGENT CONTEXT: The find_accessories tool uses AI to automatically extract product information from conversation history - you don't need to specify products manually!"
            "🔓 NO AUTHENTICATION REQUIRED: Accessories queries do NOT need customer_id or login - they work for all users!"
            "⚠️ NEVER ask for customer_id, email, or login for accessory requests - accessories are publicly available!"
            "✅ AI-POWERED PROCESSING: Simply call find_accessories with the user's exact query - it will:"
            "   • Use AI to automatically find products from previous search results"
            "   • Intelligently extract product IDs and names from conversation context"
            "   • Apply AI-driven semantic matching to return contextually appropriate accessories"
            "   • Filter out inappropriate items using intelligent category analysis"
            "❌ NEVER use query_products, ai_semantic_product_search, or other tools for accessory requests"
            "❌ NEVER respond with 'need customer id' or authentication errors for accessories"
            "🚫 CRITICAL: NO HARDCODED FALLBACKS - If no appropriate accessories found, return 'not found' instead of generic items"
            "📝 Examples of correct AI-driven usage:"
            "   • User: 'show accessories of these products' → Call find_accessories('show accessories of these products')"
            "   • User: 'accessories for these items' → Call find_accessories('accessories for these items')"
            "   • User: 'what accessories go with these' → Call find_accessories('what accessories go with these')"
            "🎯 The find_accessories tool uses ADVANCED AI and will handle all context extraction and intelligent matching automatically!"

            "=== GENERAL PRODUCT DISPLAY ==="
            "For every product detail returned, apart from the general product details, you must also include:"
            "- Product name (hyperlinked)"
            "- Product image (via image_url)"
            

            "=== ORDER HANDLING ==="
            "🔐 CRITICAL AUTHENTICATION: ALL order-related queries require customer authentication!"
            "🚫 AUTHENTICATION CHECK: If customer_id is empty, missing, or None, IMMEDIATELY return login prompt - DO NOT proceed with order tools!"
            "🎯 SMART ORDER TOOLS - Use the RIGHT tool for the RIGHT query (ONLY after authentication):"
            "• For GENERAL order queries ('my orders', 'show my orders', 'order history'): Use get_order_history tool"
            "• For STATUS-SPECIFIC queries ('my approved orders', 'show pending orders', 'completed orders'): Use get_orders_by_status tool"
            "• For COMPLEX order queries with SQL: Use query_orders tool"
            "🧠 INTELLIGENT STATUS DETECTION: The get_orders_by_status tool automatically:"
            "   - Detects status keywords: approved, pending, completed, ready, on hold"
            "   - Maps them to database values: APPROVED, OPEN, COMPLETED, READY, ON_HOLD"
            "   - Filters orders accordingly without hardcoding"
            "📝 EXAMPLES:"
            "   • 'show my approved orders' → get_orders_by_status (detects APPROVED status)"
            "   • 'show pending orders' → get_orders_by_status (detects OPEN status)"
            "   • 'my orders' → get_order_history (general query)"
            "🔐 AUTHENTICATION RULES:"
            "   • NEVER call order tools without valid customer_id"
            "   • ALWAYS check customer_id before processing order queries"
            "   • If no customer_id: Return professional login prompt, DO NOT call tools"
            "   • Order tools should handle their own authentication, but agent must verify first"
            "NEVER use product search tools for order-related queries. Order queries should ONLY use get_order_history, get_orders_by_status, or query_orders tools."
            "IMPORTANT: The customer_id passed in the context represents the customer's email address."
            "If the customer_id exists but no orders are found, show a nice 'no orders found' message instead of saying there's an error."
            "For order history queries, ALWAYS construct SQL like: 'SELECT o.ORDER_ID, o.ORDER_DATE, o.TOTAL_PRICE, o.PRODUCT_NAME, o.ORDER_STATUS, o.PRODUCT_ID, p.IMAGE_URL FROM SAP_ORDERS_COMMERCE_2211_V2 o LEFT JOIN SAP_PRODUCTS_COMMERCE_2211_V2 p ON o.PRODUCT_ID = p.PRODUCT_ID WHERE o.CUSTOMER_ID = ''customer_email'' ORDER BY o.ORDER_DATE DESC'"
            "Always replace 'customer_email' with the actual customer_id from the session context."
            "If asked for order details, always include some details of the product in the order."
            "Use orderID or productID from chat history if asked about them."
            "When displaying order history or multiple orders, format the response as an HTML table with proper headers."
            "For order history, include columns like Order ID, Date, Product Name, Total Price, and Status."
            "Use HTML table structure: <table>, <thead>, <tbody>, <tr>, <th>, <td> tags."
            "Make product names hyperlinked using the actual PRODUCT_ID from the order data."
            "Use format: <a href='/product/{PRODUCT_ID}/{encoded_product_name}'>{product_name}</a>"
            "If no orders are found, use this format:"
            "<div style='text-align: center; padding: 40px; background-color: #f8f9fa; border-radius: 8px; border: 2px dashed #dee2e6; font-family: Arial, sans-serif;'>"
            "<h3 style='color: #6c757d; margin: 0 0 10px 0;'>No Orders Found</h3>"
            "<p style='color: #6c757d; margin: 0; font-size: 16px;'>You haven't placed any orders yet. Start shopping to see your order history here!</p>"
            "</div>"

            "=== TOOL USAGE ==="
            "ALWAYS use appropriate tools to fetch data before responding."
            "CRITICAL RULE: Choose tools based on query intent, NOT query content similarity:"
            "- For GENERAL ORDER queries ('my orders', 'show my orders', 'order history', 'show order', 'view my orders'): ALWAYS use get_order_history tool"
            "- For STATUS-FILTERED ORDER queries ('my approved orders', 'show pending orders', 'completed orders', 'ready orders'): ALWAYS use get_orders_by_status tool"
            "- For SPECIFIC PRODUCT DETAILS ('tell me about product 123', 'show detailed information about product XYZ', 'product details', 'show product info'): ALWAYS use get_product_details tool"
            "- For GENERAL PRODUCT queries: **ALWAYS use ai_semantic_product_search tool** - this includes:"
            "  * Any product search in any language (English, Hindi, Spanish, etc.)"
            "  * Natural language product requests with context or intent"
            "  * Product searches with price, quality, or preference constraints"
            "  * Complex shopping scenarios and occasion-based searches"
            "  * Multilingual queries requiring intelligent translation and understanding"
            "  * 🎯 SPECIFIC ACTIVITY-BASED QUERIES: Queries mentioning SPECIFIC activities, sports, events"
            "  * Examples: 'going skiing', 'gym workout', 'office meeting tomorrow', 'hiking trip', 'running marathon'"
            "  * 🧠 SMART DETECTION: ANY query asking for products for SPECIFIC activities, events, or scenarios"
            "- For CONVERSATIONAL SCENARIO queries: **ALWAYS use ai_conversational_assistant tool** - this includes:"
            "  * GENERAL holiday/vacation queries without specific activities: 'going for a holiday', 'planning a vacation'"
            "  * Vague scenario queries that need clarification: 'need something for travel', 'going on a trip'"
            "  * Greeting and exploratory queries: 'hello', 'can you help me', 'what do you recommend'"
            "  * 🎯 RULE: If query is GENERAL (holiday, vacation, trip) → use ai_conversational_assistant to ask details"
            "  * 🎯 RULE: If query is SPECIFIC (skiing, swimming, hiking) → use ai_semantic_product_search directly"
            "- For PRICE FILTERING of PREVIOUS SEARCH RESULTS: **ALWAYS use ai_context_price_filter tool** - this includes:"
            "  * Queries like 'under 200', 'below 150', 'between 50 and 100', 'over 80'"
            "  * When user asks for price filtering after already searching for products"
            "  * Context-aware price constraints on previous product searches"
            "  * Examples: User searches 'jackets' then asks 'under 200 pounds' → use ai_context_price_filter"
            "- For CART queries ('add to cart', 'add product to cart'): use add_to_cart tool with proper format"
            "- For SHOW CART queries ('show my cart', 'view cart', 'what's in my cart', 'display cart', 'cart contents'): ALWAYS use show_cart tool"
            "- For ACCESSORIES queries ('show accessories', 'accessories for', 'what goes with'): use find_accessories tool"
            "- For specific order queries (with order ID): use query_orders tool"
            "- For FAQ questions: use faq_answers tool"
            "🌍 MULTILINGUAL PRIORITY: For ANY query containing non-English text (Hindi, Spanish, etc.), ALWAYS use ai_semantic_product_search tool."
            "NEVER confuse order queries with product queries. Order queries should NEVER use semantic_product_search."
            "Only provide direct responses for greetings or when no tools are needed."
            
            "=== RESPONSE FORMAT HANDLING ==="
            "After using tools to get data, provide conversational, helpful responses."
            "DO NOT include JSON structure in your response text."
            "Your response will be automatically formatted by the system when products are involved."
            "For get_product_details tool responses: Provide a brief, conversational description in PLAIN TEXT without any HTML tags or special formatting. The detailed product UI will be automatically generated. Keep responses concise and friendly."
            "For product search results: Provide context about the products found. The product carousel will be automatically generated."
            "Focus only on providing clear, helpful information to the customer."
            
            "=== HTML FORMATTING RULES ==="
            "For JSON responses with single product details: Use PLAIN TEXT in ai_response field, no HTML tags. The UI will render the product display."
            "For JSON responses with multiple products: Format ai_response field in simple HTML."
            "For order history responses: Format all responses in HTML."
            "For non-product responses: Format all responses in HTML."
            "NEVER use markdown formatting like *, **, [], () for links, triple backticks, or escape characters like  \\ or \". or asterisk"
            "For single product detail responses: Use plain conversational text only. Do NOT include hyperlinks, images, or HTML tags."
            "For multiple products or order history: When mentioning a product name, include a hyperlink in the format:"
            "<a href='/product/<productID>/<encodedProductName>'>product name</a>"
            "Ensure the product name is URL-encoded (e.g., spaces → %20, / → %2f)."
            "For bold text, use:"
            "<b>text</b>"
            "For order history or multiple orders, use this enhanced HTML table format:"
            "<div style='margin: 20px 0;'>"
            "<h3 style='color: #2c3e50; margin-bottom: 15px; font-family: Arial, sans-serif;'>Your Order History</h3>"
            "<table style='width: 100%; border-collapse: collapse; box-shadow: 0 2px 10px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; font-family: Arial, sans-serif;'>"
            "<thead style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;'>"
            "<tr><th style='padding: 15px 12px; text-align: left; font-weight: 600;'>Order ID</th>"
            "<th style='padding: 15px 12px; text-align: left; font-weight: 600;'>Date</th>"
            "<th style='padding: 15px 12px; text-align: left; font-weight: 600;'>Product</th>"
            "<th style='padding: 15px 12px; text-align: right; font-weight: 600;'>Price</th>"
            "<th style='padding: 15px 12px; text-align: center; font-weight: 600;'>Status</th></tr>"
            "</thead>"
            "<tbody>...enhanced table rows with styling...</tbody></table></div>"
            "For table rows, use alternating row colors and status badges:"
            "- Use style='background-color: #f8f9fa; padding: 12px; border-bottom: 1px solid #dee2e6;' for odd rows"
            "- Use style='background-color: #ffffff; padding: 12px; border-bottom: 1px solid #dee2e6;' for even rows"
            "- For status, use colored badges: APPROVED='✓ Approved', OPEN='○ Open', READY='● Ready', etc."
            "If the response from the FAQ table includes special characters or formatting, clean it up for readability."
            "Do not provide product or order details from the web; only use available data from tools."

            "=== CRITICAL QUERY CLASSIFICATION ==="
            "🎯 BEFORE choosing ANY tool, classify the query:"
            "1. GENERAL/VAGUE queries → ai_conversational_assistant"
            "2. SPECIFIC ACTIVITY queries → ai_semantic_product_search"
            "3. SPECIFIC PRODUCT queries → ai_semantic_product_search"
            "4. PRICE-SPECIFIC queries → ai_context_price_filter"
            
            "📝 GENERAL/VAGUE QUERIES (use ai_conversational_assistant):"
            "• 'going for a holiday' (NO specific activity mentioned)"
            "• 'planning a vacation' (NO specific activity mentioned)" 
            "• 'suggest products' (NO specific type mentioned)"
            "• 'what do you recommend' (NO specific category)"
            "• 'need gear' (NO specific type mentioned)"
            "• 'help me find something' (vague request)"
            
            "📝 SPECIFIC ACTIVITY QUERIES (use ai_semantic_product_search):"
            "• 'going skiing' (SPECIFIC activity)"
            "• 'gym workout' (SPECIFIC activity)"
            "• 'office meeting' (SPECIFIC scenario)"
            "• 'beach swimming' (SPECIFIC activity)"
            "• 'hiking trip' (SPECIFIC activity)"
            
            "📝 SPECIFIC PRODUCT QUERIES (use ai_semantic_product_search):"
            "• 'show me tshirts' (SPECIFIC product)"
            "• 'find jackets' (SPECIFIC product)"
            "• 'shoes' (SPECIFIC product)"
            
            "🚨 CRITICAL RULE:"
            "IF query is GENERAL/VAGUE → ai_conversational_assistant asks clarifying questions"
            "IF query is SPECIFIC → ai_semantic_product_search finds products directly"
            "NEVER use ai_conversational_assistant for specific activities or products!"

            "=== FALLBACK RESPONSE ==="
            "If you cannot find the answer after several attempts, respond with:"
            "Sorry, I couldn’t find the information you were looking for. Please try rephrasing your question."
        )
    )
    workflow = StateGraph(AgentState)
    workflow.add_node("llm", call_model)
    workflow.add_node("tools",  call_tool)
    # 2. Set the entrypoint as `agent`, this is the first node called
    workflow.set_entry_point("llm")
    # workflow.add_edge("planner", "llm")
    # 3. Add a conditional edge after the `llm` node is called.

    workflow.add_conditional_edges(
    # Edge is used after the `llm` node is called.
    "llm",
    # The function that will determine which node is called next.
    should_continue,
    # Mapping for where to go next, keys are strings from the function return, and the values are other nodes.
    # END is a special node marking that the graph is finish.
    {
        # If `tools`, then we call the tool node.
        "continue": "tools",
        # Otherwise we finish.
        "end": END,
    },)
    workflow.add_edge("tools", "llm")
    if not commerce_token:
        commerce_token='none'

    current_datetime = datetime.now()
    # Format the date and hour as dd-mm-yy:hh
    formatted_datetime = current_datetime.strftime("%d-%m-%y:%H")
    session_id=customer_id+"_"+formatted_datetime
    
    # 🧠 ENHANCED MEMORY HANDLING: Be more selective about when to clear memory
    # Only clear memory for very specific cases, NOT for general product searches
    # This preserves conversation context for accessories queries
    
    import re
    has_product_id = bool(re.search(r'product\s+\d+', query.lower()))
    
    # Only clear memory for truly independent searches that should start fresh
    # Don't clear for accessory queries or follow-up questions
    is_accessory_query = any(keyword in query.lower() for keyword in [
        'accessories', 'accessory', 'of these', 'of those', 'for these', 'for those',
        'go with', 'match', 'complement', 'what goes with'
    ])
    
    # Only clear memory in very specific cases
    should_clear_memory = (
        # Clear for new customer sessions (when no conversation history exists)
        not memory.load(session_id) or
        # Clear for login/logout related queries
        any(keyword in query.lower() for keyword in ['login', 'logout', 'sign in', 'sign out'])
    )
    
    # NEVER clear memory for accessory queries - they need product context!
    if is_accessory_query:
        should_clear_memory = False
    
    if should_clear_memory:
        memory.clear(session_id)

    # 🧠 CRITICAL: Set the session_id in environment for tools to access
    import os
    os.environ['CURRENT_SESSION_ID'] = session_id
    
    # Now we can compile and visualize our graph
    graph = workflow.compile(checkpointer=None)
    # Tools are properly bound to the model
    # 🎯 CRITICAL: Format the query properly so AI understands what to pass to tools
    # Combine metadata with the actual query in a single HumanMessage
    formatted_query = f"[Context: Customer ID: {customer_id}, Token: {commerce_token}]\n\nUser Query: {query}"
    response=graph.invoke({"messages": [system_prompt, HumanMessage(formatted_query)]},config={"configurable":{"session_id":customer_id+"_"+formatted_datetime}})
    
    # Get the response content and extract product data first
    response_content = response["messages"][-1].content
    
    # 🎯 CRITICAL: Extract ai_response from tool results (not from final AI message)
    # When tools use return_direct=True, we should use their ai_response field
    tool_ai_response = None
    
    # Check if any product-related tools were called and extract product data
    product_data = []
    order_data = []
    cross_sell_data = []  # 🔗 NEW: Store cross-sell products from tool responses
    
    # [Process cart data and product data...]
    
    # Check for cart display tools first
    cart_data = None
    for i, message in enumerate(response["messages"]):
        # Check for show_cart tool responses
        if hasattr(message, 'name') and message.name == 'show_cart':
            print(f"DEBUG: Found show_cart tool response")
            try:
                tool_result = message.content
                print(f"DEBUG: Processing show_cart tool result: {type(tool_result)}, content: {tool_result}")
                
                # If content is a string representation of a dict, parse it
                if isinstance(tool_result, str):
                    try:
                        import ast
                        tool_result = ast.literal_eval(tool_result)
                        print(f"DEBUG: Successfully parsed show_cart tool result as dict")
                    except (ValueError, SyntaxError) as e:
                        print(f"DEBUG: Failed to parse show_cart tool result as dict: {e}")
                        continue
                
                # If content is already a dict (direct tool response)
                if isinstance(tool_result, dict):
                    if 'message' in tool_result:
                        cart_data = tool_result
                        print(f"DEBUG: Extracted cart data: {cart_data}")
                        break
            except Exception as e:
                print(f"DEBUG: Error processing show_cart tool result: {e}")
                pass
    
    # Check for conversational assistant responses
    conversational_data = None
    for i, message in enumerate(response["messages"]):
        if hasattr(message, 'name') and message.name == 'ai_conversational_assistant':
            try:
                tool_result = message.content
                if isinstance(tool_result, str):
                    try:
                        import ast
                        tool_result = ast.literal_eval(tool_result)
                    except (ValueError, SyntaxError):
                        continue
                if isinstance(tool_result, dict):
                    if 'ai_response' in tool_result:
                        conversational_data = tool_result
                        break
            except Exception:
                pass

    # Check if any tools were called and extract data
    is_product_search = False  # Track if this was a search operation
    for i, message in enumerate(response["messages"]):

        # Check for ToolMessage responses from product-related tools (excluding order tools)
        if (hasattr(message, 'name') and message.name in ['get_product_details', 'query_products', 'search_products_with_promotions','ai_semantic_product_search', 'find_accessories', 'ai_context_price_filter']) or \
           (hasattr(message, 'tool_call_id') and hasattr(message, 'content') and hasattr(message, 'name') and message.name not in ['get_order_history', 'query_orders', 'get_orders_by_status']):
            # Track if this is a search operation (not specific product details)
            if hasattr(message, 'name') and message.name in ['query_products', 'search_products_with_promotions', 'ai_semantic_product_search', 'find_accessories', 'ai_context_price_filter', 'ai_personalized_recommendations']:
                is_product_search = True
            
            try:
                # Handle the tool response content
                tool_result = message.content
                
                # If content is a string representation of a dict, parse it
                if isinstance(tool_result, str):
                    try:
                        tool_result = json.loads(tool_result)
                    except (json.JSONDecodeError, ValueError):
                        try:
                            import ast
                            tool_result = ast.literal_eval(tool_result)
                        except (ValueError, SyntaxError):
                            pass  # Keep as string
                
                # If content is already a dict (direct tool response)
                if isinstance(tool_result, dict):
                    # 🎯 EXTRACT ai_response from tool result (priority over AI's verbose message)
                    if 'ai_response' in tool_result and not tool_ai_response:
                        tool_ai_response = tool_result['ai_response']
                    
                    # 🔗 EXTRACT cross_sell_products from tool result
                    if 'cross_sell_products' in tool_result and tool_result['cross_sell_products']:
                        cross_sell_data.extend(tool_result['cross_sell_products'])
                    
                    # 🎯 PRIORITY: Check for products_data field first (already formatted)
                    if 'products_data' in tool_result and tool_result['products_data']:
                        # Use products_data directly if it exists (already properly formatted)
                        for prod in tool_result['products_data']:
                            if prod not in product_data:  # Avoid duplicates
                                product_data.append(prod)
                    
                    # Fallback to results field if products_data wasn't used
                    if 'results' in tool_result and tool_result['results'] and not tool_result.get('products_data'):
                        for result in tool_result['results']:
                            # Only process as product if it has product fields but NOT order fields
                            if all(key in result for key in ['PRODUCT_ID', 'PRODUCT_NAME']) and 'ORDER_ID' not in result:
                                # Improved price parsing to handle various formats
                                # Use 'price' (display price) as the main price, falling back to 'PRICE' (original)
                                price_value = 0.0
                                try:
                                    # Try to get display price first (this is discounted if promotion exists)
                                    price_raw = result.get('price', result.get('PRICE', '0'))
                                    if isinstance(price_raw, str):
                                        # Extract numeric value from string, handle cases like "17.78\t" or " Eat sleep"
                                        import re
                                        price_match = re.search(r'(\d+\.?\d*)', str(price_raw).strip())
                                        if price_match:
                                            price_value = float(price_match.group(1))
                                    else:
                                        price_value = float(price_raw) if price_raw else 0.0
                                except (ValueError, TypeError):
                                    price_value = 0.0
                                
                                product_info = {
                                    'product_id': str(result.get('PRODUCT_ID', '')).strip(),
                                    'product_name': str(result.get('PRODUCT_NAME', '')).strip(),
                                    'summary': str(result.get('SUMMARY', '')).strip(),
                                    'price': price_value,
                                    'image_url': str(result.get('IMAGE_URL', '')).strip(),
                                    # Promotion fields - pass through all calculated values
                                    'PRICE': result.get('PRICE', price_value),  # Original price for frontend
                                    'original_price': result.get('original_price', result.get('PRICE', price_value)),
                                    'discounted_price': result.get('discounted_price', result.get('price', price_value)),
                                    'discount_percent': result.get('discount_percent', result.get('PROMO_DISCOUNT_PERCENT', 0)),
                                    'savings': result.get('savings', 0),
                                    'has_promotion': result.get('has_promotion', False),
                                    'PROMO_TITLE': result.get('PROMO_TITLE', ''),
                                    'PROMO_DESCRIPTION': result.get('PROMO_DESCRIPTION', ''),
                                    'PROMO_DISCOUNT_PERCENT': result.get('PROMO_DISCOUNT_PERCENT', result.get('discount_percent', 0)),
                                    'promo_title': result.get('promo_title', result.get('PROMO_TITLE', '')),
                                    'categories': result.get('CATEGORIES', [])
                                }
                                product_data.append(product_info)
            except Exception as e:
                pass  # Continue processing other messages
    
    # 🤖 AI-DRIVEN SUGGESTIONS: Generate intelligent suggestions for product search results
    # Controlled by SHOW_SUGGESTIONS env variable (set to 'true' to enable)
    ai_suggestions = None
    show_suggestions = os.getenv('SHOW_SUGGESTIONS', 'true').strip().lower() == 'true'
    if show_suggestions and product_data and is_product_search:
        print(f"🤖 Triggering AI-driven search suggestions for {len(product_data)} products")
        try:
            ai_suggestions = generate_ai_search_suggestions(
                query=query,
                products_data=product_data,
                customer_id=customer_id
            )
            print(f"✅ AI Suggestions generated: {ai_suggestions}")
        except Exception as e:
            print(f"⚠️ AI suggestion generation failed: {e}")
            ai_suggestions = None
    elif not show_suggestions:
        print("ℹ️ AI suggestions disabled via SHOW_SUGGESTIONS=false")
    
    if not memory.load(session_id):
        memory.save(session_id,[SystemMessage(
        content="You are receiving this chat history from previous conversation, use this as context")])
    
    # 🧠 ENHANCED: Store conversation in memory; store product data in session cache (NOT in LLM memory)
    memory_messages = [HumanMessage(query), response["messages"][-1]]
    
    # If we found product data, store it in the session product cache (outside LangGraph memory)
    # This prevents PRODUCT_CONTEXT_DATA from leaking into LLM conversation history
    # which was causing the LLM to skip find_accessories tool calls
    if product_data:
        _session_products[session_id] = product_data
        print(f"✅ Stored {len(product_data)} products in session cache: {session_id}")
    
    memory.save(session_id, memory_messages)
    
    # [Process order data for order-related tools]
    for i, message in enumerate(response["messages"]):
        # Check for ToolMessage responses from order-related tools
        if hasattr(message, 'name') and message.name in ['get_order_history', 'query_orders', 'get_orders_by_status']:
            try:
                tool_result = message.content
                if isinstance(tool_result, str):
                    try:
                        import ast
                        tool_result = ast.literal_eval(tool_result)
                    except (ValueError, SyntaxError):
                        continue
                if isinstance(tool_result, dict):
                    if 'results' in tool_result and tool_result['results']:
                        for result in tool_result['results']:
                            if 'ORDER_ID' in result:
                                order_data.append({
                                    'order_id': result.get('ORDER_ID', ''),
                                    'order_date': result.get('ORDER_DATE', ''),
                                    'product_name': result.get('PRODUCT_NAME', ''),
                                    'total_price': float(result.get('TOTAL_PRICE', 0)) if result.get('TOTAL_PRICE') else 0.0,
                                    'order_status': result.get('ORDER_STATUS', ''),
                                    'product_id': result.get('PRODUCT_ID', ''),
                                    'image_url': result.get('IMAGE_URL', '')
                                })
            except Exception:
                pass
    
    # If we found cart data, return structured cart response
    if cart_data:
        return cart_data
    
    # If we found conversational data, return the AI response
    if conversational_data:
        return conversational_data.get('ai_response', 'Hello! How can I help you today?')
    
    # 🎯 CRITICAL FIX: Use tool's ai_response instead of AI's verbose message
    # The tool provides clean, concise response. The AI's final message may contain verbose details.
    final_ai_response = tool_ai_response if tool_ai_response else response_content
    
    # 🧹 SAFETY: Strip any leaked PRODUCT_CONTEXT_DATA or STRUCTURED_PRODUCTS blocks from response text
    import re as _re
    if final_ai_response:
        # Remove everything from PRODUCT_CONTEXT_DATA: onwards (it's raw Python/JSON data)
        final_ai_response = _re.sub(r'\s*PRODUCT_CONTEXT_DATA:.*', '', final_ai_response, flags=_re.DOTALL).strip()
        # Remove [STRUCTURED_PRODUCTS: ...] blocks
        final_ai_response = _re.sub(r'\s*\[STRUCTURED_PRODUCTS:.*?\]\s*', ' ', final_ai_response, flags=_re.DOTALL).strip()
    
    if order_data:
        return {
            'response_type': 'order_history' if len(order_data) > 1 else 'order',
            'ai_response': final_ai_response,
            'orders_data': order_data,
            'order_data': order_data[0] if len(order_data) == 1 else None
        }
    
    # If we found products, return structured response
    if product_data:
        # For search operations with single result, still show as list (small card)
        # Only show full product details for specific product detail requests
        if len(product_data) == 1 and not is_product_search:
            # This is a specific product details request - show full details
            response_dict = {
                'response_type': 'product',
                'ai_response': final_ai_response,
                'products_data': product_data,
                'product_data': product_data[0],
                'cross_sell_products': cross_sell_data  # 🔗 Include cross-sell products ONLY for product details
            }
        else:
            # This is a search result or multiple products - show as cards (NO cross-sell for search)
            response_dict = {
                'response_type': 'products_list',
                'ai_response': final_ai_response,
                'products_data': product_data,
                'product_data': product_data[0] if len(product_data) == 1 else None
            }
        
        # 🤖 ADD AI SUGGESTIONS: Include intelligent suggestions if available
        if ai_suggestions and ai_suggestions.get('has_suggestions'):
            response_dict['ai_suggestions'] = ai_suggestions
            print(f"✅ Added {len(ai_suggestions.get('suggestions', []))} AI suggestions to response")
        
        return response_dict
    
    # Check if response is empty or just whitespace
    if not response_content or not response_content.strip():
        # Provide helpful fallback message
        response_content = "I apologize, but I couldn't find any products matching your search criteria. Could you please try:\n\n• Using different keywords\n• Checking the spelling\n• Broadening your search terms\n• Asking about a specific category like 'jackets', 'shoes', or 'tshirts'\n\nHow else can I help you today?"
    
    # Default to regular response
    return response_content