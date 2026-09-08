"""
Product Search A2UI Module
Handles product search functionality with A2UI Protocol integration
for real-time UI updates and seamless user experience.
"""

import asyncio
import httpx
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# A2UI Server Configuration
A2UI_SERVER_URL = os.getenv("A2UI_SERVER_URL", "http://localhost:8020")

class ProductSearchA2UI:
    """
    Product Search module with A2UI Protocol integration
    Sends real-time updates to frontend during search operations
    """
    
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id
        self.module_name = "product_search"
        
    async def send_ui_update(self, action: str, component: str, data: Dict[str, Any], metadata: Optional[Dict] = None):
        """Send UI update to A2UI server"""
        try:
            async with httpx.AsyncClient() as client:
                endpoint = f"{A2UI_SERVER_URL}/api/ui/update"
                if self.session_id:
                    endpoint = f"{A2UI_SERVER_URL}/api/ui/update/{self.session_id}"
                
                payload = {
                    "module": self.module_name,
                    "action": action,
                    "component": component,
                    "data": data,
                    "metadata": metadata or {}
                }
                
                response = await client.post(endpoint, json=payload, timeout=5.0)
                if response.status_code == 200:
                    logger.info(f"✅ UI update sent: {action} -> {component}")
                else:
                    logger.warning(f"⚠️ UI update failed: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"❌ Error sending UI update: {e}")
            # Don't fail the main operation if UI update fails
            
    async def send_loading_state(self, is_loading: bool, message: str = ""):
        """Update loading state in the UI"""
        await self.send_ui_update(
            action="update",
            component="loading_state",
            data={
                "is_loading": is_loading,
                "message": message
            }
        )
        
    async def send_search_results(self, products: List[Dict], query: str, total_count: int):
        """Send search results to UI"""
        await self.send_ui_update(
            action="replace",
            component="product_list",
            data={
                "products": products,
                "query": query,
                "total_count": total_count,
                "timestamp": datetime.utcnow().isoformat()
            },
            metadata={
                "search_query": query,
                "result_count": len(products)
            }
        )
        
    async def send_error(self, error_message: str, error_type: str = "search_error"):
        """Send error notification to UI"""
        await self.send_ui_update(
            action="update",
            component="error_state",
            data={
                "has_error": True,
                "error_message": error_message,
                "error_type": error_type
            }
        )
        
    async def send_toast(self, message: str, toast_type: str = "info"):
        """Send toast notification to UI"""
        try:
            async with httpx.AsyncClient() as client:
                endpoint = f"{A2UI_SERVER_URL}/api/ui/command"
                
                payload = {
                    "module": self.module_name,
                    "command": "show_toast",
                    "params": {
                        "message": message,
                        "type": toast_type,  # success, error, warning, info
                        "duration": 3000
                    }
                }
                
                await client.post(endpoint, json=payload, timeout=5.0)
                
        except Exception as e:
            logger.error(f"Error sending toast: {e}")
            
    async def search_products(self, query: str, filters: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Main search function with A2UI integration
        
        Args:
            query: Search query string
            filters: Optional filters (category, price_range, etc.)
            
        Returns:
            Search results with metadata
        """
        try:
            # 1. Send loading state
            await self.send_loading_state(True, "Searching products...")
            
            # 2. Import and use existing search logic
            from agent import search_products_tool
            
            # 3. Perform search (this uses your existing implementation)
            results = await asyncio.to_thread(
                search_products_tool.invoke,
                {"query": query}
            )
            
            # 4. Process results
            if isinstance(results, str):
                # Parse string results
                import json
                try:
                    results = json.loads(results)
                except:
                    results = {"products": [], "message": results}
            
            products = results.get("products", []) if isinstance(results, dict) else []
            
            # 5. Send results to UI
            await self.send_search_results(
                products=products,
                query=query,
                total_count=len(products)
            )
            
            # 6. Send success notification
            if products:
                await self.send_toast(
                    f"Found {len(products)} products",
                    toast_type="success"
                )
            else:
                await self.send_toast(
                    "No products found. Try a different search.",
                    toast_type="info"
                )
            
            # 7. Clear loading state
            await self.send_loading_state(False)
            
            return {
                "success": True,
                "products": products,
                "total_count": len(products),
                "query": query
            }
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            
            # Send error to UI
            await self.send_error(
                error_message=f"Search failed: {str(e)}",
                error_type="search_error"
            )
            await self.send_loading_state(False)
            
            return {
                "success": False,
                "error": str(e),
                "products": [],
                "total_count": 0
            }
            
    async def get_product_details(self, product_id: str) -> Dict[str, Any]:
        """
        Get detailed product information with A2UI updates
        
        Args:
            product_id: Product ID
            
        Returns:
            Product details
        """
        try:
            await self.send_loading_state(True, "Loading product details...")
            
            # Import and use existing product details function
            from agent import get_product_details_tool
            
            # Get product details
            details = await asyncio.to_thread(
                get_product_details_tool.invoke,
                {"query": product_id}
            )
            
            # Send to UI
            await self.send_ui_update(
                action="update",
                component="product_details",
                data={"product": details}
            )
            
            await self.send_loading_state(False)
            
            return {
                "success": True,
                "product": details
            }
            
        except Exception as e:
            logger.error(f"Error getting product details: {e}")
            await self.send_error(f"Failed to load product: {str(e)}")
            await self.send_loading_state(False)
            
            return {
                "success": False,
                "error": str(e)
            }
            
    async def filter_products(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply filters to products with real-time UI updates
        
        Args:
            filters: Filter criteria (category, price_range, brand, etc.)
            
        Returns:
            Filtered products
        """
        try:
            await self.send_loading_state(True, "Applying filters...")
            
            # Build filter query
            filter_parts = []
            if filters.get("category"):
                filter_parts.append(f"category:{filters['category']}")
            if filters.get("min_price"):
                filter_parts.append(f"min_price:{filters['min_price']}")
            if filters.get("max_price"):
                filter_parts.append(f"max_price:{filters['max_price']}")
            if filters.get("brand"):
                filter_parts.append(f"brand:{filters['brand']}")
                
            query = " ".join(filter_parts) or "all products"
            
            # Search with filters
            results = await self.search_products(query, filters)
            
            await self.send_loading_state(False)
            
            return results
            
        except Exception as e:
            logger.error(f"Filter error: {e}")
            await self.send_error(f"Filter failed: {str(e)}")
            await self.send_loading_state(False)
            
            return {
                "success": False,
                "error": str(e),
                "products": []
            }

# ============================================================================
# HELPER FUNCTIONS FOR BACKWARD COMPATIBILITY
# ============================================================================

def create_product_search_session(session_id: str) -> ProductSearchA2UI:
    """
    Factory function to create a product search instance with session
    
    Args:
        session_id: User session ID
        
    Returns:
        ProductSearchA2UI instance
    """
    return ProductSearchA2UI(session_id=session_id)

async def search_products_with_a2ui(query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function for product search with A2UI
    
    Args:
        query: Search query
        session_id: Optional session ID for targeted updates
        
    Returns:
        Search results
    """
    search_module = ProductSearchA2UI(session_id=session_id)
    return await search_module.search_products(query)

# ============================================================================
# SYNC WRAPPER FOR FLASK INTEGRATION
# ============================================================================

def search_products_sync(query: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Synchronous wrapper for Flask integration
    Uses asyncio to run the async search function
    
    Args:
        query: Search query
        session_id: Optional session ID
        
    Returns:
        Search results
    """
    try:
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run async function
        return loop.run_until_complete(
            search_products_with_a2ui(query, session_id)
        )
    except Exception as e:
        logger.error(f"Sync wrapper error: {e}")
        return {
            "success": False,
            "error": str(e),
            "products": []
        }
