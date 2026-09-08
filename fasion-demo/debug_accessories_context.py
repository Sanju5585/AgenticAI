#!/usr/bin/env python3
"""
Debug script to test accessories context extraction and memory functionality
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from memory_store import SessionMemory
from langchain_core.messages import HumanMessage, AIMessage
import re
import json

def test_memory_and_accessories():
    """Test memory retention and accessories extraction"""
    
    print("=== DEBUGGING ACCESSORIES CONTEXT EXTRACTION ===")
    
    # Initialize memory
    memory = SessionMemory()
    session_id = "default"  # Use same session as the app
    
    # Step 1: Simulate previous search with products displayed
    print("\n1. SIMULATING PREVIOUS PRODUCT SEARCH...")
    
    # User searches for jackets
    user_message_1 = HumanMessage(content="show me jackets")
    
    # AI responds with product results (this is what would be saved in a real conversation)
    ai_response_1 = AIMessage(content="""
    Here are some great jackets I found for you:

    1. **Leather Jacket** (ID: 0032-1) - £120.00
       A stylish leather jacket perfect for casual outings
    
    2. **Beacon Jacket** (ID: 100191) - £85.50  
       Comfortable and versatile beacon jacket for outdoor activities
    
    3. **Tracker Insulated Jacket Youth** (ID: 102284) - £95.00
       Insulated jacket designed for youth, perfect for winter

    {"results": [
        {"PRODUCT_ID": "0032-1", "PRODUCT_NAME": "Leather Jacket", "PRICE": 120.00, "IMAGE_URL": "http://example.com/leather.jpg"},
        {"PRODUCT_ID": "100191", "PRODUCT_NAME": "Beacon Jacket", "PRICE": 85.50, "IMAGE_URL": "http://example.com/beacon.jpg"},
        {"PRODUCT_ID": "102284", "PRODUCT_NAME": "Tracker Insulated Jacket Youth", "PRICE": 95.00, "IMAGE_URL": "http://example.com/tracker.jpg"}
    ]}
    """)
    
    # Save to memory (this simulates what happens in the real app)
    memory.save(session_id, [user_message_1, ai_response_1])
    print("✓ Saved jacket search conversation to memory")
    
    # Step 2: Test memory retrieval
    print("\n2. TESTING MEMORY RETRIEVAL...")
    
    recent_context = memory.get_recent_context(session_id, num_pairs=3)
    print(f"Retrieved {len(recent_context)} conversation pairs from memory")
    
    for i, pair in enumerate(recent_context):
        print(f"\nPair {i+1}:")
        print(f"  User: {pair.get('user', '')[:50]}...")
        print(f"  AI: {pair.get('ai', '')[:100]}...")
    
    # Step 3: Test product extraction from memory
    print("\n3. TESTING PRODUCT EXTRACTION FROM MEMORY...")
    
    extracted_products = memory.extract_last_products(session_id)
    print(f"Extracted {len(extracted_products)} products from memory:")
    
    for product in extracted_products:
        print(f"  - ID: {product.get('product_id')}")
        print(f"    Name: {product.get('product_name')}")
        print(f"    Method: {product.get('extraction_method', 'unknown')}")
    
    # Step 4: Simulate user asking for accessories
    print("\n4. SIMULATING ACCESSORIES REQUEST...")
    
    user_query = "show me accessories of these products"
    print(f"User query: '{user_query}'")
    
    # Test keyword detection
    keywords = [
        'accessories', 'accessory', 'of these', 'of those', 'for these', 'for those',
        'go with', 'match', 'complement', 'accessories of these products', 
        'accessories for these', 'accessories of these', 'what goes with these',
        'show accessories', 'find accessories', 'get accessories'
    ]
    
    trigger_detected = any(keyword in user_query.lower() for keyword in keywords)
    print(f"Accessory trigger detected: {trigger_detected}")
    
    # Step 5: Test the full extraction logic like in find_accessories
    print("\n5. TESTING FULL EXTRACTION LOGIC...")
    
    extracted_products_full = []
    
    # Strategy 1: Look for structured context (none in this test)
    print("Strategy 1: Looking for structured context...")
    product_ids_match = re.search(r'\[PRODUCT_IDS:\s*([^\]]*)\]', user_query)
    if product_ids_match:
        print("Found structured context")
    else:
        print("No structured context found")
    
    # Strategy 2: JSON context (none in this test)
    print("Strategy 2: Looking for JSON context...")
    context_match = re.search(r'\[CONVERSATION_CONTEXT:\s*(\{.*?\})\]', user_query, re.DOTALL)
    if context_match:
        print("Found JSON context")
    else:
        print("No JSON context found")
    
    # Strategy 3: Memory extraction (this should work)
    print("Strategy 3: Memory extraction...")
    
    if not extracted_products_full:
        print("No structured context found, using memory extraction")
        session_id = "default"
        recent_context = memory.get_recent_context(session_id, num_pairs=5)
        
        # Look for the most recent AI response that contains product information
        for pair in recent_context:
            ai_response = pair.get('ai', '')
            
            print(f"Analyzing AI response: {ai_response[:150]}...")
            
            # Enhanced product extraction patterns
            product_patterns = [
                # Pattern for JSON-like responses with product details
                r'"PRODUCT_ID":\s*"([^"]+)"[^}]*"PRODUCT_NAME":\s*"([^"]+)"',
                r"'PRODUCT_ID':\s*'([^']+)'[^}]*'PRODUCT_NAME':\s*'([^']+)'",
                # Pattern for product listings
                r'Product ID:\s*([^\s,]+)[,\s]*Product Name:\s*([^\n,]+)',
                r'ID:\s*([^\s,]+)[,\s]*Name:\s*([^\n,]+)',
                # Pattern for structured product data
                r'"results":\s*\[[^}]*"PRODUCT_ID":\s*"([^"]+)"[^}]*"PRODUCT_NAME":\s*"([^"]+)"',
                # Pattern for simple product mentions
                r'(\d+)\s*[-:]\s*([A-Z][^,\n.]+(?:jacket|shirt|shoes|watch|pant|dress|coat|bag)[^,\n.]*)',
                # Pattern for bullet points
                r'\*\*([^*]+)\*\*\s*\(ID:\s*([^)]+)\)',
            ]
            
            products_found_in_response = []
            
            for i, pattern in enumerate(product_patterns):
                matches = re.findall(pattern, ai_response, re.IGNORECASE | re.MULTILINE)
                print(f"  Pattern {i+1}: {len(matches)} matches")
                for match in matches:
                    if len(match) >= 2 and match[0].strip() and match[1].strip():
                        # Handle different pattern formats
                        if i == 6:  # Bullet point pattern
                            product_name = match[0].strip()
                            product_id = match[1].strip()
                        else:
                            product_id = match[0].strip()
                            product_name = match[1].strip()
                        
                        product_info = {
                            'name': product_name,
                            'id': product_id,
                            'source': f'memory_pattern_{i+1}'
                        }
                        products_found_in_response.append(product_info)
                        print(f"    Found - ID: {product_id}, Name: {product_name}")
            
            # If we found products in this response, use them
            if products_found_in_response:
                extracted_products_full.extend(products_found_in_response)
                print(f"Found {len(products_found_in_response)} products in recent AI response")
                break  # Use the most recent response with products
    
    print(f"\nFinal extraction result: {len(extracted_products_full)} products")
    for product in extracted_products_full:
        print(f"  - ID: {product['id']}, Name: {product['name']}, Source: {product['source']}")
    
    # Step 6: Test accessories lookup
    if extracted_products_full:
        print("\n6. TESTING ACCESSORIES LOOKUP...")
        from agent import hana_connect
        
        try:
            conn = hana_connect()
            cursor = conn.cursor()
            
            for product_info in extracted_products_full[:2]:  # Test first 2 products
                product_name = product_info.get('name')
                product_id = product_info.get('id')
                
                print(f"\nLooking up accessories for: {product_name} (ID: {product_id})")
                
                # Test exact ID lookup
                cursor.execute("SELECT PRODUCT_IDS FROM SAP_ACCESSORIES_COMMERCE_2211 WHERE TRIM(PRODUCT_ID) = ?", (product_id.strip(),))
                result = cursor.fetchone()
                
                if result and result[0]:
                    accessory_ids = [pid.strip() for pid in result[0].split(',') if pid.strip()]
                    print(f"  Found {len(accessory_ids)} accessories by ID: {accessory_ids}")
                else:
                    print(f"  No accessories found by ID for {product_id}")
                    
                    # Try by name
                    cursor.execute("SELECT PRODUCT_IDS FROM SAP_ACCESSORIES_COMMERCE_2211 WHERE UPPER(PRODUCT_NAME) = UPPER(?)", (product_name,))
                    result = cursor.fetchone()
                    
                    if result and result[0]:
                        accessory_ids = [pid.strip() for pid in result[0].split(',') if pid.strip()]
                        print(f"  Found {len(accessory_ids)} accessories by name: {accessory_ids}")
                    else:
                        print(f"  No accessories found by name for {product_name}")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"Database error: {e}")
    
    print("\n=== DEBUGGING COMPLETE ===")
    return True

if __name__ == "__main__":
    test_memory_and_accessories()