"""
Example: How to integrate Product Search A2UI Module into app.py

Add this to your existing app.py file to enable A2UI protocol for product search
"""

# ============================================================================
# Add these imports at the top of app.py
# ============================================================================

from modules.product_search_a2ui import search_products_sync, create_product_search_session
import asyncio

# ============================================================================
# Modify your existing /api/query endpoint
# ============================================================================

@app.route("/api/query", methods=["POST"])
def query():
    """
    Enhanced query endpoint with A2UI support
    """
    try:
        data = request.json
        user_query = data.get("query", "")
        session_id = data.get("session_id", None)  # Get session_id from frontend
        
        if not user_query:
            return jsonify({"error": "No query provided"}), 400
        
        # Content moderation
        is_appropriate, moderation_message = check_content(user_query)
        if not is_appropriate:
            return jsonify({"response": moderation_message}), 200
        
        # Try A2UI-enabled search first
        if session_id:
            try:
                # Use A2UI product search (sends real-time updates)
                results = search_products_sync(user_query, session_id)
                
                if results.get("success"):
                    # Format response for frontend
                    return jsonify({
                        "response_type": "products_list",
                        "products_data": results.get("products", []),
                        "total_count": results.get("total_count", 0),
                        "query": user_query,
                        "ai_response": f"Found {results.get('total_count', 0)} products for '{user_query}'",
                        "a2ui_enabled": True
                    })
            except Exception as e:
                app.logger.error(f"A2UI search failed: {e}")
                # Fall back to traditional method
        
        # Traditional search (if A2UI not available or failed)
        session.permanent = True
        session_id = session.get('session_id', str(uuid.uuid4()))
        session['session_id'] = session_id
        
        response = process_query(user_query, session_id, llm)
        
        return jsonify({
            "response": response.get("response", ""),
            "response_type": response.get("response_type", "text"),
            "products_data": response.get("products_data", []),
            "a2ui_enabled": False
        })
        
    except Exception as e:
        app.logger.error(f"Query error: {e}")
        return jsonify({"error": str(e)}), 500

# ============================================================================
# Add new endpoint for A2UI product details
# ============================================================================

@app.route("/api/product/<product_id>", methods=["GET"])
def get_product_details_a2ui(product_id):
    """
    Get product details with A2UI support
    """
    try:
        session_id = request.args.get("session_id")
        
        if session_id:
            # Use A2UI module
            search_module = create_product_search_session(session_id)
            
            # Get event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Get product details (sends to UI via A2UI)
            result = loop.run_until_complete(
                search_module.get_product_details(product_id)
            )
            
            if result.get("success"):
                return jsonify({
                    "success": True,
                    "product": result.get("product"),
                    "a2ui_enabled": True
                })
        
        # Traditional method
        from agent import get_product_details_tool
        product = get_product_details_tool.invoke({"query": product_id})
        
        return jsonify({
            "success": True,
            "product": product,
            "a2ui_enabled": False
        })
        
    except Exception as e:
        app.logger.error(f"Product details error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ============================================================================
# Add health check endpoint for A2UI
# ============================================================================

@app.route("/api/a2ui/status", methods=["GET"])
def a2ui_status():
    """
    Check if A2UI Protocol Server is available
    """
    import requests
    from flask import current_app
    
    a2ui_url = os.getenv("A2UI_SERVER_URL", "http://localhost:8020")
    
    try:
        response = requests.get(f"{a2ui_url}/", timeout=2)
        if response.status_code == 200:
            return jsonify({
                "a2ui_available": True,
                "server_url": a2ui_url,
                "status": response.json()
            })
    except Exception as e:
        current_app.logger.warning(f"A2UI server not available: {e}")
    
    return jsonify({
        "a2ui_available": False,
        "server_url": a2ui_url,
        "error": "A2UI server not reachable"
    })

# ============================================================================
# Usage Notes
# ============================================================================

"""
INTEGRATION STEPS:

1. Copy the imports to the top of app.py
2. Replace or modify your existing /api/query endpoint
3. Add the new /api/product/<product_id> endpoint
4. Add the /api/a2ui/status endpoint
5. Test by running START_ALL_SERVERS.bat

FRONTEND CHANGES:

Update your fetch call to include session_id:

fetch("/api/query", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ 
        query: queryValue,
        session_id: a2uiClient ? a2uiClient.sessionId : null
    })
})

BENEFITS:

- Real-time loading indicators
- Instant product updates
- Better user experience
- Progressive enhancement (works without A2UI)
- No breaking changes to existing code
"""
