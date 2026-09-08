"""
AI-powered smart query parser for extracting filters from natural language product searches.
Uses semantic understanding and intelligent pattern matching to interpret user intent.
Handles price ranges, colors, sizes, categories, and other product attributes.
"""

import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field


@dataclass
class SearchFilters:
    """Container for parsed search filters"""
    category: Optional[str] = None
    colors: List[str] = field(default_factory=list)
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    sizes: List[str] = field(default_factory=list)
    brands: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    raw_query: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for easy serialization"""
        return {
            "category": self.category,
            "colors": self.colors,
            "price_min": self.price_min,
            "price_max": self.price_max,
            "sizes": self.sizes,
            "brands": self.brands,
            "keywords": self.keywords,
            "raw_query": self.raw_query
        }


class QueryParser:
    """AI-powered parser for natural language product queries with semantic understanding"""
    
    def __init__(self):
        # Enhanced semantic category mapping with broader understanding
        self.semantic_categories = {
            'clothing_tops': {
                'keywords': ['shirt', 'blouse', 'top', 'tee', 't-shirt', 'polo', 'tank', 'sweater', 'hoodie', 'cardigan'],
                'category': 'shirts'
            },
            'clothing_bottoms': {
                'keywords': ['pants', 'jeans', 'trousers', 'slacks', 'khakis', 'chinos', 'shorts', 'leggings'],
                'category': 'pants'
            },
            'footwear': {
                'keywords': ['shoe', 'shoes', 'boot', 'boots', 'sneaker', 'sneakers', 'sandal', 'sandals', 'heel', 'heels', 'flat', 'flats', 'footwear'],
                'category': 'shoes'
            },
            'dresses': {
                'keywords': ['dress', 'dresses', 'gown', 'gowns', 'frock'],
                'category': 'dresses'
            },
            'outerwear': {
                'keywords': ['jacket', 'jackets', 'coat', 'coats', 'blazer', 'blazers'],
                'category': 'jackets'
            },
            'eyewear': {
                'keywords': ['sunglasses', 'sunglass', 'shades', 'shade', 'eyewear', 'glasses', 'aviator', 'aviators'],
                'category': 'sunglasses'
            },
            'timepieces': {
                'keywords': ['watch', 'watches', 'timepiece', 'timepieces', 'chronograph', 'wristwatch', 'wrist watch', 'smartwatch', 'smart watch', 'ghadiya', 'ghadi', 'clock', 'timer'],
                'category': 'watches'
            },
            'accessories': {
                'keywords': ['belt', 'belts', 'hat', 'hats', 'cap', 'caps', 'bag', 'bags', 'purse', 'purses', 'wallet', 'wallets', 'jewelry', 'accessory', 'accessories'],
                'category': 'accessories'
            },
            'underwear': {
                'keywords': ['underwear', 'bra', 'bras', 'panty', 'panties', 'brief', 'briefs', 'boxer', 'boxers', 'lingerie'],
                'category': 'underwear'
            },
            'kids_items': {
                'keywords': ['kids', 'kid', 'children', 'child', 'youth', 'boy', 'girl', 'boys', 'girls', 'toddler', 'infant', 'baby', 'junior', 'teen', 'teenage'],
                'category': 'kids'
            },
            'winter_sports': {
                'keywords': ['snow', 'ski', 'skiing', 'snowboard', 'snowboarding', 'winter', 'alpine', 'mountain'],
                'category': 'snow'
            },
            'water_sports': {
                'keywords': ['surf', 'surfing', 'beach', 'wave', 'ocean', 'boardshort', 'swim', 'swimming'],
                'category': 'surf'
            },
            'casual_wear': {
                'keywords': ['streetwear', 'street', 'urban', 'casual', 'everyday', 'comfortable'],
                'category': 'streetwear'
            },
            'athletic_wear': {
                'keywords': ['sports', 'sport', 'athletic', 'fitness', 'workout', 'training', 'gym', 'running', 'exercise'],
                'category': 'sports'
            },
            'equipment': {
                'keywords': ['tools', 'tool', 'equipment', 'gear', 'maintenance', 'repair'],
                'category': 'tools'
            },
            'protective_gear': {
                'keywords': ['helmet', 'helmets', 'head protection', 'safety', 'protective gear', 'protection'],
                'category': 'helmets'
            },
            'goggles': {
                'keywords': ['goggles', 'goggle', 'vision protection', 'eye protection'],
                'category': 'goggles'
            }
        }
        
        # Enhanced color detection with variations and synonyms
        self.colors = [
            'red', 'blue', 'green', 'yellow', 'black', 'white', 'gray', 'grey',
            'brown', 'pink', 'purple', 'orange', 'navy', 'beige', 'khaki',
            'maroon', 'turquoise', 'magenta', 'cyan', 'gold', 'silver',
            'cream', 'tan', 'olive', 'coral', 'mint', 'lavender', 'crimson',
            'scarlet', 'azure', 'emerald', 'violet', 'indigo', 'rose', 'amber'
        ]
        
        # Enhanced size detection
        self.sizes = [
            'xs', 'x-small', 'extra small',
            's', 'small',
            'm', 'medium', 'med',
            'l', 'large', 
            'xl', 'x-large', 'extra large',
            'xxl', 'xx-large', 'extra extra large',
            '2xl', '3xl', '4xl', '5xl',
            # Numeric sizes
            '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16',
            # European sizes
            '36', '37', '38', '39', '40', '41', '42', '43', '44', '45', '46', '47', '48'
        ]
        
        # Brand recognition
        self.brands = [
            'nike', 'adidas', 'puma', 'reebok', 'under armour', 'calvin klein', 
            'tommy hilfiger', 'gap', 'zara', 'h&m', 'uniqlo', 'levis', 'wrangler',
            'vans', 'converse', 'ray-ban', 'oakley', 'von zipper', 'roxy', 'quiksilver',
            'billabong', 'volcom', 'dc', 'burton', 'element', 'fox', 'anon'
        ]
        
        # Enhanced price pattern regex with more currency support
        self.price_patterns = [
            # "under $60", "below 60", "less than £60", "under 30 pounds"
            r'(?:under|below|less\s+than|max|maximum|up\s+to)\s*[£$€]?(\d+(?:\.\d{2})?)\s*(?:pounds?|dollars?|euros?|gbp|usd|eur)?',
            # "over $50", "above 50", "more than £50", "above 100 dollars"  
            r'(?:over|above|more\s+than|min|minimum|at\s+least)\s*[£$€]?(\d+(?:\.\d{2})?)\s*(?:pounds?|dollars?|euros?|gbp|usd|eur)?',
            # "$30 to $60", "£30-60", "between $30 and $60", "50 to 100 pounds"
            r'(?:between\s+)?[£$€]?(\d+(?:\.\d{2})?)\s*(?:pounds?|dollars?|euros?|gbp|usd|eur)?\s*(?:to|and|-|through)\s*[£$€]?(\d+(?:\.\d{2})?)\s*(?:pounds?|dollars?|euros?|gbp|usd|eur)?',
            # "$60", "60 dollars", "£60", "30 pounds"
            r'[£$€](\d+(?:\.\d{2})?)|(\d+(?:\.\d{2})?)\s*(?:pounds?|dollars?|euros?|gbp|usd|eur)',
            # "around $50", "about £30", "approximately 75 pounds"
            r'(?:around|about|approximately)\s*[£$€]?(\d+(?:\.\d{2})?)\s*(?:pounds?|dollars?|euros?|gbp|usd|eur)?'
        ]
    
    def parse_query(self, query: str) -> SearchFilters:
        """AI-powered parsing of natural language query into structured filters"""
        filters = SearchFilters(raw_query=query)
        query_lower = query.lower().strip()
        
        # Use semantic category detection
        filters.category = self._extract_category_semantic(query_lower)
        
        # Extract colors with enhanced detection
        filters.colors = self._extract_colors_enhanced(query_lower)
        
        # Extract price range with better patterns
        filters.price_min, filters.price_max = self._extract_price_range_enhanced(query_lower)
        
        # Extract sizes with improved detection
        filters.sizes = self._extract_sizes_enhanced(query_lower)
        
        # Extract brands with AI-enhanced detection
        filters.brands = self._extract_brands_enhanced(query_lower)
        
        # Extract intelligent keywords
        filters.keywords = self._extract_keywords_intelligent(query_lower, filters)
        
        return filters
    
    def _extract_category_semantic(self, query: str) -> Optional[str]:
        """AI-powered semantic category detection"""
        # Score each category based on semantic matching
        category_scores = {}
        
        for category_group, config in self.semantic_categories.items():
            score = 0
            keywords = config['keywords']
            
            for keyword in keywords:
                # Exact match gets highest score
                if keyword in query:
                    score += 10
                    
                # Partial match gets medium score
                elif any(keyword in word for word in query.split()):
                    score += 5
                    
                # Similar words get low score (simple similarity)
                elif self._calculate_similarity(keyword, query) > 0.7:
                    score += 2
            
            if score > 0:
                category_scores[config['category']] = score
        
        # Return category with highest score
        if category_scores:
            return max(category_scores, key=category_scores.get)
        
        return None
    
    def _calculate_similarity(self, word: str, text: str) -> float:
        """Simple similarity calculation for fuzzy matching"""
        if word in text:
            return 1.0
        
        # Check for common prefixes/suffixes
        for text_word in text.split():
            if len(word) > 3 and len(text_word) > 3:
                # Calculate character overlap
                overlap = len(set(word) & set(text_word))
                max_len = max(len(word), len(text_word))
                similarity = overlap / max_len
                
                if similarity > 0.7:
                    return similarity
        
        return 0.0
    
    def _extract_colors_enhanced(self, query: str) -> List[str]:
        """Enhanced color detection with context awareness"""
        found_colors = []
        
        for color in self.colors:
            # Look for color with word boundaries and context
            pattern = r'\b' + re.escape(color) + r'\b'
            if re.search(pattern, query, re.IGNORECASE):
                found_colors.append(color)
        
        return found_colors
    
    def _extract_price_range_enhanced(self, query: str) -> Tuple[Optional[float], Optional[float]]:
        """Enhanced price range extraction with better pattern matching and currency support"""
        price_min, price_max = None, None
        
        # CRITICAL: Check for range patterns FIRST (highest priority)
        # "30 to 60", "50-100 pounds", "between £30 and £60"
        range_pattern = r'(?:between\s+)?[£$€]?(\d+(?:\.\d{2})?)\s*(?:pounds?|dollars?|euros?|gbp|usd|eur)?\s*(?:to|and|-|through)\s*[£$€]?(\d+(?:\.\d{2})?)\s*(?:pounds?|dollars?|euros?|gbp|usd|eur)?'
        range_match = re.search(range_pattern, query, re.IGNORECASE)
        if range_match:
            price_min = float(range_match.group(1))
            price_max = float(range_match.group(2))
            print(f"✅ Found price range: {price_min} to {price_max}")
            return price_min, price_max  # Return immediately to avoid conflicts
        
        # Check for "under/below" patterns - "under 100 pounds", "below £50"
        under_pattern = r'(?:under|below|less\s+than|max|maximum|up\s+to)\s*[£$€]?(\d+(?:\.\d{2})?)\s*(?:pounds?|dollars?|euros?|gbp|usd|eur)?'
        under_match = re.search(under_pattern, query, re.IGNORECASE)
        if under_match:
            price_max = float(under_match.group(1))
            print(f"✅ Found price maximum: {price_max}")
        
        # Check for "over/above" patterns - "over 50 pounds", "above $100"
        over_pattern = r'(?:over|above|more\s+than|min|minimum|at\s+least)\s*[£$€]?(\d+(?:\.\d{2})?)\s*(?:pounds?|dollars?|euros?|gbp|usd|eur)?'
        over_match = re.search(over_pattern, query, re.IGNORECASE)
        if over_match:
            price_min = float(over_match.group(1))
            print(f"✅ Found price minimum: {price_min}")
        
        # Check for "around/about" patterns (set as approximate range) - "around 75 pounds"
        if not price_min and not price_max:  # Only if no other pattern matched
            approx_pattern = r'(?:around|about|approximately)\s*[£$€]?(\d+(?:\.\d{2})?)\s*(?:pounds?|dollars?|euros?|gbp|usd|eur)?'
            approx_match = re.search(approx_pattern, query, re.IGNORECASE)
            if approx_match:
                price = float(approx_match.group(1))
                price_min = price * 0.8  # 20% below
                price_max = price * 1.2  # 20% above
                print(f"✅ Found approximate price: {price} (range: {price_min} to {price_max})")
        
        return price_min, price_max
    
    def _extract_sizes_enhanced(self, query: str) -> List[str]:
        """Enhanced size detection with context awareness"""
        found_sizes = []
        
        # Look for size patterns with context
        size_patterns = [
            r'\bsize\s+(\w+)\b',  # "size 10", "size medium"
            r'\b(\w+)\s+size\b',  # "10 size", "medium size"
            r'\bin\s+(\w+)\b',    # "in medium", "in large"
            r'\b(\w+)\s+(?:only|available)\b',  # "medium only", "large available"
        ]
        
        for pattern in size_patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                if match.lower() in [s.lower() for s in self.sizes]:
                    if match.lower() not in [s.lower() for s in found_sizes]:
                        found_sizes.append(match.lower())
        
        # Also check for standalone sizes with word boundaries
        for size in self.sizes:
            if re.search(r'\b' + re.escape(size) + r'\b', query, re.IGNORECASE):
                if size.lower() not in [s.lower() for s in found_sizes]:
                    found_sizes.append(size.lower())
        
        return found_sizes
    
    def _extract_brands_enhanced(self, query: str) -> List[str]:
        """Enhanced brand detection with fuzzy matching"""
        found_brands = []
        
        for brand in self.brands:
            # Exact match with word boundaries
            if re.search(r'\b' + re.escape(brand) + r'\b', query, re.IGNORECASE):
                found_brands.append(brand)
            # Fuzzy match for partial brand names
            elif self._calculate_similarity(brand, query) > 0.8:
                found_brands.append(brand)
        
        return found_brands
    
    def _extract_keywords_intelligent(self, query: str, filters: SearchFilters) -> List[str]:
        """Intelligent keyword extraction that preserves meaningful terms"""
        # Start with the original query
        remaining = query
        
        # Remove price expressions
        price_expressions = [
            r'(?:under|below|less\s+than|max|maximum|up\s+to)\s*[£$€]?\d+(?:\.\d{2})?',
            r'(?:over|above|more\s+than|min|minimum|at\s+least)\s*[£$€]?\d+(?:\.\d{2})?',
            r'(?:between\s+)?[£$€]?\d+(?:\.\d{2})?\s*(?:to|and|-|through)\s*[£$€]?\d+(?:\.\d{2})?',
            r'(?:around|about|approximately)\s*[£$€]?\d+(?:\.\d{2})?',
            r'[£$€]\d+(?:\.\d{2})?',
        ]
        
        for pattern in price_expressions:
            remaining = re.sub(pattern, '', remaining, flags=re.IGNORECASE)
        
        # Remove size expressions
        remaining = re.sub(r'\bsize\s+\w+\b', '', remaining, flags=re.IGNORECASE)
        remaining = re.sub(r'\b\w+\s+size\b', '', remaining, flags=re.IGNORECASE)
        remaining = re.sub(r'\bin\s+\w+\b', '', remaining, flags=re.IGNORECASE)
        
        # Remove colors
        for color in filters.colors:
            remaining = re.sub(r'\b' + re.escape(color) + r'\b', '', remaining, flags=re.IGNORECASE)
        
        # Remove brands
        for brand in filters.brands:
            remaining = re.sub(r'\b' + re.escape(brand) + r'\b', '', remaining, flags=re.IGNORECASE)
        
        # Remove category keywords that were already detected
        if filters.category:
            for category_group, config in self.semantic_categories.items():
                if config['category'] == filters.category:
                    for keyword in config['keywords']:
                        remaining = re.sub(r'\b' + re.escape(keyword) + r'\b', '', remaining, flags=re.IGNORECASE)
                    break
        
        # Clean up and extract meaningful words
        remaining = re.sub(r'[^\w\s]', ' ', remaining)  # Remove punctuation
        words = [word.strip() for word in remaining.split() if len(word.strip()) > 2]
        
        # Remove common stop words but keep meaningful descriptors
        stop_words = {
            'with', 'the', 'and', 'for', 'are', 'show', 'find', 'get', 'me', 'some', 'any',
            'want', 'need', 'looking', 'search', 'buy', 'purchase', 'have', 'has',
            'this', 'that', 'these', 'those', 'can', 'could', 'would', 'should'
        }
        keywords = [word for word in words if word.lower() not in stop_words]
        
        return keywords


def build_search_query(filters: SearchFilters) -> str:
    """Build a search query string from parsed filters with price consideration"""
    query_parts = []
    
    # Add category if specified
    if filters.category:
        query_parts.append(filters.category)
    
    # Add colors
    if filters.colors:
        query_parts.extend(filters.colors)
    
    # Add remaining keywords (but filter out price-related terms)
    if filters.keywords:
        # Filter out price-related keywords that aren't useful for search
        price_keywords = {'pounds', 'dollars', 'euros', 'gbp', 'usd', 'eur', 'under', 'over', 'between', 'below', 'above'}
        useful_keywords = [kw for kw in filters.keywords if kw.lower() not in price_keywords]
        query_parts.extend(useful_keywords)
    
    # If no specific parts but we have price filters, use category or generic search
    if not query_parts:
        if filters.category:
            query_parts.append(filters.category)
        elif filters.raw_query:
            # Remove price expressions from raw query for search
            cleaned_query = filters.raw_query
            price_expressions = [
                r'(?:under|below|less\s+than|max|maximum|up\s+to)\s*[£$€]?\d+(?:\.\d{2})?\s*(?:pounds?|dollars?|euros?|gbp|usd|eur)?',
                r'(?:over|above|more\s+than|min|minimum|at\s+least)\s*[£$€]?\d+(?:\.\d{2})?\s*(?:pounds?|dollars?|euros?|gbp|usd|eur)?',
                r'(?:between\s+)?[£$€]?\d+(?:\.\d{2})?\s*(?:pounds?|dollars?|euros?|gbp|usd|eur)?\s*(?:to|and|-|through)\s*[£$€]?\d+(?:\.\d{2})?\s*(?:pounds?|dollars?|euros?|gbp|usd|eur)?',
                r'(?:around|about|approximately)\s*[£$€]?\d+(?:\.\d{2})?\s*(?:pounds?|dollars?|euros?|gbp|usd|eur)?'
            ]
            
            for pattern in price_expressions:
                cleaned_query = re.sub(pattern, '', cleaned_query, flags=re.IGNORECASE)
            
            # Clean up extra spaces and return meaningful terms
            cleaned_query = re.sub(r'\s+', ' ', cleaned_query.strip())
            if cleaned_query:
                return cleaned_query
    
    # If still no query parts, use a generic search
    if not query_parts:
        return ''
    
    return ' '.join(query_parts)


def filter_products_by_criteria(products: List[Dict], filters: SearchFilters) -> List[Dict]:
    """Filter product results based on parsed criteria with enhanced price handling"""
    if not products:
        return products
    
    filtered = []
    
    for product in products:
        # Category filtering (check if product matches the desired category)
        if filters.category:
            product_text_fields = [
                product.get('name', ''),
                product.get('PRODUCT_NAME', ''),
                product.get('description', ''),
                product.get('SUMMARY', ''),
                product.get('summary', ''),
                product.get('categories', ''),
                product.get('CATEGORY_IDS', '')
            ]
            product_text = ' '.join(filter(None, product_text_fields)).lower()
            
            # Check if the product matches the category
            category_match = False
            
            # Direct category name match
            if filters.category.lower() in product_text:
                category_match = True
            
            # Check for category synonyms
            category_synonyms = {
                'shirts': ['shirt', 'tee', 't-shirt', 'top', 'blouse'],
                'shoes': ['shoe', 'boot', 'sneaker', 'sandal', 'footwear'],
                'jackets': ['jacket', 'coat', 'blazer', 'outerwear'],
                'watches': ['watch', 'timepiece', 'chronograph'],
                'accessories': ['belt', 'bag', 'hat', 'cap', 'wallet'],
                'pants': ['pant', 'jean', 'trouser', 'short'],
                'dresses': ['dress', 'gown', 'frock']
            }
            
            if filters.category in category_synonyms:
                for synonym in category_synonyms[filters.category]:
                    if synonym in product_text:
                        category_match = True
                        break
            
            if not category_match:
                continue
        
        # Enhanced price filtering with better format handling
        if filters.price_min is not None or filters.price_max is not None:
            product_price = None
            
            # Try to extract price from different possible fields and formats
            price_value = product.get('price') or product.get('PRICE') or product.get('cost')
            
            if price_value is not None:
                try:
                    # Handle different price formats
                    if isinstance(price_value, str):
                        # Remove currency symbols and extra spaces
                        price_str = price_value.strip().replace('£', '').replace('$', '').replace('€', '').replace(',', '')
                        product_price = float(price_str)
                    else:
                        product_price = float(price_value)
                except (ValueError, TypeError):
                    # If price parsing fails, skip price filtering for this product
                    print(f"Warning: Could not parse price '{price_value}' for product {product.get('code', 'unknown')}")
                    product_price = None
            
            # Apply price filters if we have a valid price
            if product_price is not None:
                if filters.price_min is not None and product_price < filters.price_min:
                    continue
                
                if filters.price_max is not None and product_price > filters.price_max:
                    continue
        
        # Color filtering (enhanced to check multiple fields)
        if filters.colors:
            product_text_fields = [
                product.get('name', ''),
                product.get('PRODUCT_NAME', ''),
                product.get('description', ''),
                product.get('SUMMARY', ''),
                product.get('summary', '')
            ]
            product_text = ' '.join(filter(None, product_text_fields)).lower()
            
            if not any(color.lower() in product_text for color in filters.colors):
                continue
        
        # Size filtering (enhanced to check multiple fields)
        if filters.sizes:
            product_text_fields = [
                product.get('name', ''),
                product.get('PRODUCT_NAME', ''),
                product.get('description', ''),
                product.get('SUMMARY', ''),
                product.get('summary', '')
            ]
            product_text = ' '.join(filter(None, product_text_fields)).lower()
            
            if not any(size.lower() in product_text for size in filters.sizes):
                continue
        
        # Brand filtering (enhanced to check multiple fields)
        if filters.brands:
            product_text_fields = [
                product.get('name', ''),
                product.get('PRODUCT_NAME', ''),
                product.get('brand', ''),
                product.get('BRAND', ''),
                product.get('manufacturer', '')
            ]
            product_text = ' '.join(filter(None, product_text_fields)).lower()
            
            if not any(brand.lower() in product_text for brand in filters.brands):
                continue
        
        # If we get here, the product passes all filters
        filtered.append(product)
    
    return filtered


# Global parser instance
query_parser = QueryParser()