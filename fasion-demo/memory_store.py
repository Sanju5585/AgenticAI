from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from collections import defaultdict
import json
from datetime import datetime, timedelta

class SessionMemory:
    def __init__(self):
        self.sessions = defaultdict(list)  # session_id -> list of messages
        self.max_history_length = 20  # Maximum conversation pairs to keep
        
    def save(self, session_id, messages):
        """Save messages to session memory with context preservation"""
        for msg in messages:
            self.sessions[session_id].append(msg)
        
        # Keep only recent conversation pairs to prevent memory overflow
        if len(self.sessions[session_id]) > self.max_history_length * 2:
            # Keep system message if exists, then recent conversation
            system_messages = [msg for msg in self.sessions[session_id] if isinstance(msg, SystemMessage)]
            recent_messages = self.sessions[session_id][-(self.max_history_length * 2):]
            self.sessions[session_id] = system_messages + recent_messages

    def load(self, session_id):
        """Load conversation history for session"""
        return self.sessions[session_id]

    def clear(self, session_id):
        """Clear conversation history for session"""
        self.sessions[session_id] = []
    
    def get_recent_context(self, session_id, num_pairs=3):
        """Get recent conversation context for smart responses"""
        messages = self.sessions[session_id]
        
        # Extract recent human-AI message pairs
        conversation_pairs = []
        human_msg = None
        
        for msg in messages[-10:]:  # Look at last 10 messages
            if isinstance(msg, HumanMessage):
                if human_msg:  # Previous human message without AI response
                    conversation_pairs.append({"human": human_msg.content, "ai": ""})
                human_msg = msg
            elif isinstance(msg, AIMessage) and human_msg:
                conversation_pairs.append({
                    "human": human_msg.content,
                    "ai": msg.content
                })
                human_msg = None
        
        # Add any remaining human message
        if human_msg:
            conversation_pairs.append({"human": human_msg.content, "ai": ""})
        
        return conversation_pairs[-num_pairs:] if conversation_pairs else []
    
    def extract_last_products(self, session_id):
        """Enhanced extraction of products from the last conversation for context-aware queries"""
        messages = self.sessions[session_id]
        
        # Look for AI responses that might contain product information
        for msg in reversed(messages[-15:]):  # Check last 15 messages (increased for better context)
            if isinstance(msg, AIMessage):
                content = msg.content
                
                # Enhanced product detection with more keywords
                if any(keyword in content.lower() for keyword in [
                    'product_id', 'product_name', 'jacket', 'shoes', 'shirt', 'watch', 'product',
                    'coat', 'pant', 'dress', 'bag', 'accessory', 'clothing', 'item', 'found'
                ]):
                    print(f"🧠 MEMORY DEBUG: Analyzing content for products: {content[:200]}...")
                    products = self._parse_product_context(content)
                    if products:
                        print(f"🧠 MEMORY DEBUG: Successfully extracted {len(products)} products")
                        return products
        
        return []
    
    def extract_last_query_category(self, session_id):
        """Extract the product category/type from the last user query"""
        messages = self.sessions[session_id]
        
        # Category keywords mapping
        category_keywords = {
            'tshirt': ['tshirt', 't-shirt', 't shirt', 'tshirts', 't-shirts'],
            'jacket': ['jacket', 'jackets', 'coat', 'coats'],
            'shoes': ['shoe', 'shoes', 'sneaker', 'sneakers', 'footwear'],
            'watch': ['watch', 'watches', 'timepiece'],
            'sunglasses': ['sunglass', 'sunglasses', 'shades'],
            'pants': ['pant', 'pants', 'trouser', 'trousers'],
            'dress': ['dress', 'dresses'],
            'bag': ['bag', 'bags', 'backpack', 'handbag'],
            'accessory': ['accessory', 'accessories'],
            'shirt': ['shirt', 'shirts', 'blouse']
        }
        
        # Look at the last few human messages
        for msg in reversed(messages[-10:]):
            if isinstance(msg, HumanMessage):
                query = msg.content.lower()
                print(f"🧠 CATEGORY DEBUG: Checking query: {query}")
                
                # Check for category keywords
                for category, keywords in category_keywords.items():
                    if any(keyword in query for keyword in keywords):
                        print(f"🧠 CATEGORY DEBUG: Found category '{category}' in query")
                        return category
        
        print(f"🧠 CATEGORY DEBUG: No category found in recent queries")
        return None
    
    def _parse_product_context(self, content):
        """Enhanced parsing of product context from AI message content"""
        products = []
        import re
        
        print(f"🧠 MEMORY DEBUG: Parsing content: {content[:300]}...")
        
        # Enhanced product extraction patterns
        patterns = [
            # JSON-style patterns
            (r'"PRODUCT_ID":\s*"([^"]+)"[^}]*"PRODUCT_NAME":\s*"([^"]+)"', 'json_style'),
            (r"'PRODUCT_ID':\s*'([^']+)'[^}]*'PRODUCT_NAME':\s*'([^']+)'", 'json_style_single'),
            
            # Structured patterns
            (r'Product ID:\s*([^\s,\n]+)[,\s]*Product Name:\s*([^\n,]+)', 'structured'),
            (r'ID:\s*([^\s,\n]+)[,\s]*Name:\s*([^\n,]+)', 'structured_short'),
            
            # Results array patterns
            (r'"results":\s*\[[^}]*"PRODUCT_ID":\s*"([^"]+)"[^}]*"PRODUCT_NAME":\s*"([^"]+)"', 'results_array'),
            
            # Natural language patterns
            (r'(\d{5,})\s*[-:]\s*([A-Z][^,\n.]+(?:jacket|shirt|shoes|watch|pant|dress|coat|bag)[^,\n.]*)', 'natural_language'),
            
            # Simple product mentions with IDs
            (r'(\d{5,})[^\w]*([A-Z][^,\n]*(?:jacket|shirt|shoes|watch|pant|dress|coat|bag)[^,\n]*)', 'simple_mention'),
            
            # Markdown-style patterns for formatted responses
            (r'\*\*([^*]+)\*\*[^(]*\(ID:\s*([^)]+)\)', 'markdown_with_id'),
            (r'\*\s*\*\*([^*]+)\*\*:', 'markdown_bullet_title'),
            
            # NEW: Structured product data patterns (from enhanced memory storage)
            (r'"product_id":\s*"([^"]+)"[^}]*"product_name":\s*"([^"]+)"', 'structured_product_data'),
            (r"'product_id':\s*'([^']+)'[^}]*'product_name':\s*'([^']+)'", 'structured_product_data_single'),
            
            # NEW: Structured products array pattern
            (r'\[STRUCTURED_PRODUCTS:\s*([^\]]+)\]', 'structured_products_array'),
        ]
        
        for pattern, pattern_type in patterns:
            # Special handling for structured products array
            if pattern_type == 'structured_products_array':
                matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE | re.DOTALL)
                print(f"🧠 MEMORY DEBUG: Pattern '{pattern_type}' found {len(matches)} matches")
                
                for match in matches:
                    try:
                        # Parse the JSON array
                        import json
                        products_array = json.loads(match)
                        print(f"🧠 MEMORY DEBUG: Parsed structured products array with {len(products_array)} products")
                        
                        for product in products_array:
                            if product.get('product_id') and product.get('product_name'):
                                products.append({
                                    "product_id": product['product_id'].strip(),
                                    "product_name": product['product_name'].strip(),
                                    "extraction_method": pattern_type
                                })
                                print(f"🧠 MEMORY DEBUG: Extracted from structured array - ID: {product['product_id'].strip()}, Name: {product['product_name'].strip()}")
                    except (json.JSONDecodeError, KeyError) as e:
                        print(f"🧠 MEMORY DEBUG: Failed to parse structured products array: {e}")
                continue
            
            matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
            print(f"🧠 MEMORY DEBUG: Pattern '{pattern_type}' found {len(matches)} matches")
            
            for match in matches:
                if len(match) >= 2 and match[0].strip() and match[1].strip():
                    product_id = match[0].strip()
                    product_name = match[1].strip()
                    
                    # Clean up product name
                    product_name = re.sub(r'["\']', '', product_name)  # Remove quotes
                    product_name = product_name.split(',')[0]  # Take first part if comma-separated
                    
                    if len(product_name) > 3:  # Valid product name
                        products.append({
                            "product_id": product_id,
                            "product_name": product_name,
                            "extraction_method": pattern_type
                        })
                        print(f"🧠 MEMORY DEBUG: Extracted - ID: {product_id}, Name: {product_name}")
        
        # If no structured patterns worked, try a more liberal approach
        if not products:
            print("🧠 MEMORY DEBUG: No structured patterns worked, trying liberal extraction")
            
            # Find all product IDs (5+ digits)
            product_ids = re.findall(r'\b(\d{5,})\b', content)
            
            # Find product-related terms
            product_terms = re.findall(r'\b([A-Z][^,\n.]*(?:jacket|shirt|shoes|watch|pant|dress|coat|bag)[^,\n.]*)', content, re.IGNORECASE)
            
            # Combine them if we have both
            if product_ids and product_terms:
                for i in range(min(len(product_ids), len(product_terms), 5)):  # Limit to 5
                    products.append({
                        "product_id": product_ids[i],
                        "product_name": product_terms[i].strip(),
                        "extraction_method": "liberal"
                    })
                    print(f"🧠 MEMORY DEBUG: Liberal extraction - ID: {product_ids[i]}, Name: {product_terms[i].strip()}")
            
            # If still nothing, just extract product IDs
            elif product_ids:
                for pid in product_ids[:5]:  # Limit to 5
                    products.append({
                        "product_id": pid,
                        "product_name": f"Product {pid}",
                        "extraction_method": "id_only"
                    })
                    print(f"🧠 MEMORY DEBUG: ID-only extraction - ID: {pid}")
        
        print(f"🧠 MEMORY DEBUG: Final extraction result: {len(products)} products")
        return products[:5]  # Return up to 5 recent products
