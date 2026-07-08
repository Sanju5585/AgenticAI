# app/tools/hybris_occ.py
import os
import re
from typing import Dict, List
import requests


def _clean_html(text: str) -> str:
    """Remove HTML tags and decode HTML entities from text"""
    if not text:
        return text
    
    # Remove HTML tags like <em class="search-results-highlight">
    text = re.sub(r'<[^>]+>', '', text)
    
    # Decode common HTML entities
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
    
    return text.strip()


def _resolve_site() -> str:
    """
    Reads OCC_SITES and returns the first site ID.
    Falls back to 'electronics-spa' if not provided.
    Examples:
      OCC_SITES=electronics-spa
      OCC_SITES=apparel-uk-spa,electronics-spa
    """
    raw = (os.getenv("OCC_SITES") or "").strip()
    if not raw:
        return "electronics-spa"
    # split by comma/whitespace, pick first non-empty token
    for token in [t.strip() for t in raw.replace(";", ",").split(",")]:
        if token:
            return token
    return "electronics-spa"


def _headers():
    headers = {"Accept": "application/json"}
    bearer = os.getenv("OCC_BEARER_TOKEN")
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    return headers


def _with_access_token(url: str) -> str:
    at = os.getenv("OCC_ACCESS_TOKEN")
    if at:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}access_token={at}"
    return url


def _build_search_url(base_url: str, site: str) -> str:
    """
    Build a correct OCC search URL whether OCC_BASE_URL already includes '/occ/v2' or not.

    If OCC_BASE_URL = https://localhost:9002/occ/v2
      -> https://localhost:9002/occ/v2/{site}/products/search

    If OCC_BASE_URL = https://localhost:9002
      -> https://localhost:9002/occ/v2/{site}/products/search
    """
    base = (base_url or "").rstrip("/")
    if not base:
        raise RuntimeError("OCC_BASE_URL not configured")

    # If base already ends with /occ/v2, don't append it again
    if base.lower().endswith("/occ/v2"):
        return f"{base}/{site}/products/search"
    else:
        return f"{base}/occ/v2/{site}/products/search"


def search_products_basic(query: str, page_size: int = 12) -> Dict:
    """
    Basic OCC product search without fallback - returns database results only.
    Returns {"results": [ {id,name,description,price,image}, ... ]} or error message
    """
    base_url = os.getenv("OCC_BASE_URL")
    if not base_url:
        return {"results": [], "error": "Database connection not configured. Please configure OCC_BASE_URL environment variable."}
    
    site = _resolve_site()
    url = _build_search_url(base_url, site)

    params = {
        "query": query or "",
        "fields": "FULL",
        "pageSize": page_size,
        "currentPage": 0,
        "lang": "en",
        "sort": "relevance"  # Sort by relevance to get best matches first
    }

    url = _with_access_token(url)
    
    try:
        # Disable SSL verification for local development
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        resp = requests.get(
            url, 
            params=params, 
            headers=_headers(), 
            timeout=20,
            verify=False  # Disable SSL certificate verification
        )
        
        resp.raise_for_status()
        data = resp.json() or {}
        
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to OCC API: {e}")
        # Return empty results with clear error message - no fallback
        return {"results": [], "error": f"Database connection failed: {str(e)}"}
    except Exception as e:
        print(f"Unexpected error in product search: {e}")
        return {"results": [], "error": f"Search failed: {str(e)}"}

    products: List[dict] = []

    for p in data.get("products", []):
        # choose image: prefer 'product', then 'thumbnail', else first
        img = ""
        images = p.get("images") or []
        preferred = None
        for im in images:
            if str(im.get("format", "")).lower() == "product":
                preferred = im
                break
        if not preferred and images:
            preferred = next(
                (im for im in images if str(im.get("format", "")).lower() == "thumbnail"),
                images[0],
            )
        if preferred:
            img = preferred.get("url") or ""

        # price
        price_val = None
        price_obj = p.get("price") or {}
        if isinstance(price_obj, dict):
            price_val = price_obj.get("value")
        try:
            price = float(price_val) if price_val is not None else 0.0
        except Exception:
            price = 0.0

        # Fix relative image URLs to be absolute
        if img and img.startswith("/medias/"):
            img = f"{base_url}{img}"

        # Clean HTML markup from name and description
        clean_name = _clean_html(p.get("name") or "Product")
        clean_description = _clean_html(p.get("summary") or "")

        products.append(
            {
                "id": p.get("code") or "",
                "name": clean_name,
                "description": clean_description,
                "price": price,
                "image": img,
            }
        )

    # Return results or clear message if no products found
    if not products:
        return {"results": [], "error": f"No products found in database for query: '{query}'"}
    
    return {"results": products}


def search_products(query: str, page_size: int = 12) -> Dict:
    """
    Intelligent product search that combines OCC API with smart filtering.
    Returns database results only - no fallback mock data.
    """
    from tools.query_parser import (
        query_parser, build_search_query, filter_products_by_criteria
    )
    
    try:
        # Parse the query to extract filters
        filters = query_parser.parse_query(query)
        print(f"Parsed filters: {filters.to_dict()}")  # Debug logging
        
        # Build a search query from the parsed filters
        search_query = build_search_query(filters)
        print(f"Search query: '{search_query}'")  # Debug logging
        
        # Call the basic OCC search with the refined query
        result = search_products_basic(search_query, page_size * 2)  # Get more to filter
        
        # If there's an error from basic search, return it
        if result.get('error'):
            return result
        
        # Apply intelligent filtering based on parsed criteria
        if result.get('results'):
            filtered_products = filter_products_by_criteria(result.get('results', []), filters)
            result['results'] = filtered_products[:page_size]
            result['filters_applied'] = filters.to_dict()
            result['search_query'] = search_query
            
            # If filtering removed all products, return appropriate message
            if not result['results']:
                return {"results": [], "error": f"No products found in database matching your criteria for: '{query}'"}
        
        return result
        
    except Exception as e:
        print(f"Error in intelligent search: {e}")
        return {"results": [], "error": f"Search processing failed: {str(e)}"}


def get_homepage_structure() -> Dict:
    """
    Get homepage CMS structure to find carousel components.
    Returns database results only - no fallback mock data.
    """
    base_url = os.getenv("OCC_BASE_URL")
    if not base_url:
        return {"homepage": {}, "error": "Database connection not configured. Please configure OCC_BASE_URL environment variable."}
    
    site = _resolve_site()
    base = base_url.rstrip("/")
    
    # Build URL for CMS pages endpoint
    if base.lower().endswith("/occ/v2"):
        url = f"{base}/{site}/cms/pages"
    else:
        url = f"{base}/occ/v2/{site}/cms/pages"
    
    params = {
        "type": "ContentPage",
        "labelOrId": "homepage", 
        "fields": "FULL"
    }
    
    url = _with_access_token(url)
    
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        resp = requests.get(
            url,
            params=params,
            headers=_headers(),
            timeout=20,
            verify=False
        )
        
        resp.raise_for_status()
        data = resp.json() or {}
        
        return {"homepage": data, "error": None}
        
    except requests.exceptions.RequestException as e:
        print(f"Error getting homepage structure: {e}")
        return {"homepage": {}, "error": f"Database connection failed: {str(e)}"}
    except Exception as e:
        print(f"Unexpected error in homepage structure: {e}")
        return {"homepage": {}, "error": f"Homepage retrieval failed: {str(e)}"}


def get_carousel_component(component_uid: str) -> Dict:
    """
    Get specific CMS carousel component by UID.
    Returns database results only - no fallback mock data.
    """
    base_url = os.getenv("OCC_BASE_URL")
    if not base_url or not component_uid:
        return {"component": {}, "error": "Database connection not configured or component UID missing."}
    
    site = _resolve_site()
    base = base_url.rstrip("/")
    
    # Build URL for CMS component endpoint
    if base.lower().endswith("/occ/v2"):
        url = f"{base}/{site}/cms/components/{component_uid}"
    else:
        url = f"{base}/occ/v2/{site}/cms/components/{component_uid}"
    
    params = {"fields": "DEFAULT"}
    url = _with_access_token(url)
    
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        resp = requests.get(
            url,
            params=params,
            headers=_headers(),
            timeout=20,
            verify=False
        )
        
        resp.raise_for_status()
        data = resp.json() or {}
        
        return {"component": data, "error": None}
        
    except requests.exceptions.RequestException as e:
        print(f"Error getting carousel component: {e}")
        return {"component": {}, "error": f"Database connection failed: {str(e)}"}
    except Exception as e:
        print(f"Unexpected error in carousel component: {e}")
        return {"component": {}, "error": f"Component retrieval failed: {str(e)}"}


def get_product_by_code(product_code: str) -> Dict:
    """
    Get individual product by code.
    Returns database results only - no fallback mock data.
    """
    base_url = os.getenv("OCC_BASE_URL")
    if not base_url or not product_code:
        return {"product": {}, "error": "Database connection not configured or product code missing."}
    
    site = _resolve_site()
    base = base_url.rstrip("/")
    
    # Build URL for product endpoint
    if base.lower().endswith("/occ/v2"):
        url = f"{base}/{site}/products/{product_code}"
    else:
        url = f"{base}/occ/v2/{site}/products/{product_code}"
    
    params = {"fields": "code,name,price,images,averageRating,url,summary"}
    url = _with_access_token(url)
    
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        resp = requests.get(
            url,
            params=params,
            headers=_headers(),
            timeout=20,
            verify=False
        )
        
        resp.raise_for_status()
        data = resp.json() or {}
        
        return {"product": data, "error": None}
        
    except requests.exceptions.RequestException as e:
        print(f"Error getting product by code: {e}")
        return {"product": {}, "error": f"Database connection failed: {str(e)}"}
    except Exception as e:
        print(f"Unexpected error in product by code: {e}")
        return {"product": {}, "error": f"Product retrieval failed: {str(e)}"}


def search_products_by_category(category_code: str, page_size: int = 8) -> Dict:
    """
    Search products by category.
    Returns database results only - no fallback mock data.
    """
    base_url = os.getenv("OCC_BASE_URL")
    if not base_url:
        return {"products": [], "pagination": {}, "error": "Database connection not configured."}
    
    site = _resolve_site()
    url = _build_search_url(base_url, site)

    params = {
        "query": f":relevance:category:{category_code}" if category_code else ":relevance",
        "fields": "products(code,name,price,images,averageRating,url,summary)",
        "pageSize": page_size,
        "currentPage": 0,
        "lang": "en"
    }

    url = _with_access_token(url)
    
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        resp = requests.get(
            url, 
            params=params, 
            headers=_headers(), 
            timeout=20,
            verify=False
        )
        
        resp.raise_for_status()
        data = resp.json() or {}
        
        # Transform to our standard format
        products = []
        for p in data.get("products", []):
            # Handle images
            img = ""
            images = p.get("images") or []
            preferred = None
            for im in images:
                if str(im.get("format", "")).lower() == "product":
                    preferred = im
                    break
            if not preferred and images:
                preferred = next(
                    (im for im in images if str(im.get("format", "")).lower() == "thumbnail"),
                    images[0],
                )
            if preferred:
                img = preferred.get("url") or ""
                
            # Fix relative image URLs to be absolute
            if img and img.startswith("/medias/"):
                img = f"{base_url}{img}"
            
            # Handle price
            price_val = None
            price_obj = p.get("price") or {}
            if isinstance(price_obj, dict):
                price_val = price_obj.get("value")
            try:
                price = float(price_val) if price_val is not None else 0.0
            except Exception:
                price = 0.0

            # Clean HTML markup
            clean_name = _clean_html(p.get("name") or "Product")
            clean_description = _clean_html(p.get("summary") or "")

            products.append({
                "id": p.get("code") or "",
                "name": clean_name,
                "description": clean_description,
                "price": price,
                "image": img,
                "averageRating": p.get("averageRating"),
                "url": p.get("url")
            })
        
        return {"results": products, "error": None}
        
    except requests.exceptions.RequestException as e:
        print(f"Error in category search: {e}")
        return {"results": [], "error": str(e)}
    except Exception as e:
        print(f"Unexpected error in category search: {e}")
        return {"results": [], "error": str(e)}


def get_best_selling_products(page_size: int = 8) -> Dict:
    """
    Get best selling products for homepage carousel.
    Returns database results only - no fallback mock data.
    """
    try:
        # First try to get homepage structure
        homepage_data = get_homepage_structure()
        
        if homepage_data.get("error"):
            print(f"Error getting homepage structure: {homepage_data['error']}")
            return {"products": [], "error": f"Homepage structure error: {homepage_data['error']}"}
        
        # Look for carousel component in homepage structure
        carousel_uid = None
        homepage = homepage_data.get("homepage", {})
        
        # Navigate through the CMS structure to find carousel
        pages = homepage.get("pages", [])
        if pages:
            page = pages[0]  # Get first page
            content_slots = page.get("contentSlots", {}).get("contentSlot", [])
            
            for slot in content_slots:
                components = slot.get("components", {}).get("component", [])
                for component in components:
                    # Look for ProductCarouselComponent or similar
                    type_code = component.get("typeCode", "")
                    if "carousel" in type_code.lower() or "product" in type_code.lower():
                        carousel_uid = component.get("uid")
                        break
                if carousel_uid:
                    break
        
        if carousel_uid:
            # Get the carousel component details
            carousel_data = get_carousel_component(carousel_uid)
            if not carousel_data.get("error"):
                component = carousel_data.get("component", {})
                
                # Extract product codes or category codes from carousel
                product_codes = []
                category_codes = []
                
                # Look for products in the carousel component
                if "products" in component:
                    products = component.get("products", [])
                    product_codes = [p.get("code") for p in products if p.get("code")]
                
                # Look for categories in the carousel component  
                if "categories" in component:
                    categories = component.get("categories", [])
                    category_codes = [c.get("code") for c in categories if c.get("code")]
                
                # Fetch products by codes or categories
                if product_codes:
                    products = []
                    for code in product_codes[:page_size]:
                        product_data = get_product_by_code(code)
                        if not product_data.get("error") and product_data.get("product"):
                            p = product_data["product"]
                            
                            # Transform product to our format
                            img = ""
                            images = p.get("images") or []
                            if images:
                                preferred = next(
                                    (im for im in images if str(im.get("format", "")).lower() == "product"),
                                    images[0]
                                )
                                if preferred:
                                    img = preferred.get("url") or ""
                                    # Fix relative URLs
                                    if img and img.startswith("/medias/"):
                                        base_url = os.getenv("OCC_BASE_URL", "").rstrip("/")
                                        img = f"{base_url}{img}"
                            
                            price_val = None
                            price_obj = p.get("price") or {}
                            if isinstance(price_obj, dict):
                                price_val = price_obj.get("value")
                            try:
                                price = float(price_val) if price_val is not None else 0.0
                            except Exception:
                                price = 0.0
                                
                            products.append({
                                "id": p.get("code") or "",
                                "name": _clean_html(p.get("name") or "Product"),
                                "description": _clean_html(p.get("summary") or ""),
                                "price": price,
                                "image": img,
                                "averageRating": p.get("averageRating"),
                                "url": p.get("url")
                            })
                    
                    return {"results": products, "error": None, "source": "carousel_products"}
                
                elif category_codes:
                    # Use first category for now
                    category_result = search_products_by_category(category_codes[0], page_size)
                    if not category_result.get("error"):
                        return {"results": category_result.get("results", []), "error": None, "source": "carousel_category"}
        
        # If no carousel found or error, fallback to general best selling search
        print("No carousel found in homepage, falling back to best selling search...")
        return search_products_basic("", page_size)  # Empty query to get general products
        
    except Exception as e:
        print(f"Error in get_best_selling_products: {e}")
        return {"products": [], "error": f"Best selling products retrieval failed: {str(e)}"}


def get_whats_new_products(page_size: int = 8) -> Dict:
    """
    Get What's New products for  homepage carousel.
    Searches for new arrivals or recently added products.
    Returns database results only - no fallback mock data.
    """
    try:
        # Try multiple strategies to find new products
        base_url = os.getenv("OCC_BASE_URL")
        if not base_url:
            return {"results": [], "error": "Database connection not configured. Please configure OCC_BASE_URL environment variable."}
        
        site = _resolve_site()
        url = _build_search_url(base_url, site)
        
        # Strategy 1: Search by sort=topRated or newest
        params = {
            "query": ":topRated",  # Hybris OCC format for sorting
            "fields": "FULL",
            "pageSize": page_size,
            "currentPage": 0,
            "lang": "en"
        }
        
        url = _with_access_token(url)
        
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        resp = requests.get(
            url,
            params=params,
            headers=_headers(),
            timeout=20,
            verify=False
        )
        
        resp.raise_for_status()
        data = resp.json() or {}
        
        products = []
        for p in data.get("products", []):
            # Get image
            img = ""
            images = p.get("images") or []
            if images:
                preferred = next(
                    (im for im in images if str(im.get("format", "")).lower() == "product"),
                    images[0]
                )
                if preferred:
                    img = preferred.get("url") or ""
                    # Fix relative URLs
                    if img and img.startswith("/medias/"):
                        base = base_url.rstrip("/")
                        img = f"{base}{img}"
            
            # Get price
            price_val = None
            price_obj = p.get("price") or {}
            if isinstance(price_obj, dict):
                price_val = price_obj.get("value")
            try:
                price = float(price_val) if price_val is not None else 0.0
            except Exception:
                price = 0.0
            
            products.append({
                "id": p.get("code") or "",
                "name": _clean_html(p.get("name") or "Product"),
                "description": _clean_html(p.get("summary") or ""),
                "price": price,
                "image": img,
                "averageRating": p.get("averageRating"),
                "url": p.get("url")
            })
        
        if not products:
            return {"results": [], "error": "No new products found in database"}
        
        return {"results": products, "error": None, "source": "whats_new_toprated"}
        
    except requests.exceptions.RequestException as e:
        print(f"Error in get_whats_new_products: {e}")
        return {"results": [], "error": f"What's New products retrieval failed: {str(e)}"}
    except Exception as e:
        print(f"Unexpected error in get_whats_new_products: {e}")
        return {"results": [], "error": f"What's New products retrieval failed: {str(e)}"}
