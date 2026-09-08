"""
What's New Carousel A2UI Module
Handles What's New product carousel with A2UI Protocol integration
for real-time UI updates and dynamic content injection.

Implementation Steps:
1. Get data from Hybris OCC API
2. Generate A2UI JSON using Gemini model automatically
3. Render JSON using UI framework via A2UI protocol
"""

import asyncio
import httpx
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import google.generativeai as genai

logger = logging.getLogger(__name__)

# A2UI Server Configuration
A2UI_SERVER_URL = os.getenv("A2UI_SERVER_URL", "http://localhost:8020")

# Configure Gemini API
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

class WhatsNewCarouselA2UI:
    """
    What's New Carousel module with A2UI Protocol integration
    
    Implementation Flow:
    1. Fetch products from Hybris OCC API
    2. Use Gemini AI to generate optimized A2UI JSON structure
    3. Send A2UI JSON to frontend via WebSocket for rendering
    """
    
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id
        self.module_name = "whats_new_carousel"
        self.gemini_model = None
        if GOOGLE_API_KEY:
            try:
                self.gemini_model = genai.GenerativeModel('gemini-2.5-flash-lite')
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini model: {e}")
    
    async def generate_a2ui_json_with_gemini(self, products: List[Dict]) -> Dict[str, Any]:
        """
        Step 2: Generate A2UI JSON using Gemini model automatically
        
        Takes raw product data and generates optimized UI structure
        using AI to create engaging, user-friendly carousel layout.
        
        Raises exception if Gemini model is unavailable.
        """
        if not self.gemini_model:
            error_msg = "Gemini AI model is required but not available. Please check GOOGLE_API_KEY configuration."
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        try:
            # Debug: Print products being sent to Gemini
            print(f"\n📊 Products sent to Gemini for A2UI generation:")
            for i, p in enumerate(products[:3], 1):
                print(f"   {i}. {p.get('name', 'Unknown')[:40]}")
                print(f"      Image: {p.get('image', 'NO IMAGE')[:80]}")
                print(f"      Price: £{p.get('price', 0):.2f}")
            
            # Prepare prompt for Gemini to generate A2UI JSON
            prompt = f"""You are a UI/UX expert. Generate an optimized A2UI JSON structure for a "What's New" product carousel.

Product Data:
{json.dumps(products, indent=2)}

CRITICAL REQUIREMENTS:
1. Use the EXACT image URL from each product's "image" field - DO NOT modify or create fake URLs
2. Create a modern, engaging carousel layout
3. Highlight key product features (name, price, image)
4. Include interactive elements (click actions, hover effects)
5. Ensure mobile-responsive design
6. Add visual appeal with proper spacing and typography

Generate a JSON structure with this format:
{{
  "component_type": "carousel",
  "layout": "horizontal_scroll",
  "title": "What's New",
  "items": [
    {{
      "id": "USE EXACT product id from data",
      "type": "product_card",
      "content": {{
        "image": "USE EXACT image URL from product data - DO NOT CREATE FAKE URLs",
        "title": "product name",
        "price": "£XX.XX formatted price",
        "badge": "NEW",
        "action": "view_details"
      }},
      "styling": {{
        "card_style": "modern",
        "hover_effect": "lift",
        "animation": "fade-in"
      }}
    }}
  ],
  "controls": {{
    "show_navigation": true,
    "auto_scroll": true,
    "scroll_interval": 5000
  }},
  "styling": {{
    "theme": "light",
    "card_spacing": "medium",
    "show_indicators": true
  }}
}}

CRITICAL: Return ONLY valid JSON. Use the EXACT image URLs from the product data provided above. Do not create placeholder or example URLs."""

            # Run Gemini generation in thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.gemini_model.generate_content(prompt)
            )
            
            # Parse Gemini response
            generated_text = response.text.strip()
            
            # Clean up markdown formatting if present
            if generated_text.startswith("```json"):
                generated_text = generated_text.replace("```json", "").replace("```", "").strip()
            elif generated_text.startswith("```"):
                generated_text = generated_text.replace("```", "").strip()
            
            a2ui_json = json.loads(generated_text)
            
            # Debug: Print the generated A2UI JSON
            print(f"\n🤖 GEMINI GENERATED A2UI JSON:")
            print("=" * 80)
            print(json.dumps(a2ui_json, indent=2))
            print("=" * 80)
            
            # Validate that images are present
            items = a2ui_json.get('items', [])
            print(f"\n✅ Generated {len(items)} carousel items")
            
            # Fix any incorrect image URLs by matching with original product data
            fixed_count = 0
            for i, item in enumerate(items):
                img_url = item.get('content', {}).get('image', '')
                item_id = item.get('id', '')
                
                # Find matching product by ID
                matching_product = next((p for p in products if p.get('id') == item_id), None)
                
                if matching_product:
                    correct_image = matching_product.get('image', '')
                    current_image = item.get('content', {}).get('image', '')
                    
                    # If Gemini used wrong URL, fix it
                    if current_image != correct_image:
                        print(f"   🔧 Fixing image for item {i+1}: {item.get('content', {}).get('title', 'Unknown')[:40]}")
                        print(f"      Wrong: {current_image[:60]}")
                        print(f"      Fixed: {correct_image[:60]}")
                        item['content']['image'] = correct_image
                        fixed_count += 1
                    else:
                        print(f"   ✅ Item {i+1}: Image OK - {current_image[:60]}")
            
            if fixed_count > 0:
                print(f"\n⚠️ Fixed {fixed_count} incorrect image URLs from Gemini")
            
            logger.info("✅ Successfully generated A2UI JSON with Gemini")
            print(f"\n🎯 Gemini generated A2UI structure with {len(items)} items")
            
            return a2ui_json
            
        except Exception as e:
            logger.error(f"Error generating A2UI JSON with Gemini: {e}")
            print(f"❌ Gemini generation failed: {e}")
            raise
        
    async def send_a2ui_json_to_frontend(self, a2ui_json: Dict[str, Any]):
        """
        Step 3: Send A2UI JSON to frontend for rendering via UI framework
        
        Sends the complete A2UI structure to frontend WebSocket connection
        for automatic UI rendering.
        """
        await self.send_ui_update(
            action="render",
            component="whats_new_carousel_a2ui",
            data={
                "a2ui_json": a2ui_json,
                "timestamp": datetime.utcnow().isoformat(),
                "session_id": self.session_id
            },
            metadata={
                "generated_by": "gemini",
                "component_type": a2ui_json.get("component_type"),
                "item_count": len(a2ui_json.get("items", []))
            }
        )
        print(f"📤 Sent A2UI JSON to frontend for rendering ({len(a2ui_json.get('items', []))} items)")
        
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
                
                print(f"📤 Sending A2UI update to {endpoint}")
                print(f"   Component: {component}, Action: {action}")
                print(f"   Data keys: {list(data.keys())}")
                
                if component == "whats_new_carousel" and "products" in data:
                    print(f"   📊 Sending {len(data['products'])} products in legacy format")
                elif component == "whats_new_carousel_a2ui" and "a2ui_json" in data:
                    print(f"   🎨 Sending A2UI JSON with {len(data['a2ui_json'].get('items', []))} items")
                
                response = await client.post(endpoint, json=payload, timeout=5.0)
                if response.status_code == 200:
                    logger.info(f"✅ UI update sent: {action} -> {component}")
                    print(f"✅ A2UI update successful: {component}")
                else:
                    logger.warning(f"⚠️ UI update failed: {response.status_code}")
                    print(f"⚠️ A2UI server returned: {response.status_code}")
                    print(f"   Response: {response.text}")
                    
        except Exception as e:
            logger.error(f"❌ Error sending UI update: {e}")
            print(f"❌ Failed to send A2UI update: {e}")
            import traceback
            traceback.print_exc()
            # Don't fail the main operation if UI update fails
            
    async def send_loading_state(self, is_loading: bool):
        """Update loading state in the carousel"""
        await self.send_ui_update(
            action="update",
            component="carousel_loading",
            data={
                "is_loading": is_loading
            }
        )
        
    async def send_carousel_products(self, products: List[Dict]):
        """Send products to carousel for rendering - Legacy format for backward compatibility"""
        
        # Transform products to match frontend expectations
        formatted_products = []
        for p in products:
            formatted_products.append({
                "product_id": p.get("id", ""),
                "product_name": p.get("name", ""),
                "summary": p.get("description", ""),
                "price": p.get("price", 0.0),
                "image_url": p.get("image", ""),
                "rating": p.get("averageRating"),
                "url": p.get("url", "")
            })
        
        print(f"\n📦 Sending legacy carousel format:")
        print(f"   First product: {formatted_products[0].get('product_name', 'Unknown')[:40]}")
        print(f"   Image URL: {formatted_products[0].get('image_url', 'NO IMAGE')[:80]}")
        
        await self.send_ui_update(
            action="replace",
            component="whats_new_carousel",
            data={
                "products": formatted_products,
                "timestamp": datetime.utcnow().isoformat(),
                "total_count": len(formatted_products)
            },
            metadata={
                "carousel_type": "whats_new",
                "product_count": len(formatted_products)
            }
        )
        
    async def send_error(self, error_message: str):
        """Send error notification"""
        await self.send_ui_update(
            action="update",
            component="carousel_error",
            data={
                "has_error": True,
                "error_message": error_message
            }
        )
        
    async def send_toast(self, message: str, toast_type: str = "info"):
        """Send toast notification"""
        try:
            async with httpx.AsyncClient() as client:
                endpoint = f"{A2UI_SERVER_URL}/api/ui/command"
                
                payload = {
                    "module": self.module_name,
                    "command": "show_toast",
                    "params": {
                        "message": message,
                        "type": toast_type,
                        "duration": 3000
                    }
                }
                
                response = await client.post(endpoint, json=payload, timeout=5.0)
                if response.status_code == 200:
                    logger.info(f"✅ Toast sent: {message}")
                    
        except Exception as e:
            logger.error(f"❌ Error sending toast: {e}")
            
    async def load_and_update_carousel(self):
        """
        Main orchestration method implementing the 3-step process:
        
        Step 1: Get data from Hybris OCC API
        Step 2: Generate A2UI JSON using Gemini model automatically
        Step 3: Render JSON using UI framework via A2UI protocol
        """
        try:
            # Send loading state immediately
            await self.send_loading_state(True)
            print("🔄 Step 1: Fetching products from Hybris OCC API...")
            
            # STEP 1: Get data from Hybris OCC API
            from tools.hybris_occ import get_whats_new_products
            
            # Get products from Hybris OCC (run in thread pool to avoid blocking)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, get_whats_new_products, 8)
            
            if result.get("error"):
                # Send all error updates in parallel
                await asyncio.gather(
                    self.send_loading_state(False),
                    self.send_error(result["error"]),
                    self.send_toast(f"Failed to load new products: {result['error']}", "error")
                )
                return {"success": False, "error": result["error"]}
            
            # Transform products for processing
            raw_products = result.get("results", [])
            products = []
            for product in raw_products:
                image_url = product.get("image", "")
                
                # Debug logging for image URLs
                print(f"   Product: {product.get('name', 'Unknown')[:30]}")
                print(f"   Image URL: {image_url[:100] if image_url else 'NO IMAGE'}")
                
                # Ensure we have a valid image URL or use placeholder
                if not image_url or image_url == "":
                    image_url = "/static/assets/product-placeholder.svg"
                    print(f"   ⚠️ Using placeholder for missing image")
                
                products.append({
                    "id": product.get("id", ""),
                    "name": product.get("name", ""),
                    "description": product.get("description", ""),
                    "price": product.get("price", 0.0),
                    "image": image_url,
                    "averageRating": product.get("averageRating"),
                    "url": product.get("url", "")
                })
            
            print(f"✅ Step 1 Complete: Retrieved {len(products)} products from Hybris OCC")
            
            # Validate and log product data before sending to Gemini
            print(f"\n📋 Product Data Validation:")
            for i, p in enumerate(products, 1):
                has_image = bool(p.get("image") and p.get("image") != "/static/assets/product-placeholder.svg")
                status = "✅" if has_image else "⚠️"
                print(f"   {status} Product {i}: {p.get('name', 'Unknown')[:40]} - Image: {has_image}")
            
            # STEP 2: Generate A2UI JSON using Gemini model automatically
            print("\n🤖 Step 2: Generating A2UI JSON structure with Gemini AI...")
            a2ui_json = await self.generate_a2ui_json_with_gemini(products)
            print(f"✅ Step 2 Complete: Generated A2UI JSON structure")
            
            # STEP 3: Send A2UI JSON to frontend for rendering
            print("📤 Step 3: Sending A2UI JSON to frontend via WebSocket...")
            await self.send_a2ui_json_to_frontend(a2ui_json)
            print(f"✅ Step 3 Complete: A2UI JSON sent to frontend for rendering")
            
            # Also send legacy format for backward compatibility
            await asyncio.gather(
                self.send_loading_state(False),
                self.send_carousel_products(products),
                self.send_toast(f"Loaded {len(products)} new arrivals!", "success")
            )
            
            return {
                "success": True,
                "products": products,
                "count": len(products),
                "a2ui_json": a2ui_json,
                "generated_with_gemini": True
            }
            
        except Exception as e:
            logger.error(f"❌ Error loading carousel: {e}")
            import traceback
            traceback.print_exc()
            # Send error updates in parallel
            await asyncio.gather(
                self.send_loading_state(False),
                self.send_error(str(e)),
                self.send_toast(f"Error: {str(e)}", "error")
            )
            return {"success": False, "error": str(e)}


# Synchronous wrapper for Flask compatibility
def load_whats_new_carousel_sync(session_id: Optional[str] = None):
    """Synchronous wrapper to load What's New carousel"""
    carousel = WhatsNewCarouselA2UI(session_id)
    return asyncio.run(carousel.load_and_update_carousel())
