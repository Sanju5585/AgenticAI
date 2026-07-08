"""
AI Visual Search - Image-to-Product Search
Upload a photo and find visually similar products using AI

Search Strategy:
- Uses PRODUCT TYPE with semantic vector search for precise matching
- Example: "Smartwatch" finds all smartwatches using AI embeddings
- Semantic search finds products based on meaning, not just text matching
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

# Import embedding function for semantic search
from ecom_llm import get_google_embedding

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
1. Product category - must match Meijer grocery store categories such as: Frozen, IceCream, FrozenMeals, FrozenPizzas, Snacks, Chips, Crackers, Cookies, Bakery, Bread, CustomCakes, Beverages, SoftDrinks, Water, Coffee, CerealBreakfast, Dairy, Milk, Yogurt, Cheese
2. Product type (e.g., ice cream, pizza, yogurt, chips, bread, coffee, cereal)
3. Main colors (list top 3)
4. Key visual attributes (style, packaging, brand if visible)
5. Searchable keywords (5-10 words relevant to Meijer grocery products)

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
        """Search for products similar to the analyzed image using semantic vector search."""
        try:
            # Use ONLY product type for semantic search (most accurate)
            product_type = image_analysis.get('product_type', '').strip()
            
            if not product_type or product_type.lower() in ['unknown', 'product', 'item', 'object']:
                # Fallback to first keyword if product type is generic
                keywords = image_analysis.get('keywords', [])
                if keywords and isinstance(keywords, list):
                    product_type = keywords[0]
                else:
                    return []
            
            print("="*80)
            print(f"🔍 VISUAL SEARCH - HANA DB QUERY")
            print(f"📦 Table: SAP_MEIJER_PRODUCTS_V1")
            print(f"🎯 Product Type Detected: '{product_type}'")
            print(f"🔢 Limit: {limit} products")
            print("="*80)
            
            # Generate embedding for semantic search
            try:
                print(f"⚙️  Generating AI embedding for '{product_type}'...")
                query_embedding = get_google_embedding(product_type)
                if not query_embedding:
                    print("⚠️ Failed to generate embedding, using text fallback")
                    return self._search_database_text_fallback(product_type, limit)
                
                print(f"✅ Generated {len(query_embedding)}-dimensional embedding")
                print(f"🔎 Executing SEMANTIC VECTOR SEARCH on HANA database...")
                
                # Search using semantic vectors
                results = self._search_database_semantic(query_embedding, product_type, limit)
                
                if results:
                    print(f"✅ HANA DB returned {len(results)} products via SEMANTIC SEARCH")
                    print("📋 Products found:")
                    for i, r in enumerate(results, 1):
                        print(f"   {i}. {r.get('product_name', 'N/A')} - ${r.get('price', 0)} (Score: {r.get('similarity_score', 0):.3f})")
                else:
                    print("⚠️ No results from semantic search, trying text fallback...")
                    results = self._search_database_text_fallback(product_type, limit)
                    if results:
                        print(f"✅ HANA DB returned {len(results)} products via TEXT SEARCH")
                
            except Exception as embed_error:
                print(f"⚠️ Embedding error: {embed_error}, using text fallback")
                results = self._search_database_text_fallback(product_type, limit)
            
            print(f"✅ Found {len(results)} products matching '{product_type}'")
            return results
            
        except Exception as e:
            print(f"Search error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    
    def _search_database_semantic(self, query_embedding: List[float], search_term: str, limit: int = 5) -> List[Dict]:
        """Search products using semantic vector search with embeddings."""
        from hdbcli import dbapi
        
        try:
            print(f"🔌 Connecting to HANA Cloud database...")
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
            print(f"✅ Connected to HANA successfully")
            
            # Convert embedding to HANA vector format
            query_vector_str = "[" + ",".join(map(str, query_embedding)) + "]"
            
            # Semantic search using vector similarity
            query = """
            SELECT 
                p.PRODUCT_ID,
                p.PRODUCT_NAME,
                p.SUMMARY,
                p.PRICE,
                p.IMAGE_URL,
                p.CATEGORY_IDS,
                COSINE_SIMILARITY(p.VECTOR_NAME, TO_REAL_VECTOR(?)) AS NAME_SIM,
                COSINE_SIMILARITY(p.VECTOR_SUMMARY, TO_REAL_VECTOR(?)) AS DESC_SIM,
                (COSINE_SIMILARITY(p.VECTOR_NAME, TO_REAL_VECTOR(?)) * 0.7 +
                 COSINE_SIMILARITY(p.VECTOR_SUMMARY, TO_REAL_VECTOR(?)) * 0.3) AS SIMILARITY_SCORE
            FROM 
                SAP_MEIJER_PRODUCTS_V1 p
            WHERE 
                p.VECTOR_NAME IS NOT NULL 
                AND p.VECTOR_SUMMARY IS NOT NULL
            ORDER BY 
                SIMILARITY_SCORE DESC
            LIMIT ?
            """
            
            print(f"🎯 Executing COSINE_SIMILARITY query on SAP_MEIJER_PRODUCTS_V1")
            print(f"📊 Searching for: '{search_term}'")
            cursor.execute(query, (query_vector_str, query_vector_str, query_vector_str, query_vector_str, limit * 2))
            rows = cursor.fetchall()
            print(f"📦 HANA returned {len(rows)} rows")
            
            results = []
            for row in rows:
                if len(results) >= limit:
                    break
                    
                # Use image URL directly from SAP_MEIJER_PRODUCTS_V1 table (row[4])
                image_url = str(row[4]).strip() if row[4] is not None else ''
                
                product = {
                    'PRODUCT_ID': str(row[0]).strip() if row[0] is not None else '',
                    'PRODUCT_NAME': str(row[1]).strip() if row[1] is not None else '',
                    'SUMMARY': str(row[2]).strip() if row[2] is not None else '',
                    'PRICE': float(row[3]) if row[3] else 0.0,
                    'IMAGE_URL': image_url,
                    'image_url': image_url,
                    'CATEGORY_IDS': str(row[5]).strip() if row[5] is not None else '',
                    'product_id': str(row[0]).strip() if row[0] is not None else '',
                    'product_name': str(row[1]).strip() if row[1] is not None else '',
                    'summary': str(row[2]).strip() if row[2] is not None else '',
                    'price': float(row[3]) if row[3] else 0.0,
                    'similarity_score': float(row[8]) if row[8] else 0.0,
                    'name_similarity': float(row[6]) if row[6] else 0.0,
                    'desc_similarity': float(row[7]) if row[7] else 0.0,
                    'relevance': 'high',
                    'data_source': 'SAP HANA Cloud',
                    'table_name': 'SAP_MEIJER_PRODUCTS_V1',
                    'search_method': 'semantic_vector'
                }
                results.append(product)
                
                print(f"  ✓ {product['product_name']} - ${product['price']} (Score: {product['similarity_score']:.3f}) [IMG: {image_url[:50] if image_url else 'NONE'}...]")
            
            cursor.close()
            conn.close()
            
            return results
            
        except Exception as e:
            print(f"Semantic search error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _search_database_text_fallback(self, search_query: str, limit: int = 5) -> List[Dict]:
        """Fallback text-based search when embeddings are unavailable."""
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
            
            # Build search pattern
            search_pattern = f"%{search_query}%"
            
            query = """
            SELECT 
                p.PRODUCT_ID,
                p.PRODUCT_NAME,
                p.SUMMARY,
                p.PRICE,
                p.IMAGE_URL,
                p.CATEGORY_IDS
            FROM 
                SAP_MEIJER_PRODUCTS_V1 p
            WHERE 
                LOWER(p.PRODUCT_NAME) LIKE LOWER(?) 
                OR LOWER(p.SUMMARY) LIKE LOWER(?)
            ORDER BY 
                CASE 
                    WHEN LOWER(p.PRODUCT_NAME) LIKE LOWER(?) THEN 1
                    ELSE 2
                END,
                p.PRICE ASC
            LIMIT ?
            """
            
            print(f"🔍 Text fallback search for: '{search_query}'")
            cursor.execute(query, (search_pattern, search_pattern, search_pattern, limit * 2))
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                if len(results) >= limit:
                    break
                    
                # Use image URL directly from SAP_MEIJER_PRODUCTS_V1 table (row[4])
                image_url = str(row[4]).strip() if row[4] is not None else ''
                
                product = {
                    'PRODUCT_ID': str(row[0]).strip() if row[0] is not None else '',
                    'PRODUCT_NAME': str(row[1]).strip() if row[1] is not None else '',
                    'SUMMARY': str(row[2]).strip() if row[2] is not None else '',
                    'PRICE': float(row[3]) if row[3] else 0.0,
                    'IMAGE_URL': image_url,
                    'image_url': image_url,
                    'CATEGORY_IDS': str(row[5]).strip() if row[5] is not None else '',
                    'product_id': str(row[0]).strip() if row[0] is not None else '',
                    'product_name': str(row[1]).strip() if row[1] is not None else '',
                    'summary': str(row[2]).strip() if row[2] is not None else '',
                    'price': float(row[3]) if row[3] else 0.0,
                    'similarity_score': 0.7,
                    'relevance': 'medium',
                    'data_source': 'SAP HANA Cloud',
                    'table_name': 'SAP_MEIJER_PRODUCTS_V1',
                    'search_method': 'text_fallback'
                }
                results.append(product)
            
            cursor.close()
            conn.close()
            
            return results
            
        except Exception as e:
            print(f"Text fallback search error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _normalize_image_url(self, url: str) -> str:
        """DEPRECATED: Return image URL directly from database without any modification."""
        # No normalization, rewriting, or fallback - use database URL as-is
        return str(url).strip() if url else ''
    
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
    
    # Determine search method used
    search_method = 'unknown'
    if results and len(results) > 0:
        search_method = results[0].get('search_method', 'unknown')
    
    print(f"✅ Visual search complete - {len(results)} products from HANA DB")
    
    return {
        "success": True,
        "image_cache": cache_filename,
        "analysis": analysis,
        "features": features,
        "results": results,
        "count": len(results),
        "query_generated": analysis.get('product_type', 'unknown'),
        "database_source": "SAP HANA Cloud",
        "table_name": "SAP_MEIJER_PRODUCTS_V1",
        "search_method": search_method
    }
