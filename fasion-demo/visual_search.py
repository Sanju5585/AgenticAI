"""
AI Visual Search - Image-to-Product Search
Upload a photo and find visually similar products using AI

Search Strategy:
- Uses PRODUCT TYPE only (not category) for precise matching
- Example: "Sunglasses" (not "Accessories") to avoid returning wrong items like watches
- Falls back to keywords only if product type doesn't yield results
"""

import os
import base64
import io
import hashlib
from typing import List, Dict, Optional, Tuple
from PIL import Image
import numpy as np
import imagehash
from functools import lru_cache
import google.generativeai as genai
from urllib.parse import urlparse, urlunparse
from dotenv import load_dotenv

load_dotenv()

# Configure Google AI
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

GOOGLE_VISION_MODEL = os.getenv('GOOGLE_VISION_MODEL', 'gemini-2.5-flash-lite')
GOOGLE_VISION_FALLBACK_MODEL = os.getenv('GOOGLE_VISION_FALLBACK_MODEL', 'gemini-1.5-flash')
MEDIA_HOST_REWRITE = os.getenv('MEDIA_HOST_REWRITE') or os.getenv('OCC_BASE_URL')


class VisualSearchEngine:
    """
    AI-powered visual product search using image analysis.
    
    Features:
    - Image upload and processing
    - Visual similarity detection
    - Color-based matching
    - Object detection
    - Text extraction from images
    """
    
    def __init__(self):
        self.max_image_size = 4 * 1024 * 1024  # 4MB
        self.supported_formats = {'jpg', 'jpeg', 'png', 'webp', 'gif'}
        self.cache_dir = "image_cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        self.vision_model = GOOGLE_VISION_MODEL
        self.fallback_vision_model = GOOGLE_VISION_FALLBACK_MODEL
        self.media_host_rewrite = MEDIA_HOST_REWRITE
    
    def validate_image(self, image_data: bytes) -> Tuple[bool, str]:
        """Validate uploaded image."""
        if len(image_data) > self.max_image_size:
            return False, f"Image too large. Maximum size is {self.max_image_size // (1024*1024)}MB"
        
        try:
            image = Image.open(io.BytesIO(image_data))
            image_format = image.format.lower() if image.format else ''
            
            if image_format not in self.supported_formats:
                return False, f"Unsupported format. Use: {', '.join(self.supported_formats)}"
            
            return True, "Valid image"
        except Exception as e:
            return False, f"Invalid image: {str(e)}"
    
    def process_image(self, image_data: bytes) -> Dict:
        """Process image and extract features."""
        try:
            image = Image.open(io.BytesIO(image_data))
            
            # Resize for faster processing
            max_dimension = 1024
            if max(image.size) > max_dimension:
                ratio = max_dimension / max(image.size)
                new_size = tuple(int(dim * ratio) for dim in image.size)
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Extract features
            features = {
                'size': image.size,
                'mode': image.mode,
                'format': image.format,
                'dominant_colors': self._extract_dominant_colors(image),
                'perceptual_hash': str(imagehash.phash(image)),
                'average_hash': str(imagehash.average_hash(image)),
            }
            
            return features
            
        except Exception as e:
            print(f"Error processing image: {e}")
            return {}
    
    def _extract_dominant_colors(self, image: Image.Image, num_colors: int = 5) -> List[str]:
        """Extract dominant colors from image."""
        try:
            # Resize to speed up processing
            img_small = image.resize((100, 100))
            pixels = np.array(img_small).reshape(-1, 3)
            
            # Simple k-means-like color clustering
            from sklearn.cluster import KMeans
            kmeans = KMeans(n_clusters=min(num_colors, len(pixels)), random_state=42, n_init=10)
            kmeans.fit(pixels)
            
            # Get dominant colors
            colors = kmeans.cluster_centers_.astype(int)
            return [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in colors]
            
        except Exception as e:
            print(f"Error extracting colors: {e}")
            # Fallback to average color
            avg_color = np.array(image.resize((1, 1))).flatten()
            return [f"#{int(avg_color[0]):02x}{int(avg_color[1]):02x}{int(avg_color[2]):02x}"]
    
    def analyze_image_with_ai(self, image_data: bytes) -> Dict:
        """Analyze image using Google Gemini Vision AI."""
        try:
            image = Image.open(io.BytesIO(image_data))
            
            try:
                model = genai.GenerativeModel(self.vision_model)
            except Exception as model_error:
                print(f"⚠️ Vision model '{self.vision_model}' unavailable: {model_error}")
                if self.fallback_vision_model == self.vision_model:
                    raise
                print(f"🔁 Falling back to '{self.fallback_vision_model}'")
                model = genai.GenerativeModel(self.fallback_vision_model)
            
            prompt = """Analyze this product image and provide:
1. Product category (e.g., clothing, electronics, furniture)
2. Product type (e.g., t-shirt, laptop, chair)
3. Main colors (list top 3)
4. Key visual attributes (style, pattern, material)
5. Searchable keywords (5-10 words)

Format as JSON:
{
    "category": "...",
    "product_type": "...",
    "colors": ["...", "...", "..."],
    "attributes": ["...", "...", "..."],
    "keywords": ["...", "...", "..."]
}"""
            
            response = model.generate_content([prompt, image])
            
            # Parse JSON from response
            import json
            import re
            
            text = response.text
            # Extract JSON from markdown code blocks if present
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
            if json_match:
                text = json_match.group(1)
            
            analysis = json.loads(text)
            return analysis
            
        except Exception as e:
            print(f"AI analysis error: {e}")
            return {
                "category": "unknown",
                "product_type": "product",
                "colors": [],
                "attributes": [],
                "keywords": []
            }
    
    def search_similar_products(self, image_analysis: Dict, limit: int = 5) -> List[Dict]:
        """Search for products similar to the analyzed image using direct database query."""
        try:
            # Build search query from image analysis
            product_type = image_analysis.get('product_type', '')
            keywords = image_analysis.get('keywords', [])
            
            # Use product type as primary search term
            search_query = product_type if product_type and product_type.lower() not in ['unknown', 'product', 'item', 'object'] else ''
            
            if not search_query and keywords:
                search_query = keywords[0]
            
            if not search_query:
                return []
            
            print(f"🔍 Visual search - Searching database for: {search_query}")
            
            # Search directly in database
            results = self._search_database(search_query, limit)
            
            print(f"✅ Found {len(results)} products matching '{search_query}'")
            return results
            
        except Exception as e:
            print(f"Search error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _search_database(self, search_query: str, limit: int = 5) -> List[Dict]:
        """Search products directly from database."""
        from hdbcli import dbapi
        
        try:
            # Connect to HANA
            conn = dbapi.connect(
                address='794d7a51-4a96-4b97-a476-dacb3a0440b4.hna2.prod-eu10.hanacloud.ondemand.com',
                port='443',
                user='00F588CD78904954BA0FA8C9585A169F_8C04J77WXE7NPHALBEVGEC4AA_DT',
                password='Ae7Z34V2HG_8_j8r1kb_dWJsCGEnmE_nN0Z0cMULba.EdRcYbilznUf.bsX-ZJJ9q.9_13It90i_q3n8jSzE8zF_gfHbwEuE9LJos0bENwD2Q6YJjo_TlBICY23muSi.',
                encrypt=True,
                sslValidateCertificate=False
            )
            cursor = conn.cursor()
            
            # Build search query - use LIKE for text matching
            search_pattern = f"%{search_query}%"
            
            query = """
            SELECT 
                p.PRODUCT_ID,
                p.PRODUCT_NAME,
                p.SUMMARY,
                p.PRICE,
                p.IMAGE_URL,
                p.CATEGORY_IDs
            FROM 
                SAP_PRODUCTS_COMMERCE_2211_V2 p
            WHERE 
                LOWER(p.PRODUCT_NAME) LIKE LOWER(?) 
                OR LOWER(p.SUMMARY) LIKE LOWER(?)
            ORDER BY 
                CASE 
                    WHEN LOWER(p.PRODUCT_NAME) LIKE LOWER(?) THEN 1
                    ELSE 2
                END
            LIMIT ?
            """
            
            cursor.execute(query, (search_pattern, search_pattern, search_pattern, limit * 2))
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                if len(results) >= limit:
                    break

                product_id = str(row[0]).strip() if row[0] is not None else ''

                # Prefer local image over Hybris URL
                _base_dir = os.path.dirname(os.path.abspath(__file__))
                local_image_path = os.path.join(_base_dir, 'static', 'product_images', f'{product_id}.jpg')
                if os.path.exists(local_image_path):
                    image_url = f'/static/product_images/{product_id}.jpg'
                else:
                    image_url = self._normalize_image_url(row[4] or '')

                product = {
                    'PRODUCT_ID': product_id,
                    'PRODUCT_NAME': str(row[1]).strip() if row[1] is not None else '',
                    'SUMMARY': str(row[2]).strip() if row[2] is not None else '',
                    'PRICE': float(row[3]) if row[3] else 0.0,
                    'IMAGE_URL': image_url,
                    'image_url': image_url,  # Also include lowercase for frontend compatibility
                    'CATEGORY_IDs': str(row[5]).strip() if row[5] is not None else '',
                    'product_id': product_id,
                    'product_name': str(row[1]).strip() if row[1] is not None else '',
                    'summary': str(row[2]).strip() if row[2] is not None else '',
                    'price': float(row[3]) if row[3] else 0.0,
                    'similarity_score': 0.8,  # Default score for visual search matches
                    'relevance': 'high'
                }
                results.append(product)
            
            cursor.close()
            conn.close()
            
            return results
            
        except Exception as e:
            print(f"Database search error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _normalize_image_url(self, url: str) -> str:
        if not url or not self.media_host_rewrite:
            return url
        try:
            source = urlparse(url)
            target = urlparse(self.media_host_rewrite)
            if not target.scheme or not target.netloc:
                return url
            updated = source._replace(scheme=target.scheme, netloc=target.netloc)
            return urlunparse(updated)
        except Exception:
            return url
    
    def _rank_by_color_similarity(self, products: List[Dict], target_colors: List[str]) -> List[Dict]:
        """Re-rank products by color similarity."""
        # Simple color matching boost
        # In production, extract colors from product images
        for product in products:
            product['color_match_boost'] = 0.0
            product_name = product.get('product_name', '').lower()
            
            # Simple keyword matching for common colors
            for color in target_colors:
                color_name = color.lower()
                if any(c in product_name for c in ['red', 'blue', 'green', 'black', 'white', 'yellow']):
                    product['color_match_boost'] += 0.1
        
        return products
    
    def save_upload(self, image_data: bytes, filename: str) -> str:
        """Save uploaded image to cache."""
        try:
            # Generate unique filename
            file_hash = hashlib.md5(image_data).hexdigest()[:16]
            ext = filename.rsplit('.', 1)[-1] if '.' in filename else 'jpg'
            cache_filename = f"{file_hash}.{ext}"
            cache_path = os.path.join(self.cache_dir, cache_filename)
            
            # Save image
            with open(cache_path, 'wb') as f:
                f.write(image_data)
            
            return cache_filename
            
        except Exception as e:
            print(f"Error saving image: {e}")
            return ""


# Global instance
_visual_search_engine = None

def get_visual_search_engine():
    """Get or create visual search engine instance."""
    global _visual_search_engine
    if _visual_search_engine is None:
        _visual_search_engine = VisualSearchEngine()
    return _visual_search_engine


def search_by_image(image_data: bytes, filename: str = "upload.jpg", limit: int = 5) -> Dict:
    """
    Main function: Search products by uploaded image.
    
    Args:
        image_data: Binary image data
        filename: Original filename
        limit: Maximum results (default 5)
        
    Returns:
        Dictionary with results and metadata
    """
    engine = get_visual_search_engine()
    
    # Validate image
    valid, message = engine.validate_image(image_data)
    if not valid:
        return {
            "success": False,
            "error": message,
            "results": []
        }
    
    # Save uploaded image
    cache_filename = engine.save_upload(image_data, filename)
    
    # Process image
    features = engine.process_image(image_data)
    
    # AI analysis
    print("🤖 Analyzing image with AI...")
    analysis = engine.analyze_image_with_ai(image_data)
    
    # Search similar products
    print("🔍 Searching similar products...")
    results = engine.search_similar_products(analysis, limit=limit)
    
    return {
        "success": True,
        "image_cache": cache_filename,
        "analysis": analysis,
        "features": features,
        "results": results,
        "count": len(results),
        "query_generated": analysis.get('product_type', 'unknown')
    }
