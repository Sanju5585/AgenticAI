"""
Script to download real product images for mobile products from the internet
Uses multiple sources: Pexels API (free), web scraping, and fallback sources
"""
import csv
import os
import requests
import time
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

def create_images_directory():
    """Create images directory if it doesn't exist"""
    if not os.path.exists('images'):
        os.makedirs('images')
        print("✅ Created 'images' directory")
    else:
        print("ℹ️  'images' directory already exists")

def search_pixabay_image(product_name, manufacturer):
    """Search for product image using Pixabay API (free tier)"""
    api_key = os.getenv('PIXABAY_API_KEY')
    if not api_key:
        print("⚠️  PIXABAY_API_KEY not found in .env file")
        return None
    
    # Use specific product-focused search terms
    search_query = f"{manufacturer} {product_name} smartphone isolated white background"
    url = f"https://pixabay.com/api/?key={api_key}&q={quote_plus(search_query)}&image_type=photo&per_page=5&orientation=vertical"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('hits') and len(data['hits']) > 0:
                # Try to find the best product image (prefer images with white/clean backgrounds)
                for hit in data['hits']:
                    tags = hit.get('tags', '').lower()
                    # Filter for actual phone product images
                    if any(keyword in tags for keyword in ['phone', 'smartphone', 'iphone', 'mobile', 'device', 'technology']):
                        image_url = hit['largeImageURL']
                        return image_url
                # If no perfect match, use first result
                image_url = data['hits'][0]['largeImageURL']
                return image_url
    except Exception as e:
        print(f"⚠️  Pixabay API error: {e}")
    
    return None

def search_pexels_image(product_name, manufacturer):
    """Search for product image using Pexels API (free tier)"""
    api_key = os.getenv('PEXELS_API_KEY')
    if not api_key:
        return None
    
    # Use specific product-focused search terms
    search_query = f"{manufacturer} {product_name} smartphone product"
    url = f"https://api.pexels.com/v1/search?query={quote_plus(search_query)}&per_page=5&orientation=portrait"
    
    headers = {'Authorization': api_key}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('photos') and len(data['photos']) > 0:
                # Get the first result's large image
                image_url = data['photos'][0]['src']['large']
                return image_url
    except Exception as e:
        print(f"⚠️  Pexels API error: {e}")
    
    return None

def search_duckduckgo_image(product_name, manufacturer):
    """Scrape image from DuckDuckGo search results"""
    search_query = f"{manufacturer} {product_name} official"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        # Use DuckDuckGo HTML search
        url = f"https://duckduckgo.com/i.js?q={quote_plus(search_query)}&o=json&p=1&s=0"
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'results' in data and len(data['results']) > 0:
                return data['results'][0].get('image')
    except:
        pass
    
    return None

def download_image_from_url(image_url, product_id):
    """Download image from URL and save it"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(image_url, headers=headers, timeout=15, allow_redirects=True)
        
        if response.status_code == 200 and len(response.content) > 1000:
            # Determine file extension
            content_type = response.headers.get('content-type', '')
            if 'jpeg' in content_type or 'jpg' in content_type:
                ext = 'jpg'
            elif 'png' in content_type:
                ext = 'png'
            elif 'webp' in content_type:
                ext = 'webp'
            else:
                ext = 'jpg'  # default
            
            image_path = f"images/{product_id}.{ext}"
            with open(image_path, 'wb') as f:
                f.write(response.content)
            return image_path
    except Exception as e:
        print(f"⚠️  Download error: {e}")
    
    return None

def search_and_download_image(product_name, product_id, manufacturer):
    """
    Search for product image using multiple sources and download it
    """
    search_query = f"{manufacturer} {product_name}"
    print(f"\n🔍 Searching for: {search_query}")
    
    # Strategy 1: Try Pixabay API (if API key is available)
    print(f"📥 Trying Pixabay API...")
    image_url = search_pixabay_image(product_name, manufacturer)
    if image_url:
        image_path = download_image_from_url(image_url, product_id)
        if image_path:
            print(f"✅ Downloaded from Pixabay: {image_path}")
            return True
    
    # Strategy 2: Try Pexels API (if API key is available)
    print(f"📥 Trying Pexels API...")
    image_url = search_pexels_image(product_name, manufacturer)
    if image_url:
        image_path = download_image_from_url(image_url, product_id)
        if image_path:
            print(f"✅ Downloaded from Pexels: {image_path}")
            return True
    
    # Strategy 3: Try Unsplash Source (random but relevant images)
    print(f"📥 Trying Unsplash Source...")
    # Use more specific terms for phone product images
    unsplash_url = f"https://source.unsplash.com/800x800/?{quote_plus(manufacturer)},{quote_plus(product_name)},smartphone,product,isolated"
    image_path = download_image_from_url(unsplash_url, product_id)
    if image_path:
        print(f"✅ Downloaded from Unsplash: {image_path}")
        return True
    
    print(f"❌ Could not find real phone product image for {product_name}")
    return False

def download_all_mobile_images():
    """Main function to download images for all mobile products"""
    csv_file = "data/mobile_products.csv"
    
    print("="*80)
    print("🚀 Downloading Real Product Images for Mobile Products")
    print("   Using Pixabay API (primary), Pexels API, and Unsplash (fallback)")
    print("="*80)
    print("\nℹ️  To use Pixabay API:")
    print("   1. Get free API key from: https://pixabay.com/api/docs/")
    print("   2. Add to .env file: PIXABAY_API_KEY=your_key_here")
    print("="*80)
    
    # Create images directory
    create_images_directory()
    
    # Read CSV and download images
    try:
        with open(csv_file, 'r', encoding='utf-8') as csvfile:
            csv_reader = csv.DictReader(csvfile)
            
            success_count = 0
            failed_count = 0
            
            for row in csv_reader:
                product_id = row.get('PRODUCT_ID', '').strip()
                product_name = row.get('PRODUCT_NAME', '').strip()
                manufacturer = row.get('MANUFACTURE_NAME', '').strip()
                
                if not product_id or not product_name:
                    continue
                
                # Check if image already exists
                image_path = f"images/{product_id}.png"
                if os.path.exists(image_path):
                    print(f"⏭️  Skipping {product_name} - image already exists")
                    success_count += 1
                    continue
                
                # Download image
                if search_and_download_image(product_name, product_id, manufacturer):
                    success_count += 1
                else:
                    failed_count += 1
                
                # Be polite to servers - add delay
                time.sleep(1)
            
            print("\n" + "="*80)
            print("📊 Download Summary:")
            print(f"   ✅ Successfully downloaded: {success_count} images")
            print(f"   ❌ Failed: {failed_count} images")
            print("="*80)
            
    except FileNotFoundError:
        print(f"❌ CSV file not found: {csv_file}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    download_all_mobile_images()
