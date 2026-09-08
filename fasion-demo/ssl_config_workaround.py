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
    
    # Patch httpx (used by langchain_google_genai) to disable SSL verification
    try:
        import httpx
        _orig_client_init = httpx.Client.__init__
        def _patched_client_init(self, *args, **kwargs):
            kwargs.setdefault('verify', False)
            _orig_client_init(self, *args, **kwargs)
        httpx.Client.__init__ = _patched_client_init

        _orig_async_client_init = httpx.AsyncClient.__init__
        def _patched_async_client_init(self, *args, **kwargs):
            kwargs.setdefault('verify', False)
            _orig_async_client_init(self, *args, **kwargs)
        httpx.AsyncClient.__init__ = _patched_async_client_init
        print("[OK] httpx SSL verification disabled for corporate proxy compatibility")
    except Exception as _e:
        print(f"[WARN] Could not patch httpx: {_e}")

    print("[WARN] SSL verification disabled for corporate proxy compatibility")
    print("[WARN] This is acceptable ONLY on corporate network")

# Auto-configure when imported
configure_ssl()
