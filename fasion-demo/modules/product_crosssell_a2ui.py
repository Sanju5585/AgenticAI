"""
Product Cross-Sell A2UI Module
Handles cross-sell product display with A2UI Protocol integration
for real-time UI updates when viewing product details.
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

class ProductCrossSellA2UI:
    """
    Product Cross-Sell module with A2UI Protocol integration
    Sends real-time cross-sell product updates to frontend
    """
    
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id
        self.module_name = "product_crosssell"
        
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
                
                print(f"\n{'='*80}")
                print(f"📡 A2UI Cross-Sell JSON Update")
                print(f"{'='*80}")
                print(f"   Session: {self.session_id}")
                print(f"   Endpoint: {endpoint}")
                print(f"\n📋 JSON Payload:")
                import json
                print(json.dumps(payload, indent=2, default=str))
                print(f"{'='*80}\n")
                
                response = await client.post(endpoint, json=payload, timeout=5.0)
                if response.status_code == 200:
                    logger.info(f"✅ Cross-Sell UI update sent: {action} -> {component}")
                    print(f"✅ A2UI Response: {response.status_code}")
                else:
                    logger.warning(f"⚠️ Cross-Sell UI update failed: {response.status_code}")
                    print(f"⚠️ A2UI Response failed: {response.status_code}")
                    print(f"   Response: {response.text}")
                    
        except Exception as e:
            logger.error(f"❌ Error sending cross-sell UI update: {e}")
            print(f"❌ A2UI Error: {e}")
            import traceback
            traceback.print_exc()
            
    async def send_loading_state(self, is_loading: bool, message: str = ""):
        """Update loading state in the UI"""
        await self.send_ui_update(
            action="update",
            component="crosssell_loading",
            data={
                "is_loading": is_loading,
                "message": message
            }
        )
        
    async def send_crosssell_products(self, products: List[Dict], product_id: str, total_count: int):
        """Send cross-sell products to UI"""
        print(f"\n📤 Sending {len(products)} cross-sell products via A2UI...")
        await self.send_ui_update(
            action="replace",
            component="crosssell_carousel",
            data={
                "products": products,
                "product_id": product_id,
                "total_count": total_count,
                "timestamp": datetime.utcnow().isoformat()
            },
            metadata={
                "source_product": product_id,
                "result_count": len(products)
            }
        )
        print(f"✅ Cross-sell products sent to A2UI server")
        
    async def send_error(self, error_message: str, error_type: str = "crosssell_error"):
        """Send error notification to UI"""
        await self.send_ui_update(
            action="update",
            component="crosssell_error",
            data={
                "has_error": True,
                "error_message": error_message,
                "error_type": error_type
            }
        )
        
    async def load_and_update_crosssell(self, product_id: str):
        """
        Load cross-sell products and send real-time updates via A2UI
        """
        try:
            print(f"🔗 Loading cross-sell products for product {product_id} via A2UI...")
            
            # Send loading state
            await self.send_loading_state(True, "Loading related products...")
            
            # Get cross-sell products from database
            from agent import hana_connect, get_cross_sell_products_for_search
            
            conn = hana_connect()
            cursor = conn.cursor()
            
            crosssell_products = get_cross_sell_products_for_search(
                [product_id], 
                conn, 
                cursor, 
                limit_per_product=6
            )
            
            cursor.close()
            conn.close()
            
            if crosssell_products and len(crosssell_products) > 0:
                print(f"✅ Found {len(crosssell_products)} cross-sell products")
                
                # Send products via A2UI
                await self.send_crosssell_products(
                    products=crosssell_products,
                    product_id=product_id,
                    total_count=len(crosssell_products)
                )
                
                # Clear loading state
                await self.send_loading_state(False)
                
                return {
                    'success': True,
                    'count': len(crosssell_products),
                    'products': crosssell_products
                }
            else:
                print(f"ℹ️ No cross-sell products found for {product_id}")
                
                # Send empty state
                await self.send_crosssell_products(
                    products=[],
                    product_id=product_id,
                    total_count=0
                )
                
                await self.send_loading_state(False)
                
                return {
                    'success': True,
                    'count': 0,
                    'products': []
                }
                
        except Exception as e:
            error_msg = f"Failed to load cross-sell products: {str(e)}"
            logger.error(error_msg)
            print(f"❌ {error_msg}")
            
            await self.send_error(error_msg)
            await self.send_loading_state(False)
            
            return {
                'success': False,
                'error': error_msg
            }


def load_crosssell_sync(product_id: str, session_id: str = None):
    """
    Synchronous wrapper for loading cross-sell products
    Compatible with Flask views
    """
    crosssell = ProductCrossSellA2UI(session_id=session_id)
    result = asyncio.run(crosssell.load_and_update_crosssell(product_id))
    return result
