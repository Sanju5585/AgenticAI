import os
from dotenv import load_dotenv
load_dotenv()
import ssl_config_workaround  # Must be imported before any Google/httpx calls
from langchain_google_genai import ChatGoogleGenerativeAI
#from gen_ai_hub.proxy.langchain.init_models import init_llm
#from gen_ai_hub.proxy.langchain.openai import ChatOpenAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings #ADDED
#from gen_ai_hub.proxy.native.openai import embeddings
#from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from langchain.chat_models import init_chat_model

# Initialize Google Generative AI LLM with latest model
google_generative_ai_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",  # Latest Gemini 2.5 Flash-Lite model
    temperature=0.3,  # Slightly higher temperature for better tool usage
    google_api_key=os.getenv("GOOGLE_API_KEY")
)

# Enhanced multilingual embedding function with AI-driven preprocessing
def get_google_embedding(text: str) -> list:
    """
    Enhanced multilingual embedding generation with Google gemini-embedding-001.
    
    Features:
    - Uses gemini-embedding-001 via v1beta API (768 dimensions)
    - Automatic text preprocessing for better embeddings
    - Multilingual optimization 
    - Robust error handling with smart fallbacks
    """
    try:
        import requests
        
        print(f"🔢 Generating Gemini embedding for: '{text[:50]}...'")
        
        # Preprocess text for better embeddings
        preprocessed_text = text.strip()
        
        # Use v1beta API with gemini-embedding-001
        api_key = os.getenv("GOOGLE_API_KEY")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={api_key}"
        
        headers = {'Content-Type': 'application/json'}
        data = {
            "model": "models/gemini-embedding-001",
            "content": {
                "parts": [{
                    "text": preprocessed_text
                }]
            }
        }
        
        response = requests.post(url, headers=headers, json=data, verify=False)
        
        if response.status_code == 200:
            result = response.json()
            embedding = result.get('embedding', {}).get('values', [])
            
            if not embedding:
                # Fallback for slightly different API response structure
                embedding = result.get('embedding', [])

            if embedding and len(embedding) > 0:
                print(f"✅ Generated {len(embedding)}-dimension embedding using gemini-embedding-001")
                return embedding
            else:
                raise Exception("Empty embedding returned from API")
        else:
            error_msg = response.text
            raise Exception(f"API Error ({response.status_code}): {error_msg}")
        
    except Exception as e:
        error_msg = str(e).lower()
        if "quota" in error_msg or "429" in error_msg:
            print("=" * 80)
            print("🚨 GOOGLE API QUOTA EXCEEDED")
            print("⚠️  WARNING: Google API quota exceeded for embeddings.")
            print("🔄 System will fall back to AI-powered text search.")
            print("💡 Consider upgrading API quota for optimal performance.")
            print("=" * 80)
        elif "invalid" in error_msg or "unauthorized" in error_msg:
            print("🔑 Google API authentication issue. Check your API key.")
        else:
            print(f"❌ Embedding generation failed: {e}")
        
        return []  # Return empty list to trigger AI text search fallback
    """
    AI-powered text preprocessing to enhance embedding quality.
    
    Optimizations:
    - Remove noise and irrelevant characters
    - Normalize multilingual text
    - Enhance context for better semantic understanding
    - Preserve important semantic information
    """
    try:
        # Basic cleanup
        processed = text.strip()
        
        # Enhanced preprocessing for product search context
        if any(word in processed.lower() for word in ['show', 'find', 'search', 'get', 'buy']):
            # Extract the core product intent
            words = processed.lower().split()
            product_words = []
            
            for word in words:
                # Skip common search verbs but keep product keywords
                if word not in ['show', 'me', 'find', 'search', 'get', 'some', 'a', 'an', 'the']:
                    product_words.append(word)
            
            if product_words:
                processed = ' '.join(product_words)
        
        # Enhance context for better semantic matching
        enhanced_text = enhance_semantic_context(processed)
        
        print(f"🔧 Text preprocessing: '{text}' → '{enhanced_text}'")
        return enhanced_text
        
    except Exception as e:
        print(f"⚠️  Text preprocessing failed: {e}")
        return text  # Return original on failure

def enhance_semantic_context(text: str) -> str:
    """
    Enhance text with semantic context for better embedding matching.
    """
    try:
        # Add semantic context for common product categories
        text_lower = text.lower()
        enhancements = []
        
        # Product category enhancements
        if any(word in text_lower for word in ['shoe', 'shoes', 'sneaker', 'boot']):
            enhancements.append('footwear')
        
        if any(word in text_lower for word in ['shirt', 'tshirt', 't-shirt', 'top', 'blouse']):
            enhancements.append('clothing apparel')
        
        if any(word in text_lower for word in ['watch', 'watches', 'timepiece']):
            enhancements.append('accessories timepiece')
        
        if any(word in text_lower for word in ['kids', 'children', 'child', 'youth']):
            enhancements.append('children youth')
        
        if any(word in text_lower for word in ['sun', 'sunglasses', 'glasses']):
            enhancements.append('eyewear accessories')
        
        # Price-related context
        if any(word in text_lower for word in ['cheap', 'budget', 'affordable']):
            enhancements.append('budget-friendly')
        
        if any(word in text_lower for word in ['expensive', 'premium', 'luxury']):
            enhancements.append('premium quality')
        
        # Combine original text with enhancements
        if enhancements:
            enhanced = f"{text} {' '.join(enhancements)}"
            return enhanced
        
        return text
        
    except Exception as e:
        print(f"⚠️  Semantic enhancement failed: {e}")
        return text

# Advanced embedding generation with multilingual support
def get_multilingual_embedding(text: str, language: str = 'en') -> list:
    """
    Generate embeddings optimized for specific languages.
    """
    try:
        # Language-specific preprocessing
        if language in ['hi', 'hindi']:
            # Hindi-specific preprocessing
            processed_text = f"hindi product search: {text}"
        elif language in ['es', 'spanish']:
            # Spanish-specific preprocessing  
            processed_text = f"producto español: {text}"
        elif language in ['fr', 'french']:
            # French-specific preprocessing
            processed_text = f"produit français: {text}"
        else:
            # English or default
            processed_text = text
        
        return get_google_embedding(processed_text)
        
    except Exception as e:
        print(f"Multilingual embedding failed: {e}")
        return get_google_embedding(text)  # Fallback to regular embedding

# Initialize SAP Generative AI LLM (commented out as using Google)
# sap_generative_ai_llm = ChatOpenAI(proxy_model_name="gpt-4o", temperature=0.4, max_tokens=4096)

# Initialize SAP Generative AI embeddings (commented out as using Google)
#def get_sapGenAI_embedding(text) -> str:  
#    response = embeddings.create(
#      model_name="text-embedding-ada-002",
#      input=text
#    )
#    return response.data[0].embedding
