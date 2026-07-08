"""
SSL Config - Corporate Network Workaround
TEMPORARY solution to bypass SSL verification
WARNING: Use only in corporate environment, never in production!
"""

import os
import warnings
from pathlib import Path

def configure_ssl():
    """Configure SSL for corporate network"""
    
    # Try to use corporate certificate first
    corp_cert = Path(__file__).parent / "corporate_ca.crt"
    
    if corp_cert.exists():
        cert_path = str(corp_cert)
        os.environ['SSL_CERT_FILE'] = cert_path
        os.environ['REQUESTS_CA_BUNDLE'] = cert_path
        os.environ['CURL_CA_BUNDLE'] = cert_path
        print(f"[OK] SSL configured with corporate certificate: {corp_cert.name}")
    
    # WORKAROUND: Disable SSL verification for Google APIs
    # This is needed because langchain_google_genai doesn't respect env vars
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    
    # Suppress SSL warnings
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except:
        pass
    
    warnings.filterwarnings('ignore', message='Unverified HTTPS request')
    
    print("[WARN] SSL verification disabled for corporate proxy compatibility")
    print("[WARN] This is acceptable ONLY on corporate network")

# Auto-configure when imported
configure_ssl()
