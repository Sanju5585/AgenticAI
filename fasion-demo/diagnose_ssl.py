"""
SSL Configuration Diagnostic
Run this to see if ssl_config is working correctly
"""

import ssl_config
import os
from pathlib import Path

print("="*80)
print("SSL CONFIGURATION DIAGNOSTIC")
print("="*80)

print("\n1. Environment Variables:")
print(f"   SSL_CERT_FILE: {os.environ.get('SSL_CERT_FILE', 'NOT SET')}")
print(f"   REQUESTS_CA_BUNDLE: {os.environ.get('REQUESTS_CA_BUNDLE', 'NOT SET')}")
print(f"   CURL_CA_BUNDLE: {os.environ.get('CURL_CA_BUNDLE', 'NOT SET')}")

print("\n2. Certificate File Check:")
cert_path = Path("corporate_ca.crt")
if cert_path.exists():
    print(f"   ✅ Certificate exists: {cert_path.absolute()}")
    print(f"   Size: {cert_path.stat().st_size} bytes")
    # Read first few lines
    content = cert_path.read_text()
    if "BEGIN CERTIFICATE" in content:
        print(f"   ✅ Valid PEM format")
    else:
        print(f"   ❌ Invalid certificate format!")
else:
    print(f"   ❌ Certificate NOT found: {cert_path.absolute()}")

print("\n3. Testing with requests library:")
try:
    import requests
    
    # Test 1: Default (should use env vars)
    print("   Test 1: Using environment variables...")
    try:
        resp = requests.get("https://www.google.com", timeout=5)
        print(f"   ✅ SUCCESS - Status {resp.status_code}")
    except Exception as e:
        print(f"   ❌ FAILED: {str(e)[:100]}")
    
    # Test 2: Explicit verify
    print("   Test 2: Explicit verify parameter...")
    try:
        resp = requests.get("https://www.google.com", timeout=5, verify=str(cert_path))
        print(f"   ✅ SUCCESS - Status {resp.status_code}")
    except Exception as e:
        print(f"   ❌ FAILED: {str(e)[:100]}")
        
except ImportError:
    print("   ⚠️  requests library not available")

print("\n4. Testing Google API:")
try:
    import requests
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv('GOOGLE_API_KEY')
    if api_key:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={api_key}"
        
        headers = {'Content-Type': 'application/json'}
        data = {
            "model": "models/gemini-embedding-001",
            "content": {
                "parts": [{
                    "text": "test"
                }]
            }
        }
        
        # Test with explicit verify
        print("   Testing Google API with explicit verify...")
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=10, verify=str(cert_path))
            if resp.status_code == 200:
                print(f"   ✅ SUCCESS - Google API working!")
            else:
                print(f"   ⚠️  API returned: {resp.status_code}")
                print(f"   Response: {resp.text[:200]}")
        except Exception as e:
            print(f"   ❌ FAILED: {str(e)[:100]}")
    else:
        print("   ⚠️  GOOGLE_API_KEY not set - skipping")
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n5. Testing langchain_google_genai:")
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    
    print("   Attempting to create ChatGoogleGenerativeAI...")
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            temperature=0.3,
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )
        
        print("   Sending test query...")
        response = llm.invoke("Say 'SSL works' in 2 words")
        print(f"   ✅ SUCCESS: {response.content}")
    except Exception as e:
        print(f"   ❌ FAILED: {str(e)[:200]}")
        if "SSL" in str(e) or "certificate" in str(e).lower():
            print("\n   🚨 LANGCHAIN SSL ERROR DETECTED!")
            print("   💡 langchain_google_genai may not respect environment variables")
            print("   💡 Need to configure SSL differently for langchain")
        
except ImportError:
    print("   ⚠️  langchain_google_genai not available")

print("\n" + "="*80)
print("DIAGNOSTIC COMPLETE")
print("="*80)
