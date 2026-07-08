"""
SSL Certificate Verification Checker
Tests SSL connectivity to various endpoints including Google APIs
"""

import sys
import ssl
import socket
import certifi
import requests
from urllib.request import urlopen
from urllib.error import URLError


def check_ssl_module():
    """Check SSL module configuration"""
    print("\n" + "="*80)
    print("🔐 SSL Module Configuration")
    print("="*80)
    
    print(f"✓ OpenSSL Version: {ssl.OPENSSL_VERSION}")
    print(f"✓ SSL Module Version: {ssl.OPENSSL_VERSION_NUMBER}")
    print(f"✓ Default CA Bundle: {ssl.get_default_verify_paths().cafile or 'Not set'}")
    print(f"✓ Certifi CA Bundle: {certifi.where()}")
    return True


def check_certifi():
    """Check if certifi is installed and working"""
    print("\n" + "="*80)
    print("📦 Certifi Package Check")
    print("="*80)
    
    try:
        import certifi
        cert_path = certifi.where()
        print(f"✅ Certifi installed: {certifi.__version__}")
        print(f"✅ CA Bundle location: {cert_path}")
        
        # Check if file exists
        import os
        if os.path.exists(cert_path):
            file_size = os.path.getsize(cert_path)
            print(f"✅ CA Bundle file exists ({file_size:,} bytes)")
            return True
        else:
            print(f"❌ CA Bundle file not found at: {cert_path}")
            return False
    except ImportError:
        print("❌ Certifi not installed")
        print("💡 Install with: pip install certifi")
        return False


def test_ssl_connection(hostname, port=443):
    """Test raw SSL socket connection"""
    print(f"\n🔌 Testing SSL socket connection to {hostname}:{port}...")
    
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                print(f"✅ SSL connection successful")
                print(f"   Subject: {dict(x[0] for x in cert['subject'])}")
                print(f"   Issuer: {dict(x[0] for x in cert['issuer'])}")
                return True
    except ssl.SSLError as e:
        print(f"❌ SSL Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return False


def test_urllib_request(url):
    """Test urllib with SSL"""
    print(f"\n🌐 Testing urllib request to {url}...")
    
    try:
        # Test WITHOUT certifi
        print("   Attempting with default SSL context...")
        response = urlopen(url, timeout=10)
        print(f"✅ SUCCESS - Status: {response.status}")
        response.close()
        return True
    except URLError as e:
        print(f"❌ FAILED with default context: {e.reason}")
        
        # Test WITH certifi
        try:
            print("   Attempting with certifi CA bundle...")
            import ssl
            context = ssl.create_default_context(cafile=certifi.where())
            response = urlopen(url, timeout=10, context=context)
            print(f"✅ SUCCESS with certifi - Status: {response.status}")
            response.close()
            return True
        except Exception as e2:
            print(f"❌ FAILED with certifi: {e2}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_requests_library(url):
    """Test requests library with SSL"""
    print(f"\n📡 Testing requests library to {url}...")
    
    # Test 1: Default (may fail)
    try:
        print("   Test 1: Default verification...")
        response = requests.get(url, timeout=10)
        print(f"✅ SUCCESS - Status: {response.status_code}")
        return True
    except requests.exceptions.SSLError as e:
        print(f"❌ FAILED with default: SSL Error")
        print(f"   Details: {str(e)[:150]}...")
    except Exception as e:
        print(f"❌ FAILED: {e}")
    
    # Test 2: With certifi
    try:
        print("   Test 2: With certifi CA bundle...")
        response = requests.get(url, timeout=10, verify=certifi.where())
        print(f"✅ SUCCESS with certifi - Status: {response.status_code}")
        return True
    except Exception as e:
        print(f"❌ FAILED with certifi: {e}")
    
    # Test 3: Verify=False (insecure)
    try:
        print("   Test 3: With verify=False (insecure)...")
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = requests.get(url, timeout=10, verify=False)
        print(f"⚠️  SUCCESS with verify=False - Status: {response.status_code}")
        print(f"   WARNING: This bypasses security - NOT recommended!")
        return False  # Return False because this isn't a proper solution
    except Exception as e:
        print(f"❌ FAILED even with verify=False: {e}")
        return False


def test_google_api():
    """Test Google Generative AI API specifically"""
    print("\n" + "="*80)
    print("🤖 Google Generative AI API Test")
    print("="*80)
    
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("⚠️  GOOGLE_API_KEY not found in environment")
        print("💡 Add it to .env file to test API connectivity")
        return None
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={api_key}"
    
    headers = {'Content-Type': 'application/json'}
    data = {
        "model": "models/gemini-embedding-001",
        "content": {
            "parts": [{
                "text": "SSL test"
            }]
        }
    }
    
    # Try with certifi
    try:
        print("🔐 Testing Google API with certifi SSL verification...")
        response = requests.post(url, headers=headers, json=data, timeout=10, verify=certifi.where())
        if response.status_code == 200:
            print(f"✅ SUCCESS - Google API responding correctly")
            return True
        else:
            print(f"⚠️  API responded with status: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
    except requests.exceptions.SSLError as e:
        print(f"❌ SSL ERROR: {str(e)[:200]}...")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def provide_solutions(ssl_errors_found):
    """Provide solutions based on test results"""
    print("\n" + "="*80)
    print("💡 SOLUTIONS")
    print("="*80)
    
    if ssl_errors_found:
        print("\n❌ SSL errors detected! Here's how to fix them:\n")
        
        print("✅ SOLUTION 1: Install/Update SSL certificates (Recommended)")
        print("   Run these commands:")
        print("   pip install --upgrade certifi")
        print("   pip install --upgrade urllib3")
        print("   pip install --upgrade requests")
        
        print("\n✅ SOLUTION 2: Use certifi in your code")
        print("   Add at the top of your Python scripts:")
        print("   import certifi")
        print("   import os")
        print("   os.environ['SSL_CERT_FILE'] = certifi.where()")
        print("   os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()")
        
        print("\n✅ SOLUTION 3: For requests library")
        print("   Use verify parameter:")
        print("   requests.get(url, verify=certifi.where())")
        
        print("\n⚠️  NOT RECOMMENDED (insecure):")
        print("   verify=False bypasses security - only use for testing!")
    else:
        print("\n✅ No SSL errors detected!")
        print("Your SSL configuration appears to be working correctly.")


def main():
    """Run all SSL checks"""
    print("="*80)
    print("🔍 SSL CERTIFICATE VERIFICATION DIAGNOSTIC TOOL")
    print("="*80)
    print("This tool checks if SSL certificate verification is working properly")
    
    ssl_errors = False
    
    # Check SSL module
    check_ssl_module()
    
    # Check certifi
    if not check_certifi():
        ssl_errors = True
    
    # Test various connections
    print("\n" + "="*80)
    print("🌍 Testing SSL Connections")
    print("="*80)
    
    # Test 1: Google
    if not test_ssl_connection("www.google.com"):
        ssl_errors = True
    
    # Test 2: Google APIs
    if not test_ssl_connection("generativelanguage.googleapis.com"):
        ssl_errors = True
    
    # Test urllib
    print("\n" + "="*80)
    print("📚 Testing Python Libraries")
    print("="*80)
    
    if not test_urllib_request("https://www.google.com"):
        ssl_errors = True
    
    # Test requests library
    if not test_requests_library("https://www.google.com"):
        ssl_errors = True
    
    # Test Google API specifically
    api_result = test_google_api()
    if api_result is False:
        ssl_errors = True
    
    # Provide solutions
    provide_solutions(ssl_errors)
    
    # Summary
    print("\n" + "="*80)
    print("📊 SUMMARY")
    print("="*80)
    if ssl_errors:
        print("❌ SSL errors were detected during testing")
        print("📋 Review the solutions above to fix the issues")
        sys.exit(1)
    else:
        print("✅ All SSL checks passed successfully!")
        print("🎉 Your SSL configuration is working correctly")
        sys.exit(0)


if __name__ == "__main__":
    main()
