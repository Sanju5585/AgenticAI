from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, render_template_string, send_from_directory
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
from datetime import timedelta
from werkzeug.utils import secure_filename
from visual_search import search_by_image


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
PAYPAL_MCP_PORT = os.getenv('PAYPAL_MCP_PORT', '8110')
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

# Product detail page route
@app.route("/product/<product_id>")
@app.route("/product/<product_id>/<path:product_name_slug>")
def product_detail(product_id, product_name_slug=None):
    """Display product detail page with payment plans for mobile and watches"""
    from agent import hana_connect
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get product information
        sql = '''
            SELECT PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, CATEGORY_IDS, IMAGE_URL
            FROM SAP_MEIJER_PRODUCTS_V1
            WHERE TRIM(PRODUCT_ID) = ?
        '''
        cursor.execute(sql, (product_id,))
        row = cursor.fetchone()
        
        if not row:
            cursor.close()
            conn.close()
            return "Product not found", 404
        
        product = {
            'id': row[0],
            'name': row[1],
            'summary': row[2],
            'price': float(row[3]) if row[3] else 0.0,
            'category_ids': row[4],
            'image_URL': row[5]
        }
        
        cursor.close()
        conn.close()
        
        return render_template("product_detail.html", product=product, payment_plans=[])
        
    except Exception as e:
        print(f"Error loading product detail: {str(e)}")
        return f"Error loading product: {str(e)}", 500

# Serve images from the images folder
@app.route("/images/<path:filename>")
def serve_image(filename):
    """Serve product images from the images folder"""
    return send_from_directory('images', filename)

@app.route("/static/images/<path:filename>")
def serve_meijer_image(filename):
    """Serve Meijer product images with .jpg → .jpeg extension fallback."""
    img_dir = os.path.join(app.static_folder, 'images')
    if os.path.exists(os.path.join(img_dir, filename)):
        return send_from_directory(img_dir, filename)
    base = os.path.splitext(filename)[0]
    for ext in ['.jpeg', '.jpg', '.png', '.gif', '.webp']:
        candidate = base + ext
        if os.path.exists(os.path.join(img_dir, candidate)):
            return send_from_directory(img_dir, candidate)
    return send_from_directory(os.path.join(app.static_folder, 'assets'), 'product-placeholder.svg')

@app.route("/static/product_images/<path:filename>")
def serve_product_image(filename):
    """Serve product images with extension fallback.
    DB stores .jpg but files may be .jpeg or .png — try all variants."""
    import os
    img_dir = os.path.join(app.static_folder, 'product_images')
    # Try exact filename first
    if os.path.exists(os.path.join(img_dir, filename)):
        return send_from_directory(img_dir, filename)
    # Try alternate extensions
    base = os.path.splitext(filename)[0]
    for ext in ['.jpeg', '.jpg', '.png', '.gif', '.webp']:
        candidate = base + ext
        if os.path.exists(os.path.join(img_dir, candidate)):
            return send_from_directory(img_dir, candidate)
    # Fall back to placeholder
    return send_from_directory(os.path.join(app.static_folder, 'assets'), 'product-placeholder.svg')

@app.route("/api/best-selling-products", methods=["GET"])
def api_best_selling_products():
    """
    Trending Now (anonymous) or Interest-based recommendations (logged-in).
    Serves Meijer grocery products directly from SAP_MEIJER_PRODUCTS_V1.
    """
    try:
        customer_id = request.args.get("customer_id", "").strip()
        page_size   = request.args.get("pageSize", 8, type=int)

        conn   = get_db_connection()
        cursor = conn.cursor()

        products = []

        if customer_id:
            # ── personalised: based on last 2-3 orders ──────────────────────
            # 1. Get recent ordered product IDs from Meijer orders table
            ordered_pids = []
            cursor.execute("""
                SELECT PRODUCT_ID, MAX(ORDER_DATE) AS LAST_DATE
                FROM SAP_MEIJER_ORDERS_V1
                WHERE CUSTOMER_ID = ?
                GROUP BY PRODUCT_ID
                ORDER BY LAST_DATE DESC
                LIMIT 10
            """, (customer_id,))
            for r in cursor.fetchall():
                if r[0]:
                    ordered_pids.append(str(r[0]).strip())



            if ordered_pids:
                # 2. Look up category_ids for those products (take first 3 unique products)
                sample_pids = ordered_pids[:3]
                placeholders = ",".join(["?" for _ in sample_pids])
                cursor.execute(
                    f"SELECT PRODUCT_ID, PRODUCT_NAME, CATEGORY_IDS FROM SAP_MEIJER_PRODUCTS_V1 WHERE PRODUCT_ID IN ({placeholders})",
                    sample_pids
                )
                ordered_products = cursor.fetchall()

                # Collect category tokens from ordered products
                category_tokens = set()
                ordered_product_names = []
                for op in ordered_products:
                    pid, pname, cat_ids = op
                    ordered_product_names.append(pname or "")
                    if cat_ids:
                        for token in str(cat_ids).replace(",", " ").replace("|", " ").split():
                            t = token.strip()
                            if len(t) > 2:
                                category_tokens.add(t.upper())

                # 3. Build WHERE clause from category tokens
                exclude_placeholders = ",".join(["?" for _ in ordered_pids])
                if category_tokens:
                    cat_conditions = " OR ".join(
                        f"UPPER(CATEGORY_IDS) LIKE '%{tok}%'" for tok in category_tokens
                    )
                    sql = f"""
                        SELECT PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, CATEGORY_IDS, IMAGE_URL, BRAND
                        FROM SAP_MEIJER_PRODUCTS_V1
                        WHERE ({cat_conditions})
                        AND PRODUCT_ID NOT IN ({exclude_placeholders})
                        ORDER BY RAND()
                        LIMIT ?
                    """
                    cursor.execute(sql, ordered_pids + [page_size])
                else:
                    # No category info — just random excluding ordered
                    cursor.execute(
                        f"SELECT PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, CATEGORY_IDS, IMAGE_URL, BRAND FROM SAP_MEIJER_PRODUCTS_V1 WHERE PRODUCT_ID NOT IN ({exclude_placeholders}) ORDER BY RAND() LIMIT ?",
                        ordered_pids + [page_size]
                    )

                for r in cursor.fetchall():
                    products.append({
                        "product_id":   str(r[0]).strip(),
                        "product_name": r[1] or "",
                        "summary":      r[2] or "",
                        "price":        float(r[3]) if r[3] else 0.0,
                        "category_ids": r[4] or "",
                        "image_url":    r[5] or "",
                        "brand":        r[6] or "",
                    })

                # Build a readable subtitle from ordered product names (first 2)
                name_labels = [n.split()[0] for n in ordered_product_names[:2] if n]
                recent_label = " & ".join(name_labels) if name_labels else "recent purchases"

                cursor.close()
                conn.close()
                return jsonify({"products": products, "total": len(products), "personalized": True, "interest": recent_label, "based_on": "orders"})

            else:
                # No orders yet — fall back to trending
                cursor.execute(
                    "SELECT PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, CATEGORY_IDS, IMAGE_URL, BRAND FROM SAP_MEIJER_PRODUCTS_V1 ORDER BY RAND() LIMIT ?",
                    (page_size,)
                )
                for r in cursor.fetchall():
                    products.append({
                        "product_id":   str(r[0]).strip(),
                        "product_name": r[1] or "",
                        "summary":      r[2] or "",
                        "price":        float(r[3]) if r[3] else 0.0,
                        "category_ids": r[4] or "",
                        "image_url":    r[5] or "",
                        "brand":        r[6] or "",
                    })
                cursor.close()
                conn.close()
                return jsonify({"products": products, "total": len(products), "personalized": False})

        else:
            # ── trending: varied selection across Meijer categories ──────────
            categories = [
                "300101",   # Ice Cream
                "333300",   # Frozen Pizzas
                "400101",   # Chips
                "400103",   # Cookies
                "700101",   # Bread
                "600103",   # Coffee
                "400202",   # Yogurt
                "700200",   # Cereal & Breakfast
            ]
            per_cat = max(1, page_size // len(categories))
            seen = set()
            for cat in categories:
                cursor.execute(
                    f"SELECT PRODUCT_ID, PRODUCT_NAME, SUMMARY, PRICE, CATEGORY_IDS, IMAGE_URL, BRAND FROM SAP_MEIJER_PRODUCTS_V1 WHERE CATEGORY_IDS = ? ORDER BY RAND() LIMIT ?",
                    (cat, per_cat,)
                )
                for r in cursor.fetchall():
                    pid = str(r[0]).strip()
                    if pid not in seen:
                        seen.add(pid)
                        products.append({
                            "product_id":   pid,
                            "product_name": r[1] or "",
                            "summary":      r[2] or "",
                            "price":        float(r[3]) if r[3] else 0.0,
                            "category_ids": r[4] or "",
                            "image_url":    r[5] or "",
                            "brand":        r[6] or "",
                        })
                if len(products) >= page_size:
                    break

            cursor.close()
            conn.close()
            return jsonify({"products": products[:page_size], "total": len(products), "personalized": False})

    except Exception as e:
        print(f"Best selling products API error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def build_similar_products_a2ui_json(products, source_product_id=""):
    """
    Build an A2UI JSON structure from cross-sell / upsell / similar DB rows.
    This JSON is pushed via WebSocket so the frontend can render the carousel directly.
    """
    BADGE_CONFIG = {
        "crosssell": {"label": "You May Need", "color": "#D71920"},
        "upsell":    {"label": "Upgrade",       "color": "#F47920"},
        "similar":   {"label": "Similar",        "color": "#1B5252"},
    }
    items = []
    for i, p in enumerate(products):
        badge = BADGE_CONFIG.get(p.get("relation_type", "similar"), BADGE_CONFIG["similar"])
        price_val = p.get("price", 0)
        price_str = f"${float(price_val):.2f}" if price_val else "N/A"
        items.append({
            "id":   p["product_id"],
            "type": "product_card",
            "display_order": i,
            "content": {
                "image":       p.get("image_url") or "/static/assets/product-placeholder.svg",
                "title":       p.get("product_name", ""),
                "brand":       p.get("brand", ""),
                "price":       price_str,
                "badge":       badge["label"],
                "badge_color": badge["color"],
                "action":      "view_details",
            },
            "styling": {
                "card_style":   "modern",
                "hover_effect": "lift",
                "animation":    "slideInRight",
            },
        })
    return {
        "component_type": "carousel",
        "layout":         "horizontal_scroll",
        "title":          "You May Also Like",
        "source_product": source_product_id,
        "items":          items,
        "controls": {
            "show_navigation": True,
            "auto_scroll":     False,
        },
        "styling": {
            "theme":        "light",
            "card_spacing": "medium",
        },
    }


@app.route("/api/similar-products/<product_id>", methods=["GET"])
def api_similar_products(product_id):
    """
    Return similar/crosssell/upsell products for a given product_id.
    Uses SAP_MEIJER_CROSSSELL_V1 when available; falls back to same-category products.
    Query param ?type=similar|crosssell|upsell|all (default: all)
    Query param ?limit=N (default 8)
    Query param ?session_id=... (optional — enables A2UI push via WebSocket)
    """
    try:
        relation_type = request.args.get("type", "all")
        limit = request.args.get("limit", 8, type=int)
        session_id = request.args.get("session_id", "").strip()

        conn = get_db_connection()
        cursor = conn.cursor()

        products = []
        try:
            if relation_type == "all":
                sql = """
                    SELECT p.PRODUCT_ID, p.PRODUCT_NAME, p.SUMMARY, p.PRICE,
                           p.CATEGORY_IDS, p.IMAGE_URL, p.BRAND, c.RELATION_TYPE, c.DISPLAY_ORDER
                    FROM SAP_MEIJER_CROSSSELL_V1 c
                    JOIN SAP_MEIJER_PRODUCTS_V1 p ON c.RELATED_PRODUCT_ID = TRIM(p.PRODUCT_ID)
                    WHERE TRIM(c.PRODUCT_ID) = ?
                    ORDER BY
                        CASE c.RELATION_TYPE
                            WHEN 'crosssell' THEN 1
                            WHEN 'upsell'    THEN 2
                            ELSE             3
                        END,
                        c.DISPLAY_ORDER
                    LIMIT ?
                """
                cursor.execute(sql, (product_id.strip(), limit))
            else:
                sql = """
                    SELECT p.PRODUCT_ID, p.PRODUCT_NAME, p.SUMMARY, p.PRICE,
                           p.CATEGORY_IDS, p.IMAGE_URL, p.BRAND, c.RELATION_TYPE, c.DISPLAY_ORDER
                    FROM SAP_MEIJER_CROSSSELL_V1 c
                    JOIN SAP_MEIJER_PRODUCTS_V1 p ON c.RELATED_PRODUCT_ID = TRIM(p.PRODUCT_ID)
                    WHERE TRIM(c.PRODUCT_ID) = ? AND c.RELATION_TYPE = ?
                    ORDER BY c.DISPLAY_ORDER
                    LIMIT ?
                """
                cursor.execute(sql, (product_id.strip(), relation_type, limit))

            for row in cursor.fetchall():
                products.append({
                    "product_id":    str(row[0]).strip(),
                    "product_name":  row[1] or "",
                    "summary":       row[2] or "",
                    "price":         float(row[3]) if row[3] else 0.0,
                    "category_ids":  row[4] or "",
                    "image_url":     row[5] or "",
                    "brand":         row[6] or "",
                    "relation_type": row[7] or "similar",
                    "display_order": row[8] or 0,
                })
        except Exception as crosssell_err:
            print(f"⚠️ Crosssell table unavailable ({crosssell_err}), using same-category fallback")
            cursor.execute(
                """SELECT p2.PRODUCT_ID, p2.PRODUCT_NAME, p2.SUMMARY, p2.PRICE,
                          p2.CATEGORY_IDS, p2.IMAGE_URL, p2.BRAND
                   FROM SAP_MEIJER_PRODUCTS_V1 p1
                   JOIN SAP_MEIJER_PRODUCTS_V1 p2
                     ON p1.CATEGORY_IDS = p2.CATEGORY_IDS
                    AND TRIM(p2.PRODUCT_ID) != TRIM(p1.PRODUCT_ID)
                   WHERE TRIM(p1.PRODUCT_ID) = ?
                   ORDER BY RAND()
                   LIMIT ?""",
                (product_id.strip(), limit)
            )
            for row in cursor.fetchall():
                products.append({
                    "product_id":    str(row[0]).strip(),
                    "product_name":  row[1] or "",
                    "summary":       row[2] or "",
                    "price":         float(row[3]) if row[3] else 0.0,
                    "category_ids":  row[4] or "",
                    "image_url":     row[5] or "",
                    "brand":         row[6] or "",
                    "relation_type": "similar",
                    "display_order": 0,
                })

        cursor.close()
        conn.close()

        # Push via A2UI WebSocket if session_id provided
        if session_id and products:
            import threading, requests as _req
            a2ui_json = build_similar_products_a2ui_json(products, product_id)

            def _push_a2ui():
                try:
                    a2ui_url = os.environ.get("A2UI_SERVER_URL", "http://localhost:8020")
                    # Push the structured A2UI JSON for direct carousel rendering
                    _req.post(
                        f"{a2ui_url}/api/ui/update/{session_id}",
                        json={
                            "module":    "similar_products",
                            "action":    "render",
                            "component": "similar_products_a2ui",
                            "data": {
                                "a2ui_json":         a2ui_json,
                                "source_product_id": product_id,
                                "total":             len(products),
                            },
                            "metadata": {
                                "component_type": "carousel",
                                "item_count":     len(products),
                            },
                        },
                        timeout=5,
                    )
                    print(f"✅ A2UI similar_products_a2ui pushed to session {session_id} ({len(products)} items)")
                except Exception as _e:
                    print(f"⚠️ A2UI similar_products push failed: {_e}")

            threading.Thread(target=_push_a2ui, daemon=True).start()

        return jsonify({"products": products, "source_product_id": product_id, "total": len(products)})

    except Exception as e:
        print(f"Similar products API error for {product_id}: {e}")
        return jsonify({"error": str(e), "products": []}), 500

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
        
        # Log database source
        if result.get("success"):
            db_source = result.get("database_source", "Unknown")
            table_name = result.get("table_name", "Unknown")
            search_method = result.get("search_method", "Unknown")
            count = result.get("count", 0)
            print(f"✅ Visual search SUCCESS:")
            print(f"   📦 Source: {db_source}")
            print(f"   🗄️  Table: {table_name}")
            print(f"   🔍 Method: {search_method}")
            print(f"   📊 Results: {count} products")

        response_payload = {
            "success": result.get("success", False),
            "response_type": "visual_search",
            "analysis": result.get("analysis", {}),
            "features": result.get("features", {}),
            "products_data": result.get("results", []),
            "image_cache": result.get("image_cache"),
            "query_generated": result.get("query_generated"),
            "count": result.get("count", len(result.get("results", []))),
            "database_source": result.get("database_source"),
            "table_name": result.get("table_name"),
            "search_method": result.get("search_method")
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
            # Fallback to trending products
            from tools.hybris_occ import get_best_selling_products
            trending_result = get_best_selling_products(page_size)
            products = []
            for product in trending_result.get("results", []):
                products.append({
                    "product_id": product.get("id", ""),
                    "product_name": product.get("name", ""),
                    "summary": product.get("description", ""),
                    "price": product.get("price", 0.0),
                    "image_url": product.get("image", ""),
                    "rating": product.get("averageRating"),
                    "url": product.get("url", "")
                })
            return jsonify({
                "products": products,
                "source": "trending_fallback",
                "total": len(products),
                "personalized": False
            })
        
        results = result.get('results', [])
        
        # Transform to frontend format
        products = []
        for product in results:
            products.append({
                "product_id": product.get('PRODUCT_ID', ''),
                "product_name": product.get('PRODUCT_NAME', ''),
                "summary": product.get('SUMMARY', ''),
                "price": product.get('PRICE', 0.0),
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
            trending_result = get_best_selling_products(page_size)
            products = []
            for product in trending_result.get("results", []):
                products.append({
                    "product_id": product.get("id", ""),
                    "product_name": product.get("name", ""),
                    "summary": product.get("description", ""),
                    "price": product.get("price", 0.0),
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
        
        # Check if email exists in Meijer customer table
        query = """
            SELECT CUSTOMER_NAME, CUSTOMER_ID, PASSWORD_HASH, INTEREST
            FROM SAP_MEIJER_CUSTOMERS_V1
            WHERE LOWER(CUSTOMER_ID) = ?
        """
        cursor.execute(query, (email,))
        result = cursor.fetchone()
        
        if not result:
            cursor.close()
            conn.close()
            return jsonify({"error": "Email not found in our system. Please check your email address."}), 401
        
        customer_name = result[0]
        customer_id   = result[1]
        password_hash = result[2]
        interest      = result[3] or ""

        # Verify password
        from werkzeug.security import check_password_hash
        if not check_password_hash(password_hash, password):
            cursor.close()
            conn.close()
            return jsonify({"error": "Incorrect password. Please try again."}), 401
        
        # Get last 5 orders for welcome message
        orders = []
        try:
            cursor.execute("""
                SELECT o.ORDER_ID, o.ORDER_DATE, o.ORDER_STATUS, o.PRODUCT_NAME,
                       o.LINE_TOTAL, o.PRODUCT_ID, o.IMAGE_URL
                FROM SAP_MEIJER_ORDERS_V1 o
                WHERE o.CUSTOMER_ID = ?
                ORDER BY o.ORDER_DATE DESC, o.ORDER_ID DESC, o.LINE_ITEM_ID ASC
                LIMIT 5
            """, (customer_id,))
            orders = cursor.fetchall()
        except Exception as orders_err:
            print(f"⚠️ Orders query skipped: {orders_err}")


        
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
            "interest": interest,
            "recent_orders": recent_orders,
            "total_orders": len(recent_orders)
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
        data = request.get_json()
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

        # Ensure the response is JSON-serializable
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
                    "details": "Please start the PayPal server using 'python run_both_servers.py'",
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
                "details": "The PayPal server is not running. Please start both servers using 'python run_both_servers.py'",
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
                "details": "Please ensure the PayPal server is running using 'python run_both_servers.py'",
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

if __name__ == "__main__":
    # Use a provided port or default to 5000
    app.run(host="0.0.0.0", port=5000, debug=True)

