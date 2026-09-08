"""
Mock OCC API for testing when the real SAP Commerce server is not available
"""
import os
from typing import Dict, List


def search_products_mock(query: str, page_size: int = 12) -> Dict:
    """
    Mock product search that returns sample products for testing
    """
    
    # Sample product data based on the query
    mock_products = []
    
    query_lower = query.lower()
    
    if any(word in query_lower for word in ['shoe', 'boot', 'sneaker', 'footwear']):
        mock_products = [
            {
                "id": "300938",
                "name": "Snow boots",
                "description": "Warm winter snow boots with waterproof design",
                "price": 110.88,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3wyMDU1N3xpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3MQ"
            },
            {
                "id": "300919", 
                "name": "Casual sneakers",
                "description": "Comfortable everyday sneakers perfect for walking",
                "price": 75.50,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3wyMTIzNHxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Mg"
            },
            {
                "id": "300920",
                "name": "Leather boots", 
                "description": "Premium leather boots for formal occasions",
                "price": 199.99,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3wzMTU2N3xpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Mw"
            }
        ]
    elif any(word in query_lower for word in ['shirt', 'blouse', 'top', 'tee']):
        mock_products = [
            {
                "id": "300001",
                "name": "Cotton T-Shirt",
                "description": "Comfortable 100% cotton t-shirt in various colors",
                "price": 29.99,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w0MTI5N3xpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3NA"
            },
            {
                "id": "300002", 
                "name": "White Dress Shirt",
                "description": "Professional white dress shirt for business occasions",
                "price": 59.99,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w1MjM0NXxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3NQ"
            },
            {
                "id": "300003",
                "name": "Blue Casual Shirt",
                "description": "Relaxed fit blue casual shirt perfect for weekends",
                "price": 42.50,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w2MjM0NXxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Ng"
            },
            {
                "id": "300004",
                "name": "Red Polo Shirt",
                "description": "Classic red polo shirt with collar and short sleeves",
                "price": 38.99,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w3MjM0NXxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Nw"
            },
            {
                "id": "300005",
                "name": "Black Tank Top",
                "description": "Simple black tank top ideal for layering or workout",
                "price": 19.99,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w4MjM0NXxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3OA"
            },
            {
                "id": "300006",
                "name": "Green Flannel Shirt",
                "description": "Cozy green flannel shirt perfect for fall weather",
                "price": 48.75,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w5MjM0NXxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3OQ"
            }
        ]
    elif any(word in query_lower for word in ['pants', 'jeans', 'trousers']):
        mock_products = [
            {
                "id": "300101",
                "name": "Blue Jeans", 
                "description": "Classic blue denim jeans with regular fit",
                "price": 79.99,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w2MjM0NXxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Ng"
            },
            {
                "id": "300102",
                "name": "Dress Pants",
                "description": "Formal dress pants for professional wear",
                "price": 89.99,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w3MzQ1NnxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Nw"
            },
            {
                "id": "300103",
                "name": "Black Casual Pants",
                "description": "Comfortable black casual pants for everyday wear",
                "price": 45.00,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w4MzQ1NnxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3OA"
            },
            {
                "id": "300104",
                "name": "Red Chino Pants",
                "description": "Stylish red chino pants perfect for casual occasions",
                "price": 55.50,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w5MzQ1NnxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3OQ"
            },
            {
                "id": "300105",
                "name": "Gray Cargo Pants",
                "description": "Functional gray cargo pants with multiple pockets",
                "price": 65.00,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3wxMDM0NXxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M4MA"
            },
            {
                "id": "300106",
                "name": "Khaki Trousers",
                "description": "Classic khaki trousers for business casual wear",
                "price": 75.99,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3wxMTM0NXxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M4MQ"
            }
        ]
    else:
        # Generic products for any other search
        mock_products = [
            {
                "id": "300999",
                "name": "Popular Item",
                "description": f"Popular item matching your search for '{query}'",
                "price": 49.99,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w4NDU2N3xpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3OA"
            }
        ]
    
    return {"results": mock_products[:page_size]}


# Enhanced search with intelligent filtering
def search_products_smart(query: str, page_size: int = 12) -> Dict:
    """
    Intelligent product search that parses natural language queries 
    and applies appropriate filters for price, color, etc.
    """
    from app.tools.query_parser import query_parser, build_search_query, filter_products_by_criteria
    
    # Parse the query to extract filters
    filters = query_parser.parse_query(query)
    print(f"Parsed filters: {filters.to_dict()}")  # Debug logging
    
    # Build a search query from the parsed filters
    search_query = build_search_query(filters)
    print(f"Search query: '{search_query}'")  # Debug logging
    
    # Get initial product results
    initial_results = search_products_mock(search_query, page_size * 2)  # Get more to filter
    
    # Apply intelligent filtering based on parsed criteria
    filtered_products = filter_products_by_criteria(initial_results.get('results', []), filters)
    
    # Limit to requested page size
    filtered_products = filtered_products[:page_size]
    
    return {
        "results": filtered_products,
        "filters_applied": filters.to_dict(),
        "search_query": search_query
    }


# Use this as fallback when real OCC API is not available
def search_products_with_fallback(query: str, page_size: int = 12) -> Dict:
    """
    Try real OCC API first, fallback to mock if not available.
    Now includes smart filtering capabilities.
    """
    from app.tools.hybris_occ import search_products as real_search_products
    from app.tools.query_parser import query_parser, build_search_query, filter_products_by_criteria
    
    try:
        # Parse query for intelligent filtering
        filters = query_parser.parse_query(query)
        search_query = build_search_query(filters)
        
        # Try real API first
        result = real_search_products(search_query, page_size * 2)
        
        # If real API returned results, apply our intelligent filtering
        if not ('error' in result) and result.get('results'):
            filtered_products = filter_products_by_criteria(result.get('results', []), filters)
            result['results'] = filtered_products[:page_size]
            result['filters_applied'] = filters.to_dict()
            return result
        
        # If real API failed or no products, use smart mock search
        print(f"OCC API unavailable, using smart mock search for query: {query}")
        return search_products_smart(query, page_size)
        
    except Exception as e:
        print(f"OCC API error ({e}), using smart mock search for query: {query}")
        return search_products_smart(query, page_size)


def get_homepage_structure_mock() -> Dict:
    """Mock homepage structure with a sample carousel component"""
    return {
        "homepage": {
            "pages": [{
                "uid": "homepage",
                "typeCode": "ContentPage",
                "contentSlots": {
                    "contentSlot": [{
                        "slotId": "Section1",
                        "components": {
                            "component": [{
                                "uid": "ProductCarouselComponent",
                                "typeCode": "ProductCarouselComponent",
                                "name": "Best Selling Products Carousel"
                            }]
                        }
                    }]
                }
            }]
        },
        "error": None
    }


def get_carousel_component_mock(component_uid: str) -> Dict:
    """Mock carousel component with sample products"""
    return {
        "component": {
            "uid": component_uid,
            "typeCode": "ProductCarouselComponent", 
            "name": "Best Selling Products Carousel",
            "products": [
                {"code": "300938"},
                {"code": "300919"},
                {"code": "300920"},
                {"code": "300001"},
                {"code": "300002"},
                {"code": "300003"},
                {"code": "300101"},
                {"code": "300102"}
            ],
            "categories": [
                {"code": "shoes"},
                {"code": "shirts"}
            ]
        },
        "error": None
    }


def get_product_by_code_mock(product_code: str) -> Dict:
    """Mock individual product by code"""
    # Sample products by code
    products = {
        "300938": {
            "code": "300938",
            "name": "Snow boots",
            "summary": "Warm winter snow boots with waterproof design",
            "price": {"value": 110.88, "currencyIso": "GBP"},
            "images": [{
                "url": "/medias/?context=bWFzdGVyfGltYWdlc3wyMDU1N3xpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3MQ",
                "format": "product"
            }],
            "averageRating": 4.5,
            "url": "/apparel-uk/en/Open-Catalogue/Shoes/Boots/Snow-boots/p/300938"
        },
        "300919": {
            "code": "300919",
            "name": "Casual sneakers",
            "summary": "Comfortable everyday sneakers perfect for walking",
            "price": {"value": 75.50, "currencyIso": "GBP"},
            "images": [{
                "url": "/medias/?context=bWFzdGVyfGltYWdlc3wyMTIzNHxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Mg",
                "format": "product"
            }],
            "averageRating": 4.2,
            "url": "/apparel-uk/en/Open-Catalogue/Shoes/Sneakers/Casual-sneakers/p/300919"
        },
        "300920": {
            "code": "300920",
            "name": "Leather boots",
            "summary": "Premium leather boots for formal occasions",
            "price": {"value": 199.99, "currencyIso": "GBP"},
            "images": [{
                "url": "/medias/?context=bWFzdGVyfGltYWdlc3wzMTU2N3xpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Mw",
                "format": "product"
            }],
            "averageRating": 4.8,
            "url": "/apparel-uk/en/Open-Catalogue/Shoes/Boots/Leather-boots/p/300920"
        },
        "300001": {
            "code": "300001",
            "name": "Cotton T-Shirt",
            "summary": "Comfortable 100% cotton t-shirt in various colors",
            "price": {"value": 29.99, "currencyIso": "GBP"},
            "images": [{
                "url": "/medias/?context=bWFzdGVyfGltYWdlc3w0MTI5N3xpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3NA",
                "format": "product"
            }],
            "averageRating": 4.0,
            "url": "/apparel-uk/en/Open-Catalogue/Clothing/Shirts/Cotton-T-Shirt/p/300001"
        },
        "300002": {
            "code": "300002",
            "name": "White Dress Shirt",
            "summary": "Professional white dress shirt for business occasions",
            "price": {"value": 59.99, "currencyIso": "GBP"},
            "images": [{
                "url": "/medias/?context=bWFzdGVyfGltYWdlc3w1MjM0NXxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3NQ",
                "format": "product"
            }],
            "averageRating": 4.6,
            "url": "/apparel-uk/en/Open-Catalogue/Clothing/Shirts/White-Dress-Shirt/p/300002"
        },
        "300003": {
            "code": "300003",
            "name": "Blue Casual Shirt",
            "summary": "Relaxed fit blue casual shirt perfect for weekends",
            "price": {"value": 42.50, "currencyIso": "GBP"},
            "images": [{
                "url": "/medias/?context=bWFzdGVyfGltYWdlc3w2MjM0NXxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Ng",
                "format": "product"
            }],
            "averageRating": 4.3,
            "url": "/apparel-uk/en/Open-Catalogue/Clothing/Shirts/Blue-Casual-Shirt/p/300003"
        },
        "300101": {
            "code": "300101",
            "name": "Blue Jeans",
            "summary": "Classic blue denim jeans with regular fit",
            "price": {"value": 79.99, "currencyIso": "GBP"},
            "images": [{
                "url": "/medias/?context=bWFzdGVyfGltYWdlc3w2MjM0NXxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Ng",
                "format": "product"
            }],
            "averageRating": 4.4,
            "url": "/apparel-uk/en/Open-Catalogue/Clothing/Pants/Blue-Jeans/p/300101"
        },
        "300102": {
            "code": "300102",
            "name": "Dress Pants",
            "summary": "Formal dress pants for professional wear",
            "price": {"value": 89.99, "currencyIso": "GBP"},
            "images": [{
                "url": "/medias/?context=bWFzdGVyfGltYWdlc3w3MzQ1NnxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Nw",
                "format": "product"
            }],
            "averageRating": 4.7,
            "url": "/apparel-uk/en/Open-Catalogue/Clothing/Pants/Dress-Pants/p/300102"
        }
    }
    
    if product_code in products:
        return {"product": products[product_code], "error": None}
    else:
        return {"product": {}, "error": f"Product {product_code} not found"}


def search_products_by_category_mock(category_code: str, page_size: int = 8) -> Dict:
    """Mock category-based product search"""
    category_products = {
        "shoes": [
            {
                "id": "300938",
                "name": "Snow boots",
                "description": "Warm winter snow boots with waterproof design",
                "price": 110.88,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3wyMDU1N3xpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3MQ",
                "averageRating": 4.5
            },
            {
                "id": "300919",
                "name": "Casual sneakers",
                "description": "Comfortable everyday sneakers perfect for walking",
                "price": 75.50,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3wyMTIzNHxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Mg",
                "averageRating": 4.2
            },
            {
                "id": "300920",
                "name": "Leather boots",
                "description": "Premium leather boots for formal occasions",
                "price": 199.99,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3wzMTU2N3xpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Mw",
                "averageRating": 4.8
            }
        ],
        "shirts": [
            {
                "id": "300001",
                "name": "Cotton T-Shirt",
                "description": "Comfortable 100% cotton t-shirt in various colors",
                "price": 29.99,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w0MTI5N3xpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3NA",
                "averageRating": 4.0
            },
            {
                "id": "300002",
                "name": "White Dress Shirt",
                "description": "Professional white dress shirt for business occasions",
                "price": 59.99,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w1MjM0NXxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3NQ",
                "averageRating": 4.6
            },
            {
                "id": "300003",
                "name": "Blue Casual Shirt", 
                "description": "Relaxed fit blue casual shirt perfect for weekends",
                "price": 42.50,
                "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w2MjM0NXxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Ng",
                "averageRating": 4.3
            }
        ]
    }
    
    products = category_products.get(category_code, [])
    return {"results": products[:page_size], "error": None}


def get_best_selling_products_mock(page_size: int = 8) -> Dict:
    """Mock best selling products for homepage carousel"""
    best_sellers = [
        {
            "id": "300938",
            "name": "Snow boots",
            "description": "Warm winter snow boots with waterproof design",
            "price": 110.88,
            "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3wyMDU1N3xpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3MQ",
            "averageRating": 4.5,
            "url": "/apparel-uk/en/Open-Catalogue/Shoes/Boots/Snow-boots/p/300938"
        },
        {
            "id": "300002",
            "name": "White Dress Shirt",
            "description": "Professional white dress shirt for business occasions",
            "price": 59.99,
            "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w1MjM0NXxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3NQ",
            "averageRating": 4.6,
            "url": "/apparel-uk/en/Open-Catalogue/Clothing/Shirts/White-Dress-Shirt/p/300002"
        },
        {
            "id": "300101",
            "name": "Blue Jeans",
            "description": "Classic blue denim jeans with regular fit",
            "price": 79.99,
            "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w2MjM0NXxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Ng",
            "averageRating": 4.4,
            "url": "/apparel-uk/en/Open-Catalogue/Clothing/Pants/Blue-Jeans/p/300101"
        },
        {
            "id": "300920",
            "name": "Leather boots",
            "description": "Premium leather boots for formal occasions",
            "price": 199.99,
            "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3wzMTU2N3xpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Mw",
            "averageRating": 4.8,
            "url": "/apparel-uk/en/Open-Catalogue/Shoes/Boots/Leather-boots/p/300920"
        },
        {
            "id": "300919",
            "name": "Casual sneakers",
            "description": "Comfortable everyday sneakers perfect for walking",
            "price": 75.50,
            "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3wyMTIzNHxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Mg",
            "averageRating": 4.2,
            "url": "/apparel-uk/en/Open-Catalogue/Shoes/Sneakers/Casual-sneakers/p/300919"
        },
        {
            "id": "300003",
            "name": "Blue Casual Shirt",
            "description": "Relaxed fit blue casual shirt perfect for weekends",
            "price": 42.50,
            "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w2MjM0NXxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Ng",
            "averageRating": 4.3,
            "url": "/apparel-uk/en/Open-Catalogue/Clothing/Shirts/Blue-Casual-Shirt/p/300003"
        },
        {
            "id": "300001",
            "name": "Cotton T-Shirt",
            "description": "Comfortable 100% cotton t-shirt in various colors",
            "price": 29.99,
            "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w0MTI5N3xpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3NA",
            "averageRating": 4.0,
            "url": "/apparel-uk/en/Open-Catalogue/Clothing/Shirts/Cotton-T-Shirt/p/300001"
        },
        {
            "id": "300102",
            "name": "Dress Pants",
            "description": "Formal dress pants for professional wear",
            "price": 89.99,
            "image": "https://apparel-uk.local:9002/yacceleratorstorefront/medias/?context=bWFzdGVyfGltYWdlc3w3MzQ1NnxpbWFnZS9qcGVnfGFXMWhaMlZ6TDJnNFlpOW9OV0V2T0RjNU5qWTRNVGcyTXpFNU9DNXFjR2N8N2JmZjAxOGMwNjhjYzI0YmU0ZWZiNTFjYjQ3ZjJlZmE1YWI1OGQ2MjU4ZTJmYTQzNWE2M2VhOTMwNGI3N2M3Nw",
            "averageRating": 4.7,
            "url": "/apparel-uk/en/Open-Catalogue/Clothing/Pants/Dress-Pants/p/300102"
        }
    ]
    
    return {"results": best_sellers[:page_size], "error": None, "source": "mock_best_sellers"}