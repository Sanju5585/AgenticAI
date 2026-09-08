from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, render_template_string, send_file, Response
from flask_cors import CORS
# from gen_ai_hub.proxy.langchain.init_models import init_llm
from agent import process_query
# from concurrent.futures import ThreadPoolExecutor  # No longer needed
#from ecom_llm import sap_generative_ai_llm as llm
from ecom_llm import google_generative_ai_llm as llm
from content_moderation import check_content  # Content moderation
import os
import uuid
import json
import requests
import time
import urllib3
from datetime import timedelta
from werkzeug.utils import secure_filename
from visual_search import search_by_image
from urllib.parse import unquote, urlparse, parse_qs
import io


app = Flask(__name__)
CORS(app) # Enable CORS for all routes and origins

# Configure session
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here-change-in-production')
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)  # Session lasts 2 hours

# Simple in-memory session storage as backup (persist across requests within same server run)
persistent_sessions = {}

# PayPal MCP Server Configuration
PAYPAL_MCP_HOST = os.getenv('PAYPAL_MCP_HOST', 'localhost')
PAYPAL_MCP_PORT = os.getenv('PAYPAL_MCP_PORT', '8000')
PAYPAL_MCP_SERVER_URL = f"http://{PAYPAL_MCP_HOST}:{PAYPAL_MCP_PORT}"

# Database Connection Helper with Retry Logic
def get_db_connection(max_retries=3, retry_delay=1):
    """
    Get a database connection with retry mechanism.
    Handles connection errors gracefully with exponential backoff.
    """
    from agent import hana_connect
    
    for attempt in range(max_retries):
        try:
            print(f"🔄 Database connection attempt {attempt + 1}/{max_retries}")
            conn = hana_connect()
            print(f"✅ Database connection established")
            return conn
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Connection error on attempt {attempt + 1}: {error_msg}")
            
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                print(f"⏳ Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"💥 All connection attempts failed")
                raise

# Home route: Render the search page
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/best-selling-products", methods=["GET"])
def api_best_selling_products():
    """
    API endpoint to get best-selling products for homepage carousel.
    For logged-in users, returns personalized recommendations based on order history.
    For anonymous users, returns general best-selling products.
    """
    try:
        customer_id = request.args.get("customer_id", "")
        page_size = request.args.get("pageSize", 8, type=int)
        
        # If user is logged in, provide personalized recommendations
        if customer_id:
            print(f"🎯 Loading personalized products for customer: {customer_id}")
            return get_personalized_products(customer_id, page_size)
        
        # Anonymous user - show general best sellers from HANA database
        from agent import hana_connect
        from promotion_helper import get_active_promotion, calculate_discounted_price
        
        conn = hana_connect()
        cursor = conn.cursor()
        
        # Get top products from HANA (prioritize those with images and reasonable prices)
        query = f"""
            SELECT PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, IMAGE_URL
            FROM SAP_PRODUCTS_COMMERCE_2211_V2
            WHERE PRICE > 0 AND IMAGE_URL IS NOT NULL
            ORDER BY PRICE DESC
            LIMIT {page_size}
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        products = []
        for row in rows:
            product_id = str(row[0]).strip() if row[0] else ""
            product_name = row[1] if row[1] else ""
            summary = row[2] if row[2] else ""
            original_price = float(row[3]) if row[3] else 0.0
            image_url = row[4] if row[4] else ""
            
            # Check for active promotion
            promotion = get_active_promotion(product_id)
            has_promotion = promotion is not None
            
            if has_promotion:
                discount_percent = float(promotion.get('discount_percent', 0))
                discounted_price = calculate_discounted_price(original_price, discount_percent)
                price = discounted_price
            else:
                discount_percent = 0
                discounted_price = original_price
                price = original_price
            
            products.append({
                "product_id": product_id,
                "product_name": product_name,
                "summary": summary,
                "price": price,
                "original_price": original_price,
                "discount_percent": discount_percent,
                "discounted_price": discounted_price,
                "has_promotion": has_promotion,
                "promo_title": promotion.get('promo_title', '') if promotion else '',
                "image_url": image_url,
                "rating": None,
                "url": ""
            })
        
        return jsonify({
            "products": products,
            "source": "hana_db",
            "total": len(products),
            "personalized": False
        })
        
    except Exception as e:
        error_response = {"error": str(e)}
        print(f"Best selling products API error: {error_response}")
        return jsonify(error_response), 500

@app.route("/api/cross-sell-products", methods=["GET"])
def api_cross_sell_products():
    """
    API endpoint to get cross-sell products for a given product.
    Returns associated products (cross-sell, upsell, related) from HANA database.
    """
    try:
        product_id = request.args.get("product_id", "").strip()
        limit = request.args.get("limit", 4, type=int)
        relationship_type = request.args.get("type", "").strip()  # Optional filter
        
        if not product_id:
            return jsonify({"error": "product_id is required"}), 400
        
        from agent import hana_connect
        from promotion_helper import get_active_promotion, calculate_discounted_price
        
        conn = hana_connect()
        cursor = conn.cursor()
        
        # Build query based on filters
        query = """
            SELECT p.PRODUCT_ID, p.PRODUCT_NAME, p.SUMMARY, p.PRICE, p.IMAGE_URL,
                   cs.RELATIONSHIP_TYPE, cs.PRIORITY
            FROM SAP_PRODUCT_CROSS_SELL_V2 cs
            JOIN SAP_PRODUCTS_COMMERCE_2211_V2 p 
                ON TRIM(cs.CROSS_SELL_PRODUCT_ID) = TRIM(p.PRODUCT_ID)
            WHERE TRIM(cs.SOURCE_PRODUCT_ID) = ?
        """
        
        params = [product_id]
        
        if relationship_type:
            query += " AND cs.RELATIONSHIP_TYPE = ?"
            params.append(relationship_type)
        
        query += f" ORDER BY cs.PRIORITY LIMIT {limit}"
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        products = []
        for row in rows:
            cross_sell_product_id = str(row[0]).strip() if row[0] else ""
            product_name = row[1] if row[1] else ""
            summary = row[2] if row[2] else ""
            original_price = float(row[3]) if row[3] else 0.0
            image_url = row[4] if row[4] else ""
            rel_type = row[5] if row[5] else "cross-sell"
            priority = row[6] if row[6] else 1
            
            # Check for active promotion
            promotion = get_active_promotion(cross_sell_product_id)
            has_promotion = promotion is not None
            
            if has_promotion:
                discount_percent = float(promotion.get('discount_percent', 0))
                discounted_price = calculate_discounted_price(original_price, discount_percent)
                price = discounted_price
            else:
                discount_percent = 0
                discounted_price = original_price
                price = original_price
            
            products.append({
                "product_id": cross_sell_product_id,
                "product_name": product_name,
                "summary": summary,
                "price": price,
                "original_price": original_price,
                "discount_percent": discount_percent,
                "discounted_price": discounted_price,
                "has_promotion": has_promotion,
                "promo_title": promotion.get('promo_title', '') if promotion else '',
                "image_url": image_url,
                "relationship_type": rel_type,
                "priority": priority
            })
        
        return jsonify({
            "products": products,
            "source_product_id": product_id,
            "total": len(products),
            "relationship_filter": relationship_type if relationship_type else "all"
        })
        
    except Exception as e:
        error_response = {"error": str(e)}
        print(f"Cross-sell products API error: {error_response}")
        return jsonify(error_response), 500

@app.route("/api/outfit-builder-a2ui", methods=["POST"])
def api_outfit_builder_a2ui():
    """
    Triggered when a product is added to cart.
    Looks up category-based outfit rules from OUTFIT_COMPLETE_LOOK table,
    fetches complement products, and returns them.
    Also tries to push via A2UI WebSocket if server is available.
    """
    try:
        data = request.get_json()
        product_id   = (data.get("product_id",   "") or "").strip()
        product_name = (data.get("product_name", "") or "").strip()
        session_id   = (data.get("session_id",   "") or "").strip() or "default_session"

        if not product_id:
            return jsonify({"error": "product_id is required"}), 400

        print(f"\n{'='*70}")
        print(f"👗 Outfit Builder — product: {product_id} ({product_name}), session: {session_id}")
        print(f"{'='*70}\n")

        # Query DB for outfit sections (always, regardless of A2UI)
        from modules.outfit_builder_a2ui import get_outfit_looks
        from agent import hana_connect
        conn = hana_connect()
        cursor = conn.cursor()
        sections = get_outfit_looks(product_id, product_name, cursor)
        cursor.close()
        conn.close()

        print(f"📊 Outfit DB result: {len(sections)} sections found")

        # Optionally try to push via A2UI (best-effort, don't fail if unavailable)
        via_a2ui = False
        try:
            a2ui_check = requests.get("http://localhost:8020/", timeout=1)
            if a2ui_check.status_code < 500:
                from modules.outfit_builder_a2ui import load_outfit_sync
                a2ui_result = load_outfit_sync(product_id, product_name, session_id)
                via_a2ui = a2ui_result.get("success", False)
                print(f"✅ A2UI push: {via_a2ui}")
        except Exception as a2ui_err:
            print(f"⚠️ A2UI push skipped (server not available): {a2ui_err}")

        return jsonify({
            "success":  len(sections) > 0,
            "via_a2ui": via_a2ui,
            "sections": len(sections),
            "message":  f"Found {len(sections)} outfit sections",
            "data":     sections,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Outfit builder error: {str(e)}"}), 500


@app.route("/api/crosssell-a2ui", methods=["POST"])
def api_crosssell_a2ui():
    """
    API endpoint to trigger cross-sell product display via A2UI Protocol.
    Sends real-time UI updates through WebSocket connection.
    """
    try:
        data = request.get_json()
        product_id = data.get("product_id", "").strip()
        session_id = data.get("session_id", "").strip()
        
        if not product_id:
            return jsonify({"error": "product_id is required"}), 400
        if not session_id:
            return jsonify({"error": "session_id is required"}), 400
        
        print(f"\n{'='*80}")
        print(f"🔗 Cross-Sell A2UI Request")
        print(f"   Product ID: {product_id}")
        print(f"   Session ID: {session_id}")
        print(f"{'='*80}\n")
        
        # Check if A2UI server is running
        import requests
        try:
            a2ui_check = requests.get("http://localhost:8020/", timeout=1)
            print(f"✅ A2UI Server is running (Status: {a2ui_check.status_code})")
        except:
            print(f"⚠️ WARNING: A2UI Server may not be running on port 8020")
            return jsonify({
                "success": False,
                "error": "A2UI Server is not reachable. Please ensure it's running."
            }), 503
        
        # Import the cross-sell A2UI module
        from modules.product_crosssell_a2ui import load_crosssell_sync
        
        # Load and send cross-sell products via A2UI
        result = load_crosssell_sync(product_id, session_id)
        
        print(f"\n📊 Cross-Sell A2UI Result:")
        print(f"   Success: {result.get('success')}")
        print(f"   Count: {result.get('count', 0)}")
        if not result.get('success'):
            print(f"   Error: {result.get('error')}")
        print(f"{'='*80}\n")
        
        if result.get('success'):
            return jsonify({
                "success": True,
                "via_a2ui": True,
                "count": result.get('count', 0),
                "message": "Cross-sell products sent via A2UI",
                "products": result.get('products', [])
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get('error', 'Unknown error')
            }), 500
        
    except Exception as e:
        error_msg = f"Cross-sell A2UI error: {str(e)}"
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": error_msg}), 500

@app.route("/api/test-crosssell-a2ui", methods=["GET"])
def test_crosssell_a2ui():
    """
    Test endpoint for cross-sell A2UI - uses a known product with cross-sell items
    """
    test_product_id = "300441142"  # Trench Coat with known cross-sell products
    test_session_id = "test_session_" + str(int(time.time()))
    
    print(f"\n{'='*80}")
    print(f"🧪 TEST: Cross-Sell A2UI")
    print(f"   Product ID: {test_product_id}")
    print(f"   Session ID: {test_session_id}")
    print(f"{'='*80}\n")
    
    try:
        from modules.product_crosssell_a2ui import load_crosssell_sync
        result = load_crosssell_sync(test_product_id, test_session_id)
        
        return jsonify({
            "test": "Cross-Sell A2UI Test",
            "result": result,
            "instructions": "Check browser console for WebSocket messages"
        })
    except Exception as e:
        return jsonify({
            "test": "Cross-Sell A2UI Test",
            "error": str(e),
            "instructions": "Check Flask console for error details"
        }), 500

@app.route("/api/visual-search", methods=["POST"])
def api_visual_search():
    try:
        if "image" not in request.files:
            return jsonify({
                "success": False,
                "response_type": "visual_search",
                "error": "No image file received. Please attach an image and try again."
            }), 400

        image_file = request.files["image"]
        if image_file is None or image_file.filename == "":
            return jsonify({
                "success": False,
                "response_type": "visual_search",
                "error": "Image upload failed. Please choose a valid file."
            }), 400

        image_bytes = image_file.read()
        if not image_bytes:
            return jsonify({
                "success": False,
                "response_type": "visual_search",
                "error": "Uploaded file is empty. Please try another image."
            }), 400

        safe_name = secure_filename(image_file.filename) or "upload.jpg"

        limit_raw = request.form.get("limit", 6)
        try:
            limit_value = int(limit_raw)
        except (TypeError, ValueError):
            limit_value = 6
        limit_value = max(1, min(limit_value, 9))

        print(f"🖼️ Visual search request received (limit={limit_value}) for file: {safe_name}")

        result = search_by_image(image_bytes, safe_name, limit=limit_value)

        response_payload = {
            "success": result.get("success", False),
            "response_type": "visual_search",
            "analysis": result.get("analysis", {}),
            "features": result.get("features", {}),
            "products_data": result.get("results", []),
            "image_cache": result.get("image_cache"),
            "query_generated": result.get("query_generated"),
            "count": result.get("count", len(result.get("results", [])))
        }

        if response_payload["success"]:
            analysis = response_payload.get("analysis") or {}
            product_type = analysis.get("product_type") if isinstance(analysis.get("product_type"), str) else ""
            category = analysis.get("category") if isinstance(analysis.get("category"), str) else ""
            count = response_payload.get("count", 0)

            summary_parts = []
            if product_type and category:
                summary_parts.append(f"I looked for {product_type} items in the {category.lower()} category.")
            elif product_type:
                summary_parts.append(f"I looked for {product_type} items in your catalog.")
            elif category:
                summary_parts.append(f"I focused on the {category.lower()} category for matches.")
            else:
                summary_parts.append("I analyzed your photo and searched for similar catalog items.")

            if count:
                summary_parts.append(f"Found {count} similar product{'s' if count != 1 else ''}.")
            else:
                summary_parts.append("I couldn't find direct matches, but here are some related suggestions.")

            response_payload["ai_response"] = " ".join(summary_parts)
            return jsonify(response_payload)

        response_payload["error"] = result.get("error", "Unable to process the uploaded image.")
        return jsonify(response_payload), 400

    except Exception as exc:
        print(f"Visual search API error: {exc}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "response_type": "visual_search",
            "error": "Unexpected error while running visual search. Please retry shortly."
        }), 500

def get_personalized_products(customer_id: str, page_size: int = 8):
    """
    Get AI-powered personalized product recommendations by calling the agent tool.
    """
    try:
        print(f"🎯 Getting personalized products for: {customer_id}")
        
        # Import the tool from agent
        from agent import get_personalized_recommendations
        
        # Call the tool with customer email
        result = get_personalized_recommendations.func(customer_id)
        
        # Check if we got results
        if result.get('error'):
            print(f"❌ Error from recommendation tool: {result['error']}")
            # Fallback to trending products from HANA
            from agent import hana_connect
            from promotion_helper import get_active_promotion, calculate_discounted_price
            
            conn = hana_connect()
            cursor = conn.cursor()
            
            query = f"""
                SELECT PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, IMAGE_URL
                FROM SAP_PRODUCTS_COMMERCE_2211_V2
                WHERE PRICE > 0 AND IMAGE_URL IS NOT NULL
                ORDER BY PRICE DESC
                LIMIT {page_size}
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            
            products = []
            for row in rows:
                product_id = str(row[0]).strip() if row[0] else ""
                product_name = row[1] if row[1] else ""
                summary = row[2] if row[2] else ""
                original_price = float(row[3]) if row[3] else 0.0
                image_url = row[4] if row[4] else ""
                
                # Check for active promotion
                promotion = get_active_promotion(product_id)
                has_promotion = promotion is not None
                
                if has_promotion:
                    discount_percent = float(promotion.get('discount_percent', 0))
                    discounted_price = calculate_discounted_price(original_price, discount_percent)
                    price = discounted_price
                else:
                    discount_percent = 0
                    discounted_price = original_price
                    price = original_price
                
                products.append({
                    "product_id": product_id,
                    "product_name": product_name,
                    "summary": summary,
                    "price": price,
                    "original_price": original_price,
                    "discount_percent": discount_percent,
                    "discounted_price": discounted_price,
                    "has_promotion": has_promotion,
                    "promo_title": promotion.get('promo_title', '') if promotion else '',
                    "image_url": image_url,
                    "rating": None,
                    "url": ""
                })
            return jsonify({
                "products": products,
                "source": "hana_trending_fallback",
                "total": len(products),
                "personalized": False
            })
        
        results = result.get('results', [])
        
        # Transform to frontend format
        from promotion_helper import get_active_promotion, calculate_discounted_price
        products = []
        for product in results:
            product_id = product.get('PRODUCT_ID', '')
            original_price = float(product.get('PRICE', 0.0))
            
            # Check for active promotion
            promotion = get_active_promotion(product_id)
            has_promotion = promotion is not None
            
            if has_promotion:
                discount_percent = float(promotion.get('discount_percent', 0))
                discounted_price = calculate_discounted_price(original_price, discount_percent)
                price = discounted_price
            else:
                discount_percent = 0
                discounted_price = original_price
                price = original_price
            
            products.append({
                "product_id": product_id,
                "product_name": product.get('PRODUCT_NAME', ''),
                "summary": product.get('SUMMARY', ''),
                "price": price,
                "original_price": original_price,
                "discount_percent": discount_percent,
                "discounted_price": discounted_price,
                "has_promotion": has_promotion,
                "promo_title": promotion.get('promo_title', '') if promotion else '',
                "image_url": product.get('IMAGE_URL', ''),
                "rating": None,
                "url": ""
            })
        
        print(f"✅ Returning {len(products)} personalized products")
        
        return jsonify({
            "products": products,
            "source": "ai_personalized_recommendations",
            "total": len(products),
            "personalized": result.get('personalized', True),
            "categories_used": result.get('categories_used', []),
            "ai_message": result.get('ai_response', '')
        })
        
    except Exception as e:
        print(f"❌ Error in get_personalized_products: {e}")
        import traceback
        traceback.print_exc()
        
        # Final fallback
        try:
            from tools.hybris_occ import get_best_selling_products
            from promotion_helper import get_active_promotion, calculate_discounted_price
            trending_result = get_best_selling_products(page_size)
            products = []
            for product in trending_result.get("results", []):
                product_id = product.get("id", "")
                original_price = product.get("price", 0.0)
                
                # Check for active promotion
                promotion = get_active_promotion(product_id)
                has_promotion = promotion is not None
                
                if has_promotion:
                    discount_percent = promotion.get('discount_percent', 0)
                    discounted_price = calculate_discounted_price(original_price, discount_percent)
                    price = discounted_price
                else:
                    discount_percent = 0
                    discounted_price = original_price
                    price = original_price
                
                products.append({
                    "product_id": product_id,
                    "product_name": product.get("name", ""),
                    "summary": product.get("description", ""),
                    "price": price,
                    "original_price": original_price,
                    "discount_percent": discount_percent,
                    "discounted_price": discounted_price,
                    "has_promotion": has_promotion,
                    "promo_title": promotion.get('promo_title', '') if promotion else '',
                    "image_url": product.get("image", ""),
                    "rating": product.get("averageRating"),
                    "url": product.get("url", "")
                })
            return jsonify({
                "products": products,
                "source": "error_fallback",
                "total": len(products),
                "personalized": False
            })
        except:
            return jsonify({"error": str(e)}), 500

@app.route("/api/login", methods=["POST"])
def api_login():
    """
    API endpoint to validate user login credentials.
    Returns user info along with last 5 orders for personalized greeting.
    Implements connection retry mechanism for database errors.
    """
    conn = None
    cursor = None
    
    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        
        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400
        
        # Get database connection with retry logic
        try:
            conn = get_db_connection(max_retries=3, retry_delay=1)
            cursor = conn.cursor()
        except Exception as conn_error:
            print(f"💥 Failed to establish database connection: {conn_error}")
            return jsonify({
                "error": "Unable to connect to the database. Please try again in a moment.",
                "technical_details": "The database connection is currently unavailable."
            }), 503
        
        # Check if email exists in customer table (with persona fields)
        try:
            query = """SELECT CUSTOMER_NAME, CUSTOMER_ID,
                              STYLE_PREFERENCE, FAVORITE_CATEGORIES, BUDGET_RANGE,
                              SHOPPING_PERSONA, OCCASION_PREFERENCE, COLOR_PREFERENCE,
                              GENDER, AGE
                       FROM SAP_CUSTOMER_COMMERCE_2211_V2
                       WHERE LOWER(CUSTOMER_ID) = ?"""
            cursor.execute(query, (email,))
        except Exception:
            query = "SELECT CUSTOMER_NAME, CUSTOMER_ID FROM SAP_CUSTOMER_COMMERCE_2211_V2 WHERE LOWER(CUSTOMER_ID) = ?"
            cursor.execute(query, (email,))
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            conn.close()
            return jsonify({"error": "Email not found in our system. Please check your email address."}), 401
        
        customer_name = result[0]
        customer_id = result[1]
        persona = {}
        if len(result) > 2:
            persona = {
                "style_preference":  str(result[2] or ""),
                "favorite_categories": str(result[3] or ""),
                "budget_range":      str(result[4] or ""),
                "shopping_persona":  str(result[5] or ""),
                "occasion_preference": str(result[6] or ""),
                "color_preference":  str(result[7] or ""),
                "gender":            str(result[8] or ""),
                "age":               str(result[9] or ""),
            }
        
        # Get last 5 orders for welcome message
        orders_query = """
            SELECT o.ORDER_ID, o.ORDER_DATE, o.ORDER_STATUS, o.PRODUCT_NAME, 
                   o.TOTAL_PRICE, o.PRODUCT_ID, p.IMAGE_URL
            FROM SAP_ORDERS_COMMERCE_2211_V2 o
            LEFT JOIN SAP_PRODUCTS_COMMERCE_2211_V2 p ON TRIM(o.PRODUCT_ID) = TRIM(p.PRODUCT_ID)
            WHERE o.CUSTOMER_ID = ?
            ORDER BY o.ORDER_DATE DESC
            LIMIT 5
        """
        cursor.execute(orders_query, (customer_id,))
        orders = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        # Format orders
        recent_orders = []
        for order in orders:
            recent_orders.append({
                "order_id": order[0],
                "order_date": order[1],
                "order_status": order[2],
                "product_name": order[3],
                "total_price": float(order[4]) if order[4] else 0.0,
                "product_id": order[5],
                "image_url": order[6] or ""
            })
        
        print(f"✅ Login successful for {customer_name}")
        return jsonify({
            "success": True,
            "message": f"Welcome back, {customer_name}!",
            "customer_name": customer_name,
            "customer_email": customer_id,
            "recent_orders": recent_orders,
            "total_orders": len(recent_orders),
            "persona": persona
        })
            
    except Exception as e:
        # Clean up resources
        try:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        except:
            pass
            
        error_response = {"error": f"Login failed: {str(e)}"}
        print(f"❌ Login API error: {error_response}")
        import traceback
        traceback.print_exc()
        return jsonify(error_response), 500

@app.route("/api/add-to-cart", methods=["POST"])
def api_add_to_cart():
    """
    API endpoint to add products to cart using browser session.
    """
    try:
        data = request.get_json()
        product_id = data.get("product_id", "")
        quantity = data.get("quantity", 1)
        customer_id = data.get("customer_id", "")
        
        if not product_id:
            return jsonify({"error": "Product ID is required"}), 400
        
        if not customer_id:
            return jsonify({"error": "Customer email is required"}), 400
        
        # Call the add_to_cart tool with the correct format
        from agent import add_to_cart
        
        # Format the query as expected by the add_to_cart tool
        tool_query = f"product_id:{product_id},quantity:{quantity}"
        print(f"DEBUG: Calling add_to_cart tool with query: {tool_query}")
        
        # Call the tool using .invoke() method since it's a decorated @tool
        response = add_to_cart.invoke({"query": tool_query})
        
        print(f"DEBUG: add_to_cart response: {response}")
        
        return jsonify(response)
        
    except Exception as e:
        error_response = {"error": str(e)}
        print(f"Add to cart API error: {error_response}")
        return jsonify(error_response), 500

@app.route("/api/query", methods=["POST"])
def api_query():
    """
    API endpoint to process user queries.
    """
    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({"error": "Invalid or empty request body"}), 400
        query = data.get("query", "")
        cart_id=data.get("cart_id", "")
        customer_id=data.get("customer_id", "")
        conversation_context = data.get("conversation_context", None)
        product_context_ids = data.get("product_context_ids", [])
        product_context_names = data.get("product_context_names", [])
        token= request.headers.get('Authorization')
        if not query:
            return jsonify({"error": "Query is required"}), 400

        # 🛡️ SECURITY: Content moderation check
        is_blocked, block_reason, block_message = check_content(query)
        if is_blocked:
            print(f"🛡️ BLOCKED CONTENT - Reason: {block_reason}, Query: {query}")
            return jsonify({
                "response": block_message,
                "blocked": True,
                "reason": block_reason,
                "show_products": False
            }), 200  # Return 200 to avoid error handling on frontend

        if customer_id:
            query = f"Customer ID: {customer_id}. {query}"
        
        # 🧠 ENHANCED: Include conversation context in query processing
        if conversation_context:
            print(f"🧠 Received conversation context: {conversation_context}")
            # Add context to query for the agent to use
            context_info = f" [CONVERSATION_CONTEXT: {conversation_context}]"
            query = query + context_info
            print(f"🧠 Enhanced query with conversation context: {query[:200]}...")
        
        # 🧠 SIMPLE BACKUP: Also add simple product context
        if product_context_ids or product_context_names:
            print(f"🧠 Simple product context - IDs: {product_context_ids}, Names: {product_context_names}")
            # Use more natural language format to avoid SQL confusion
            context_info = ""
            if product_context_names:
                context_info += f" Context: User previously searched for these products: {', '.join(product_context_names)}."
            if product_context_ids:
                context_info += f" Product IDs: {', '.join(product_context_ids)}."
            
            query = query + context_info
            print(f"🧠 Final enhanced query: {query[:200]}...")
        
        # Process the query directly (it now returns structured responses)
        response = process_query(customer_id, cart_id, query, token)

        if isinstance(response, dict):
            return jsonify(response)
        else:
            return jsonify({"response": response})
    except Exception as e:
        error_response = {"error": str(e)}
        print(f"API error: {error_response}")  # Debugging output
        return jsonify(error_response), 500

@app.route("/api/cleanup-sessions", methods=["POST"])
def api_cleanup_sessions():
    """
    API endpoint to cleanup old sessions (optional maintenance endpoint)
    """
    try:
        from datetime import datetime, timedelta
        
        # Clean up sessions older than 2 hours
        current_time = datetime.now()
        cleaned_count = 0
        
        sessions_to_remove = []
        for session_id, session_data in persistent_sessions.items():
            timestamp = session_data.get('timestamp')
            if timestamp:
                try:
                    # Try to parse timestamp
                    session_time = datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else datetime.now()
                    if current_time - session_time > timedelta(hours=2):
                        sessions_to_remove.append(session_id)
                        cleaned_count += 1
                except:
                    pass
        
        for session_id in sessions_to_remove:
            persistent_sessions.pop(session_id, None)
        
        return jsonify({
            "success": True,
            "cleaned_sessions": cleaned_count,
            "remaining_sessions": len(persistent_sessions)
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/checkout", methods=["POST"])
def api_checkout():
    """
    API endpoint to handle PayPal checkout integration.
    NEW: Opens PayPal in new tab and uses file-based polling for status updates
    """
    try:
        from payment_status import create_payment_status_file
        from datetime import datetime
        
        data = request.get_json()
        customer_id = data.get("customer_id")
        cart_items = data.get("cart_items")
        
        if not customer_id:
            return jsonify({"error": "Customer ID is required"}), 400
            
        if not cart_items or len(cart_items) == 0:
            return jsonify({"error": "Cart is empty"}), 400
        
        # Calculate total amount
        total_amount = sum(item.get('price', 0) * item.get('quantity', 1) for item in cart_items)
        
        # Generate unique session ID for this payment
        session_id = str(uuid.uuid4())
        
        # Prepare payment data
        payment_data = {
            'customer_id': customer_id,
            'cart_items': cart_items,
            'total_amount': total_amount,
            'chat_history': data.get('chat_history', []),
            'conversation_context': data.get('conversation_context', {}),
            'timestamp': datetime.now().isoformat(),
            'session_id': session_id
        }
        
        print(f"✨ CHECKOUT: Creating payment session {session_id} for customer {customer_id}")
        
        # Create payment status file (status: pending)
        status_file = create_payment_status_file(session_id, payment_data)
        print(f"📝 Payment status file created: {status_file}")
        
        # Prepare PayPal payment request
        paypal_request = {
            "amount": str(total_amount),
            "currency": "GBP",
            "description": f"Order for {len(cart_items)} items from AI Shopping Assistant",
            "return_url": f"{request.host_url}paypal/callback/success?session_id={session_id}",
            "cancel_url": f"{request.host_url}paypal/callback/cancel?session_id={session_id}"
        }
        
        # Call PayPal MCP Server with improved error handling
        try:
            print(f"🔗 Attempting to connect to PayPal MCP Server at {PAYPAL_MCP_SERVER_URL}")
            
            # First, check if the server is running
            try:
                health_check = requests.get(f"{PAYPAL_MCP_SERVER_URL}/health", timeout=5)
                print(f"✅ PayPal MCP Server is running (status: {health_check.status_code})")
            except requests.exceptions.RequestException as health_error:
                print(f"❌ PayPal MCP Server health check failed: {health_error}")
                return jsonify({
                    "error": "PayPal MCP Server is not running",
                    "details": "Please start the PayPal server using 'python run_all_servers.py'",
                    "technical_error": str(health_error)
                }), 503
            
            # Make the payment request
            mcp_response = requests.post(
                f"{PAYPAL_MCP_SERVER_URL}/mcp/tools/invoke/paypal_payment",
                json=paypal_request,
                timeout=30
            )
            
            print(f"📥 MCP Server response status: {mcp_response.status_code}")
            
            if mcp_response.status_code == 200:
                paypal_data = mcp_response.json()
                print(f"💳 PayPal response: {paypal_data.get('status', 'unknown')}")
                
                if paypal_data.get("status") == "success":
                    return jsonify({
                        "success": True,
                        "payment_id": paypal_data.get("payment_id"),
                        "approval_url": paypal_data.get("approval_url"),
                        "session_id": session_id,
                        "message": "Opening PayPal in new tab...",
                        "polling_enabled": True  # Signal frontend to start polling
                    })
                else:
                    return jsonify({
                        "error": f"PayPal error: {paypal_data.get('details', 'Unknown error')}"
                    }), 400
            else:
                error_detail = mcp_response.text if hasattr(mcp_response, 'text') else 'No details available'
                print(f"❌ MCP Server error response: {error_detail}")
                return jsonify({
                    "error": f"MCP Server error: {mcp_response.status_code}",
                    "details": error_detail
                }), 500
                
        except requests.exceptions.ConnectionError as ce:
            print(f"❌ Connection Error: PayPal MCP Server not reachable - {ce}")
            return jsonify({
                "error": "Cannot connect to PayPal MCP Server",
                "details": "The PayPal server is not running. Please start all servers using 'python run_all_servers.py'",
                "technical_error": str(ce)
            }), 503
            
        except requests.exceptions.Timeout as te:
            print(f"❌ Timeout Error: PayPal MCP Server took too long to respond - {te}")
            return jsonify({
                "error": "PayPal MCP Server timeout",
                "details": "The server is taking too long to respond. Please try again.",
                "technical_error": str(te)
            }), 504
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Request Exception: {type(e).__name__} - {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({
                "error": f"Failed to connect to PayPal MCP Server",
                "details": "Please ensure the PayPal server is running using 'python run_all_servers.py'",
                "technical_error": f"{type(e).__name__}: {str(e)}"
            }), 503
        
    except Exception as e:
        error_response = {"error": str(e)}
        print(f"Checkout API error: {error_response}")
        return jsonify(error_response), 500

@app.route("/api/restore-session", methods=["GET"])
def api_restore_session():
    """
    API endpoint to restore session data after PayPal return
    """
    try:
        restoration_key = request.args.get('restoration_key')
        
        print(f"Session restoration requested with key: {restoration_key}")
        
        if not restoration_key:
            return jsonify({"error": "No restoration key provided"}), 400
        
        # Get restoration data from session (using fixed key)
        if restoration_key == 'restoration_data':
            restoration_data = session.get('restoration_data')
        else:
            # Fallback to old method
            restoration_data = session.get('restoration_data')
        
        print(f"Found restoration data: {bool(restoration_data)}")
        
        if not restoration_data:
            print("No restoration data found in session")
            return jsonify({"error": "No restoration data found"}), 404
        
        # Clear the restoration data after retrieving it
        session.pop('restoration_data', None)
        
        print(f"Returning restoration data with {len(restoration_data.get('chat_history', []))} messages")
        
        return jsonify({
            "success": True,
            "restoration_data": restoration_data
        })
        
    except Exception as e:
        print(f"Session restoration error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Failed to restore session"}), 500

@app.route("/paypal/callback/success")
def paypal_callback_success():
    """
    PayPal success callback - Updates temp file with success status
    This page auto-closes after updating the status
    """
    try:
        from payment_status import update_payment_status, check_payment_status
        from agent import create_order
        import json
        
        session_id = request.args.get('session_id')
        payment_id = request.args.get('paymentId')
        payer_id = request.args.get('PayerID')
        token = request.args.get('token')
        
        print(f"✅ PayPal Success Callback - Session: {session_id}, Payment: {payment_id}")
        
        if not session_id:
            return render_template_string("""
                <html><body>
                    <h2>Error: No session ID</h2>
                    <p>You can close this window.</p>
                    <script>setTimeout(() => window.close(), 3000);</script>
                </body></html>
            """)
        
        # Get payment data from status file
        payment_status = check_payment_status(session_id)
        
        if payment_status['status'] == 'not_found':
            return render_template_string("""
                <html><body>
                    <h2>Error: Payment session not found</h2>
                    <p>You can close this window.</p>
                    <script>setTimeout(() => window.close(), 3000);</script>
                </body></html>
            """)
        
        payment_data = payment_status.get('payment_data', {})
        customer_id = payment_data.get('customer_id')
        cart_items = payment_data.get('cart_items', [])
        
        # Create order in database
        order_result = None
        if customer_id and cart_items:
            try:
                cart_items_json = json.dumps(cart_items)
                query = f"customer_id:{customer_id},cart_items:{cart_items_json}"
                order_result = create_order.func(query)
                print(f"✅ Order creation result: {order_result}")
            except Exception as order_error:
                print(f"❌ Order creation failed: {order_error}")
                order_result = {"error": str(order_error)}
        
        # Update payment status file with result
        result_data = {
            'payment_id': payment_id,
            'payer_id': payer_id,
            'token': token,
            'order_result': order_result,
            'message': 'Payment completed successfully!'
        }
        
        update_payment_status(session_id, 'success', result_data)
        
        # Show auto-closing success page with congratulations message
        order_id = order_result.get('order_details', {}).get('order_id', 'Processing...')
        return f"""
        <html>
        <head>
            <title>🎉 Payment Successful</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    text-align: center;
                    padding: 50px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    margin: 0;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    min-height: 100vh;
                }}
                .container {{
                    background: white;
                    color: #333;
                    padding: 40px;
                    border-radius: 20px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.3);
                    max-width: 500px;
                    margin: 0 auto;
                }}
                .success-icon {{
                    font-size: 72px;
                    color: #10b981;
                    margin-bottom: 20px;
                    animation: bounce 1s ease infinite;
                }}
                .congrats {{
                    font-size: 32px;
                    font-weight: bold;
                    color: #10b981;
                    margin-bottom: 10px;
                }}
                .message {{
                    font-size: 18px;
                    color: #666;
                    margin: 15px 0;
                }}
                .order-id {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #667eea;
                    margin: 20px 0;
                    padding: 15px;
                    background: #f0f4ff;
                    border-radius: 10px;
                }}
                .countdown {{
                    font-size: 14px;
                    color: #999;
                    margin-top: 20px;
                }}
                @keyframes bounce {{
                    0%, 100% {{ transform: translateY(0); }}
                    50% {{ transform: translateY(-10px); }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">🎉</div>
                <div class="congrats">Congratulations!</div>
                <div class="message">Your order has been placed successfully!</div>
                <div class="order-id">
                    Order ID: #{order_id}
                </div>
                <div class="message">✅ Payment confirmed<br>📧 Confirmation email sent</div>
                <div class="countdown">This window will close in 3 seconds...</div>
            </div>
            <script>
                let countdown = 3;
                const countdownEl = document.querySelector('.countdown');
                const interval = setInterval(() => {{
                    countdown--;
                    if (countdown > 0) {{
                        countdownEl.textContent = `This window will close in ${{countdown}} seconds...`;
                    }} else {{
                        clearInterval(interval);
                        window.close();
                    }}
                }}, 1000);
            </script>
        </body>
        </html>
        """
        
    except Exception as e:
        print(f"❌ PayPal success callback error: {e}")
        import traceback
        traceback.print_exc()
        return f"""
        <html>
        <body>
            <h2>Error Processing Payment</h2>
            <p>{str(e)}</p>
            <p>You can close this window.</p>
            <script>setTimeout(() => window.close(), 5000);</script>
        </body>
        </html>
        """

@app.route("/paypal/callback/cancel")
def paypal_callback_cancel():
    """
    PayPal cancel callback - Updates temp file with cancelled status
    This page auto-closes after updating the status
    """
    try:
        from payment_status import update_payment_status
        
        session_id = request.args.get('session_id')
        
        print(f"⚠️ PayPal Cancel Callback - Session: {session_id}")
        
        if session_id:
            # Update payment status file
            result_data = {
                'message': 'Payment was cancelled by user'
            }
            update_payment_status(session_id, 'cancelled', result_data)
        
        # Show auto-closing cancel page
        return """
        <html>
        <head>
            <title>Payment Cancelled</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                .warning { color: #ffc107; font-size: 24px; }
                .info { color: #666; margin-top: 20px; }
            </style>
        </head>
        <body>
            <h1 class="warning">⚠️ Payment Cancelled</h1>
            <p class="info">Your payment was cancelled.</p>
            <p class="info">Your cart items have been preserved.</p>
            <p class="info">This window will close in 3 seconds...</p>
            <script>
                setTimeout(() => {
                    window.close();
                }, 3000);
            </script>
        </body>
        </html>
        """
        
    except Exception as e:
        print(f"❌ PayPal cancel callback error: {e}")
        return f"""
        <html>
        <body>
            <h2>Error</h2>
            <p>{str(e)}</p>
            <p>You can close this window.</p>
            <script>setTimeout(() => window.close(), 5000);</script>
        </body>
        </html>
        """

@app.route("/api/check-payment-status", methods=["GET"])
def api_check_payment_status():
    """
    API endpoint to check payment status (for polling)
    Frontend polls this every 10 seconds
    """
    try:
        from payment_status import check_payment_status
        
        session_id = request.args.get('session_id')
        
        if not session_id:
            return jsonify({"error": "session_id required"}), 400
        
        # Check payment status from file
        status_data = check_payment_status(session_id)
        
        if status_data['status'] == 'not_found':
            return jsonify({
                "status": "not_found",
                "message": "Payment session not found"
            }), 404
        
        current_status = status_data['status']
        
        # Return status and data
        response = {
            "status": current_status,  # 'pending', 'success', 'cancelled', 'error'
            "message": None,
            "order_details": None
        }
        
        if current_status == 'success':
            result = status_data.get('result', {})
            order_result = result.get('order_result', {})
            
            response['message'] = result.get('message', 'Payment successful!')
            response['order_details'] = order_result.get('order_details', {})
            response['payment_id'] = result.get('payment_id')
            
            print(f"✅ SUCCESS - Sending success response:")
            print(f"   Order Details: {response['order_details']}")
            print(f"   Payment ID: {response['payment_id']}")
            
        elif current_status == 'cancelled':
            result = status_data.get('result', {})
            response['message'] = result.get('message', 'Payment was cancelled')
            print(f"⚠️ CANCELLED - Payment cancelled by user")
            
        elif current_status == 'pending':
            response['message'] = 'Waiting for payment confirmation...'
            print(f"⏳ PENDING - Still waiting for payment...")
        
        print(f"🔍 Payment status check - Session: {session_id}, Status: {current_status}")
        print(f"📤 Returning response: {response}")
        
        return jsonify(response)
        
    except Exception as e:
        print(f"❌ Payment status check error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/test")
def test_ui():
    """Test page for UI components"""
    with open("test_ui.html", "r") as f:
        return f.read()

@app.route("/a2ui_demo")
def a2ui_demo():
    """A2UI Protocol Demo Page"""
    return render_template("a2ui_demo.html")

# ─── AI Personal Stylist ──────────────────────────────────────────────────────
# In-memory session store for multi-turn stylist conversations
_stylist_sessions = {}  # session_id -> { step, cart_product, occasion, colors, fit, budget }

def _build_stylist_outfit(state: dict):
    """
    Query SAP HANA to fetch outfit products matching stylist preferences.
    Returns (outfit_products_list, stylist_intro_text).
    NOTE: LLM call intentionally removed – builds intro from template to avoid
    blocking when Gemini API credits are exhausted.
    """
    conn   = None
    cursor = None
    try:
        from agent import hana_connect
        from modules.outfit_builder_a2ui import detect_category
        from datetime import datetime
        import re as _re

        cart_product = state.get("cart_product", {})
        cart_name    = cart_product.get("product_name", "")
        cart_id      = str(cart_product.get("product_id", "")).strip()
        occasion     = state.get("occasion", "casual")
        colors       = state.get("colors", "any")
        fit          = state.get("fit", "any")
        budget_str   = state.get("budget", "No limit")

        print(f"🧵 Stylist build: cart={cart_name!r}, occasion={occasion!r}, "
              f"colors={colors!r}, fit={fit!r}, budget={budget_str!r}")

        # Parse budget ceiling
        budget_max = 9999.0
        nums = _re.findall(r'\d+', budget_str)
        if nums:
            budget_max = float(max(int(n) for n in nums))
        print(f"🧵 budget_max={budget_max}")

        # Color keyword hints
        color_map = {
            "neutral":  ["black", "white", "beige", "grey", "cream"],
            "earth":    ["brown", "olive", "tan", "khaki", "camel"],
            "bold":     ["red", "orange", "yellow", "bright"],
            "pastel":   ["pastel", "mint", "blush", "lavender"],
            "navy":     ["navy", "blue", "cobalt"],
        }
        colors_lower = colors.lower()
        selected_colors = []
        for key, vals in color_map.items():
            if key in colors_lower:
                selected_colors = vals[:3]
                break
        print(f"🧵 selected_colors={selected_colors}")

        # Outfit categories with broad keyword sets based on actual DB data
        outfit_categories = [
            ("top",       ["shirt", "tee", "hoodie", "sweater", "blouse", "jumper",
                           "jersey", "knitwear", "pullover", "sweatshirt"]),
            ("bottom",    ["pant", "trouser", "jean", "short", "skirt",
                           "legging", "chino", "cargo", "boardshort"]),
            ("footwear",  ["sneaker", "shoe", "boot", "sandal", "trainer", "vans"]),
            ("accessory", ["belt", "bag", "cap", "beanie", "backpack",
                           "sunglass", "shades", "watch", "scarf", "glove"]),
        ]

        today = datetime.now().strftime('%Y-%m-%d')
        conn   = hana_connect()
        cursor = conn.cursor()

        cart_cat = detect_category(cart_name)
        print(f"🧵 cart_cat={cart_cat!r}")

        # Determine which categories to skip (already have in cart)
        skip_keys = set()
        if cart_cat:
            for cat_key, _ in outfit_categories:
                if cat_key.startswith(cart_cat[:3]) or cart_cat.startswith(cat_key[:3]):
                    skip_keys.add(cat_key)
                    break
        print(f"🧵 skipping categories: {skip_keys}")

        outfit_products = []

        for cat_key, keywords in outfit_categories:
            if cat_key in skip_keys:
                continue

            # Build category WHERE conditions
            cat_conds = " OR ".join(
                [f"UPPER(p.PRODUCT_NAME) LIKE '%{kw.upper()}%'" for kw in keywords]
            )

            # Optional color filter (only on PRODUCT_NAME to avoid SUMMARY type issues)
            color_cond = ""
            if selected_colors:
                color_parts = [f"UPPER(p.PRODUCT_NAME) LIKE '%{c.upper()}%'"
                               for c in selected_colors]
                color_cond = f"AND ({' OR '.join(color_parts)})"

            def build_sql(with_color: bool) -> str:
                cc = color_cond if with_color else ""
                return f"""
                    SELECT TOP 2
                        p.PRODUCT_ID, p.PRODUCT_NAME, p.SUMMARY, p.PRICE, p.IMAGE_URL,
                        promo.PROMO_DISCOUNT_PERCENT,
                        CASE
                            WHEN promo.PROMO_DISCOUNT_PERCENT IS NOT NULL
                            THEN p.PRICE * (1 - promo.PROMO_DISCOUNT_PERCENT / 100)
                            ELSE p.PRICE
                        END AS FINAL_PRICE
                    FROM SAP_PRODUCTS_COMMERCE_2211_V2 p
                    LEFT JOIN SAP_PROMOTION_COMMERCE_2211_V2 promo
                        ON TRIM(p.PRODUCT_ID) = TRIM(promo.PROMO_PRODUCT_ID)
                        AND promo.PROMO_START_DATE <= '{today}'
                        AND promo.PROMO_END_DATE   >= '{today}'
                    WHERE ({cat_conds})
                    {cc}
                    AND p.PRICE <= {budget_max}
                    AND TRIM(p.PRODUCT_ID) != '{cart_id}'
                    ORDER BY p.PRICE DESC
                """

            try:
                cursor.execute(build_sql(with_color=bool(color_cond)))
                rows = cursor.fetchall()
                print(f"🧵   {cat_key} with color: {len(rows)} rows")

                # Fallback: try without color filter
                if not rows and color_cond:
                    cursor.execute(build_sql(with_color=False))
                    rows = cursor.fetchall()
                    print(f"🧵   {cat_key} without color: {len(rows)} rows")

                for row in rows:
                    orig_price  = float(row[3]) if row[3] else 0.0
                    discount    = float(row[5]) if row[5] else 0.0
                    final_price = float(row[6]) if row[6] else orig_price
                    outfit_products.append({
                        "product_id":       str(row[0]).strip(),
                        "product_name":     (row[1] or "").strip(),
                        "summary":          (row[2] or "").strip(),
                        "price":            round(final_price, 2),
                        "original_price":   round(orig_price, 2),
                        "image_url":        row[4] or "",
                        "has_promotion":    discount > 0,
                        "discount_percent": discount,
                        "category":         cat_key,
                    })

            except Exception as cat_err:
                print(f"⚠️ Stylist: error fetching {cat_key}: {cat_err}")
                import traceback as _tb; _tb.print_exc()
                continue

        print(f"🧵 Total outfit products: {len(outfit_products)}")

        # Build a template stylist intro (no LLM call — avoids blocking on depleted API)
        if outfit_products:
            names = ", ".join(p["product_name"] for p in outfit_products[:3])
            stylist_intro = (
                f"Here's your complete outfit for **{occasion}**! 🌟\n\n"
                f"I've paired your **{cart_name}** with {names} "
                f"— keeping your {colors.split('(')[0].strip().lower()} palette "
                f"and {fit.lower()} style in mind. Enjoy your look! ✨"
            )
        else:
            stylist_intro = (
                f"I looked through our collection for **{occasion}** outfits to pair with "
                f"your **{cart_name}**, but couldn't find matching pieces within your preferences. "
                f"Try broadening your budget or colour choice! 💫"
            )

        return outfit_products, stylist_intro

    except Exception as e:
        print(f"❌ Stylist outfit build error: {e}")
        import traceback
        traceback.print_exc()
        return [], "Here's a curated selection to complete your look! 🌟"
    finally:
        # Always close HANA connection regardless of outcome
        try:
            if cursor: cursor.close()
        except Exception:
            pass
        try:
            if conn: conn.close()
        except Exception:
            pass


@app.route("/api/stylist-chat", methods=["POST"])
def api_stylist_chat():
    """
    AI Personal Stylist — multi-turn conversational outfit builder.
    Triggered after add-to-cart. Gathers occasion, colour palette, fit
    preference, and budget through quick-reply options, then returns a
    curated complete outfit from HANA.

    Request body:
        session_id   : unique browser session string
        action       : "start" | "chat" | "reset"
        message      : user reply text (for action="chat")
        cart_product : { product_id, product_name, price }  (required for "start")
    """
    try:
        data         = request.get_json(force=True, silent=True) or {}
        session_id   = (data.get("session_id") or "default").strip()
        user_message = (data.get("message") or "").strip()
        cart_product = data.get("cart_product", {})
        action       = data.get("action", "chat")

        # ── Start / reset: create fresh session ──────────────────────────────
        if action in ("start", "reset") or session_id not in _stylist_sessions:
            _stylist_sessions[session_id] = {
                "step":         1,
                "cart_product": cart_product,
                "occasion":     None,
                "colors":       None,
                "fit":          None,
                "budget":       None,
            }
            pname = cart_product.get("product_name", "your item")
            return jsonify({
                "message": (
                    f"✨ Great choice! I'm your **AI Stylist** and I'll help you "
                    f"build a complete outfit around **{pname}**.\n\n"
                    f"**What's the occasion?**"
                ),
                "step": 1,
                "options": ["Casual Day Out", "Office / Work", "Date Night",
                            "Gym / Active", "Beach / Holiday", "Formal / Wedding"],
                "done": False,
            })

        state = _stylist_sessions[session_id]
        step  = state["step"]

        # ── Step 1: Save occasion → ask colour ───────────────────────────────
        if step == 1:
            state["occasion"] = user_message or "casual"
            state["step"]     = 2
            return jsonify({
                "message": f"Perfect for **{state['occasion']}**! 🎨\n\nWhat **colour palette** do you prefer?",
                "step": 2,
                "options": ["Neutral (black/white/beige)", "Earth tones (olive/tan/brown)",
                            "Bold & bright", "Pastels", "Navy & blues", "No preference"],
                "done": False,
            })

        # ── Step 2: Save colour → ask fit ────────────────────────────────────
        elif step == 2:
            state["colors"] = user_message or "any"
            state["step"]   = 3
            return jsonify({
                "message": "Got it! 💫  What **fit / style** do you prefer?",
                "step": 3,
                "options": ["Slim / tailored", "Relaxed / loose", "Athletic / sporty",
                            "Classic / timeless", "Trendy", "Comfortable / easy"],
                "done": False,
            })

        # ── Step 3: Save fit → ask budget ────────────────────────────────────
        elif step == 3:
            state["fit"]  = user_message or "any"
            state["step"] = 4
            return jsonify({
                "message": "Almost there! 💷  **What's your budget** for the remaining pieces?",
                "step": 4,
                "options": ["Under £50", "£50 – £100", "£100 – £200", "£200 – £300", "No limit"],
                "done": False,
            })

        # ── Step 4: Build outfit ──────────────────────────────────────────────
        elif step == 4:
            state["budget"] = user_message or "No limit"
            outfit_products, stylist_message = _build_stylist_outfit(state)

            # Clear session
            _stylist_sessions.pop(session_id, None)

            return jsonify({
                "message":        stylist_message,
                "step":           5,
                "done":           True,
                "outfit_products": outfit_products,
            })

        else:
            _stylist_sessions.pop(session_id, None)
            return jsonify({"message": "Your outfit is ready! 🎉", "done": True, "outfit_products": []})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Use a provided port or default to 5000
    app.run(host="localhost", port=5000, debug=True)

