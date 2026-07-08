"""
Script to fetch electronic products from Hybris OCC API and create electronicProduct.csv
"""

import csv
import requests
import os
from typing import List, Dict, Optional
from dotenv import load_dotenv
import urllib3

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables
load_dotenv()

# OCC API Configuration
OCC_BASE_URL = os.getenv("OCC_BASE_URL", "https://localhost:9002").rstrip('/')
# Use electronics-spa site explicitly for electronics catalog
SITE_ID = "electronics-spa"
OCC_API_URL = f"{OCC_BASE_URL}/occ/v2"

# Electronics Product Catalog configuration
CATALOG_ID = "electronicsProductCatalog"
CATALOG_VERSION = "Online"


def get_electronics_products(page_size: int = 100) -> List[Dict]:
    """
    Fetch all products from Electronics Product Catalog:Online using Hybris OCC API.
    
    Args:
        page_size: Number of products per page
        
    Returns:
        List of product dictionaries
    """
    all_products = []
    current_page = 0
    
    try:
        while True:
            # OCC API endpoint for products
            url = f"{OCC_API_URL}/{SITE_ID}/products/search"
            
            # Parameters for the search - query all products from electronics catalog
            params = {
                'query': ':relevance',
                'fields': 'FULL',
                'currentPage': current_page,
                'pageSize': page_size
            }
            
            print(f"🔍 Fetching page {current_page} of products from Electronics Product Catalog:Online...")
            
            # Make API request
            response = requests.get(url, params=params, verify=False, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                products = data.get('products', [])
                
                if not products:
                    print(f"✅ No more products found. Total fetched: {len(all_products)}")
                    break
                
                # All products from electronics-spa site are from electronicsProductCatalog
                all_products.extend(products)
                print(f"   Found {len(products)} products from Electronics Product Catalog:Online")
                
                # Check if there are more pages
                pagination = data.get('pagination', {})
                total_pages = pagination.get('totalPages', 1)
                
                if current_page >= total_pages - 1:
                    print(f"✅ Fetched all {len(all_products)} products from {total_pages} pages")
                    break
                
                current_page += 1
            else:
                print(f"❌ Error fetching products: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                break
                
    except Exception as e:
        print(f"❌ Exception while fetching products: {e}")
    
    return all_products





def extract_product_data(product: Dict) -> Optional[Dict]:
    """
    Extract required fields from product data.
    
    Args:
        product: Product dictionary from OCC API
        
    Returns:
        Dictionary with required CSV fields
    """
    try:
        # Extract product ID
        product_id = product.get('code', '')
        
        # Extract product name
        product_name = product.get('name', '')
        
        # Extract summary
        summary = product.get('summary', '')
        
        # Extract price
        price = ''
        if 'price' in product and product['price']:
            price_obj = product['price']
            if 'value' in price_obj:
                price = str(price_obj['value'])
            elif 'formattedValue' in price_obj:
                # Extract numeric value from formatted string
                price = price_obj['formattedValue'].replace('£', '').replace(',', '').strip()
        
        # Extract category IDs
        category_ids = []
        if 'categories' in product and product['categories']:
            for category in product['categories']:
                if 'code' in category:
                    category_ids.append(category['code'])
        category_ids_str = '|'.join(category_ids) if category_ids else ''
        
        # Extract manufacturer name
        manufacturer_name = ''
        if 'manufacturer' in product and product['manufacturer']:
            manufacturer_name = product['manufacturer']
        
        # Extract image URL with https://localhost:9002/ prefix
        image_url = ''
        if 'images' in product and len(product['images']) > 0:
            # Find PRIMARY image or use first available
            primary_image = None
            for image in product['images']:
                if image.get('imageType') == 'PRIMARY':
                    primary_image = image
                    break
            
            if not primary_image:
                primary_image = product['images'][0]
            
            if 'url' in primary_image:
                raw_url = primary_image['url']
                # Ensure URL has https://localhost:9002/ prefix
                if raw_url.startswith('/medias/'):
                    image_url = f"https://localhost:9002{raw_url}"
                elif raw_url.startswith('medias/'):
                    image_url = f"https://localhost:9002/{raw_url}"
                elif raw_url.startswith('http'):
                    # Replace any existing domain with localhost:9002
                    if '://' in raw_url:
                        path = raw_url.split('/', 3)[-1] if raw_url.count('/') >= 3 else ''
                        if path:
                            image_url = f"https://localhost:9002/{path}"
                else:
                    image_url = f"https://localhost:9002/{raw_url}"
        
        return {
            'PRODUCT_ID': product_id,
            'PRODUCT_NAME': product_name,
            'SUMMARY': summary,
            'PRICE': price,
            'CATEGORY_IDS': category_ids_str,
            'MANUFACTURE_NAME': manufacturer_name,
            'IMAGE_URL': image_url
        }
        
    except Exception as e:
        print(f"⚠️  Error extracting product data: {e}")
        return None


def create_electronic_products_csv():
    """
    Main function to fetch products and create electronicProduct.csv
    """
    print("=" * 80)
    print("🚀 Fetching Electronic Products from Hybris OCC API")
    print("=" * 80)
    print(f"📍 API URL: {OCC_API_URL}")
    print(f"🏪 Site ID: {SITE_ID}")
    print(f"📚 Catalog: {CATALOG_ID}:{CATALOG_VERSION}")
    print()
    
    # Fetch products from Electronics Product Catalog:Online
    print(f"🔍 Fetching products from {CATALOG_ID}:{CATALOG_VERSION}...")
    products = get_electronics_products()
    
    if not products:
        print("❌ No products found!")
        return
    
    print(f"\n📊 Processing {len(products)} products...")
    
    # Extract data for CSV
    csv_data = []
    success_count = 0
    error_count = 0
    
    for product in products:
        product_data = extract_product_data(product)
        if product_data:
            csv_data.append(product_data)
            success_count += 1
        else:
            error_count += 1
    
    # Create output directory if it doesn't exist
    os.makedirs('data', exist_ok=True)
    
    # Write to CSV
    output_file = 'data/electronicProduct.csv'
    
    try:
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['PRODUCT_ID', 'PRODUCT_NAME', 'SUMMARY', 'PRICE', 'CATEGORY_IDS', 'MANUFACTURE_NAME', 'IMAGE_URL']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            writer.writerows(csv_data)
        
        print("\n" + "=" * 80)
        print("✅ CSV File Created Successfully!")
        print("=" * 80)
        print(f"📄 File: {output_file}")
        print(f"✅ Successfully processed: {success_count} products")
        print(f"❌ Errors: {error_count} products")
        print(f"📊 Total rows in CSV: {len(csv_data)}")
        print()
        
        # Display first few rows as sample
        if csv_data:
            print("📋 Sample Data (first 3 products):")
            print("-" * 80)
            for i, row in enumerate(csv_data[:3], 1):
                print(f"\n{i}. Product ID: {row['PRODUCT_ID']}")
                print(f"   Name: {row['PRODUCT_NAME']}")
                print(f"   Price: {row['PRICE']}")
                print(f"   Manufacturer: {row['MANUFACTURE_NAME']}")
                print(f"   Categories: {row['CATEGORY_IDS']}")
                print(f"   Image: {row['IMAGE_URL'][:80]}...")
        
    except Exception as e:
        print(f"❌ Error writing CSV file: {e}")


if __name__ == "__main__":
    create_electronic_products_csv()
