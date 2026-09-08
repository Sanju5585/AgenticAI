import csv
import requests
import json
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OCC API Configuration from .env file
OCC_BASE_URL = os.getenv("OCC_BASE_URL", "https://localhost:9002").rstrip('/')
SITE_ID = os.getenv("OCC_SITES", "apparel-uk-spa")
OLD_URL_PREFIX = "https://ec2-3-17-109-117.us-east-2.compute.amazonaws.com:9002/medias/"
LOCALHOST_BASE = f"{OCC_BASE_URL}/medias/"
OCC_API_URL = f"{OCC_BASE_URL}/occ/v2"

def get_product_from_hybris(product_code: str) -> Optional[dict]:
    """
    Fetch product information from Hybris OCC API.
    
    Args:
        product_code: The product code to fetch
        
    Returns:
        Product data dict if found, None if not found
    """
    try:
        # OCC API endpoint for product details
        url = f"{OCC_API_URL}/{SITE_ID}/products/{product_code}"
        
        # Add fields parameter to get images
        params = {
            'fields': 'code,images,DEFAULT'
        }
        
        print(f"🔍 Fetching product: {product_code}")
        
        # Make API request (disable SSL verification for self-signed certs)
        response = requests.get(url, params=params, verify=False, timeout=10)
        
        if response.status_code == 200:
            product_data = response.json()
            print(f"✅ Found product: {product_code}")
            return product_data
        elif response.status_code == 404:
            print(f"⚠️  Product not found in Hybris: {product_code}")
            return None
        else:
            print(f"❌ Error fetching product {product_code}: {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        print(f"⏱️  Timeout fetching product: {product_code}")
        return None
    except Exception as e:
        print(f"❌ Exception fetching product {product_code}: {e}")
        return None

def extract_image_url(product_data: dict) -> Optional[str]:
    """
    Extract the primary image URL from product data.
    
    Args:
        product_data: Product data from OCC API
        
    Returns:
        Image URL if found, None otherwise
    """
    try:
        # Check if images exist in the response
        if 'images' in product_data and len(product_data['images']) > 0:
            # Get the first image (PRIMARY or first available)
            primary_image = None
            
            # Try to find PRIMARY image
            for image in product_data['images']:
                if image.get('imageType') == 'PRIMARY':
                    primary_image = image
                    break
            
            # If no PRIMARY, use first image
            if not primary_image:
                primary_image = product_data['images'][0]
            
            # Get the URL from the image
            if 'url' in primary_image:
                return primary_image['url']
                
        return None
    except Exception as e:
        print(f"⚠️  Error extracting image URL: {e}")
        return None

def convert_to_localhost_url(original_url: str) -> str:
    """
    Convert AWS URL to localhost URL.
    
    Args:
        original_url: Original image URL from Hybris
        
    Returns:
        Converted localhost URL with full https://localhost:9002 prefix
    """
    if original_url.startswith(OLD_URL_PREFIX):
        # Extract the media path after the prefix
        media_path = original_url[len(OLD_URL_PREFIX):]
        # Create new localhost URL with full path
        return f"{LOCALHOST_BASE}{media_path}"
    elif original_url.startswith('/medias/'):
        # If URL starts with /medias/, prepend the base URL
        return f"{OCC_BASE_URL}{original_url}"
    elif original_url.startswith('medias/'):
        # If URL starts with medias/, prepend the base URL with /
        return f"{OCC_BASE_URL}/{original_url}"
    else:
        # If URL doesn't match expected format, just replace the base
        return original_url.replace(
            "https://ec2-3-17-109-117.us-east-2.compute.amazonaws.com:9002",
            OCC_BASE_URL
        )

def update_product_csv():
    """
    Main function to update product.csv with new image URLs from Hybris OCC API.
    """
    input_file = 'data/product.csv'
    output_file = 'data/product_updated.csv'
    backup_file = 'data/product_backup.csv'
    
    print("=" * 80)
    print("🚀 Starting Product Image URL Update Process")
    print("=" * 80)
    
    # Disable SSL warnings for self-signed certificates
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    updated_count = 0
    skipped_count = 0
    error_count = 0
    
    try:
        # Read the CSV file
        with open(input_file, 'r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            fieldnames = reader.fieldnames
            
            # Store all rows
            rows = []
            
            for row in reader:
                product_code = row.get('PRODUCT_ID', '').strip() if row.get('PRODUCT_ID') else ''
                current_url = row.get('IMAGE_URL', '').strip() if row.get('IMAGE_URL') else ''
                
                # Skip empty rows
                if not product_code:
                    print(f"\n⚠️  Empty product ID, skipping row")
                    continue
                
                print(f"\n📦 Processing: {product_code}")
                
                # Skip if no image URL
                if not current_url:
                    print(f"⚠️  No image URL for {product_code}, skipping")
                    skipped_count += 1
                    rows.append(row)
                    continue
                
                # Only update if current URL has the old prefix
                if current_url.startswith(OLD_URL_PREFIX):
                    # Fetch product from Hybris
                    product_data = get_product_from_hybris(product_code)
                    
                    if product_data:
                        # Extract image URL
                        image_url = extract_image_url(product_data)
                        
                        if image_url:
                            # Convert to localhost URL
                            new_url = convert_to_localhost_url(image_url)
                            row['IMAGE_URL'] = new_url
                            print(f"✅ Updated URL for {product_code}")
                            print(f"   Old: {current_url[:80]}...")
                            print(f"   New: {new_url[:80]}...")
                            updated_count += 1
                        else:
                            print(f"⚠️  No image found for {product_code}, keeping original")
                            skipped_count += 1
                    else:
                        # Product not found in Hybris, skip this row
                        print(f"⏭️  Skipping {product_code} (not found in Hybris)")
                        skipped_count += 1
                else:
                    print(f"ℹ️  URL already in correct format, skipping")
                    skipped_count += 1
                
                rows.append(row)
        
        # Write updated data to new CSV
        print(f"\n💾 Writing updated data to {output_file}")
        with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Filter out None keys from each row before writing
            clean_rows = []
            for row in rows:
                clean_row = {k: v for k, v in row.items() if k is not None and k in fieldnames}
                clean_rows.append(clean_row)
            
            writer.writerows(clean_rows)
        
        # Create backup
        import shutil
        shutil.copy2(input_file, backup_file)
        
        print("\n" + "=" * 80)
        print("✅ UPDATE COMPLETE!")
        print("=" * 80)
        print(f"✅ Updated: {updated_count} products")
        print(f"⏭️  Skipped: {skipped_count} products")
        print(f"❌ Errors: {error_count} products")
        print(f"📄 Output file: {output_file}")
        print(f"💾 Backup file: {backup_file}")
        print("=" * 80)
        
        print("\n💡 To use the updated file, rename it:")
        print(f"   mv {output_file} {input_file}")
        
    except FileNotFoundError:
        print(f"❌ Error: {input_file} not found!")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Set UTF-8 encoding for Windows console
    import sys
    import io
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    # Display configuration from .env file
    print("🔧 Configuration (from .env file):")
    print(f"   OCC API Base: {OCC_API_URL}")
    print(f"   Site ID: {SITE_ID}")
    print(f"   Old URL Prefix: {OLD_URL_PREFIX}")
    print(f"   New URL Base: {LOCALHOST_BASE}")
    print()
    
    update_product_csv()
