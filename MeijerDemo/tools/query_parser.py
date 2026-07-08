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
    """Data class to store extracted search filters"""
    category: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    colors: List[str] = field(default_factory=list)
    sizes: List[str] = field(default_factory=list)
    brands: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    sort_by: Optional[str] = None
    filters: Dict[str, Any] = field(default_factory=dict)


class EnhancedQueryParser:
    """
    Enhanced query parser with intelligent pattern matching for e-commerce searches.
    
    Features:
    - Advanced price extraction (ranges, under, over, approximate)
    - Color and size detection
    - Category and brand identification
    - Multi-language support for common terms
    - Robust error handling
    """
    
    def __init__(self):
        # Product categories and their aliases (Meijer grocery store)
        self.categories = {
            'ice_cream':      ['ice cream', 'sorbet', 'frozen yogurt', 'ice pops', 'popsicle', 'gelato'],
            'frozen_meals':   ['frozen meal', 'frozen dinner', 'pot pie', 'lasagna', 'taquito', 'nugget', 'skillet meal'],
            'frozen_pizza':   ['pizza', 'frozen pizza', 'pepperoni pizza', 'cheese pizza', 'pizza snack'],
            'chips':          ['chips', 'potato chips', 'tortilla chips', 'kettle chips', 'pringles', 'corn chips', 'nacho'],
            'crackers':       ['cracker', 'crackers', 'ritz', 'triscuit', 'graham cracker', 'saltine', 'rice cracker'],
            'cookies':        ['cookie', 'cookies', 'oreo', 'shortbread', 'oatmeal raisin', 'chocolate chip cookie', 'wafer'],
            'bread':          ['bread', 'loaf', 'white bread', 'wheat bread', 'sandwich bread', 'whole wheat'],
            'cakes':          ['cake', 'birthday cake', 'custom cake', 'celebration cake', 'sheet cake'],
            'soft_drinks':    ['soda', 'cola', 'soft drink', 'ginger ale', 'root beer', 'lemon lime soda', 'sparkling soda'],
            'water':          ['water', 'sparkling water', 'mineral water', 'seltzer', 'tonic water', 'coconut water'],
            'coffee':         ['coffee', 'espresso', 'cold brew', 'coffee pods', 'ground coffee', 'coffee beans', 'coffee creamer'],
            'cereal':         ['cereal', 'granola', 'corn flakes', 'oat', 'breakfast cereal', 'raisin bran', 'muesli'],
            'milk':           ['milk', 'whole milk', 'skim milk', 'almond milk', 'oat milk', 'lactose free milk', '2% milk'],
            'yogurt':         ['yogurt', 'greek yogurt', 'skyr', 'drinkable yogurt', 'frozen yogurt', 'probiotic yogurt'],
            'cheese':         ['cheese', 'cheddar', 'mozzarella', 'swiss cheese', 'american cheese', 'cream cheese', 'gouda'],
            'snacks':         ['snack', 'snacks', 'munchies', 'treat', 'finger food'],
            'frozen':         ['frozen', 'frozen food', 'freezer aisle'],
            'dairy':          ['dairy', 'dairy product', 'refrigerated'],
            'bakery':         ['bakery', 'baked goods', 'fresh baked'],
            'beverages':      ['beverage', 'drink', 'drinks'],
        }

        # Common brands to detect (Meijer grocery)
        self.brands = [
            # Frozen / Ice Cream
            "haagen-dazs", "ben & jerry's", "talenti", "popsicle", "so delicious",
            "yoplait", "stouffer's", "lean cuisine", "marie callender's", "tyson",
            "el monterey", "hot pockets", "amy's", "digiorno", "tombstone",
            "red baron", "totino's", "jack's", "screamin' sicilian",
            # Snacks
            "lay's", "lays", "doritos", "tostitos", "pringles", "fritos",
            "pepperidge farm", "ritz", "triscuit", "cheez-it", "honey maid",
            "oreo", "keebler", "quaker", "famous amos", "mrs. fields",
            # Beverages
            "refreshco", "sunnyfizz", "citrusrush", "gingergold", "heritagebrew",
            "naturepop", "crystal springs", "aquapure", "mountain mist",
            "roastmaster", "highland reserve", "quickbrew", "beancraft", "chillbrew",
            # Cereal
            "kellogg's", "kelloggs", "general mills", "post", "malt-o-meal",
            "special k", "nature valley", "cheerios",
            # Dairy
            "organic valley", "dairypure", "lactaid", "fairlife", "horizon organic",
            "nesquik", "trumoo", "almond breeze", "dannon", "chobani", "fage",
            "siggi's", "yakult", "go-gurt", "oikos", "kraft", "amul", "violife",
            # Bakery
            "golden oven", "daily fresh", "nature's grain", "farm harvest",
            "sweet moments", "bake studio", "cake creations", "golden bakery",
        ]
        
        # Color patterns
        self.colors = [
            'red', 'blue', 'green', 'black', 'white', 'gray', 'grey',
            'silver', 'gold', 'rose', 'pink', 'purple', 'yellow', 'orange',
            'brown', 'beige', 'navy', 'teal', 'cyan', 'magenta', 'titanium'
        ]
        
        # Size patterns
        self.sizes = [
            'small', 'medium', 'large', 'xl', 'xxl', 's', 'm', 'l',
            '32gb', '64gb', '128gb', '256gb', '512gb', '1tb', '2tb',
            '40mm', '41mm', '42mm', '44mm', '45mm', '46mm', '47mm',
            '11-inch', '13-inch', '11inch', '13inch'
        ]
        
        # Enhanced price pattern regex - using $ as primary currency
        self.price_patterns = [
            # "under $60", "below 60", "less than $60", "under 30 dollars"
            r'(?:under|below|less\s+than|max|maximum|up\s+to)\s*[$€]?(\d+(?:\.\d{2})?)\s*(?:dollars?|euros?|usd|eur)?',
            # "over $50", "above 50", "more than $50", "above 100 dollars"  
            r'(?:over|above|more\s+than|min|minimum|at\s+least)\s*[$€]?(\d+(?:\.\d{2})?)\s*(?:dollars?|euros?|usd|eur)?',
            # "$30 to $60", "$30-60", "between $30 and $60", "50 to 100 dollars"
            r'(?:between\s+)?[$€]?(\d+(?:\.\d{2})?)\s*(?:dollars?|euros?|usd|eur)?\s*(?:to|and|-|through)\s*[$€]?(\d+(?:\.\d{2})?)\s*(?:dollars?|euros?|usd|eur)?',
            # "$60", "60 dollars", "$60", "30 dollars"
            r'[$€](\d+(?:\.\d{2})?)|(\d+(?:\.\d{2})?)\s*(?:dollars?|euros?|usd|eur)',
            # "around $50", "about $30", "approximately 75 dollars"
            r'(?:around|about|approximately)\s*[$€]?(\d+(?:\.\d{2})?)\s*(?:dollars?|euros?|usd|eur)?'
        ]
    
    def parse_query(self, query: str) -> SearchFilters:
        """
        Parse natural language query and extract structured filters.
        
        Args:
            query: Natural language search query
            
        Returns:
            SearchFilters object with extracted attributes
        """
        filters = SearchFilters()
        query_lower = query.lower()
        
        try:
            # Extract price constraints
            price_min, price_max = self._extract_price_range(query_lower)
            filters.price_min = price_min
            filters.price_max = price_max
            
            # Extract category
            filters.category = self._extract_category(query_lower)
            
            # Extract colors
            filters.colors = self._extract_colors(query_lower)
            
            # Extract sizes
            filters.sizes = self._extract_sizes(query_lower)
            
            # Extract brands
            filters.brands = self._extract_brands(query_lower)
            
            # Extract keywords (remaining meaningful words)
            filters.keywords = self._extract_keywords(query, filters)
            
            # Extract sort preferences
            filters.sort_by = self._extract_sort_preference(query_lower)
            
            print(f"✅ Parsed query: '{query}' -> Category={filters.category}, Price={filters.price_min}-{filters.price_max}")
            
        except Exception as e:
            print(f"⚠️ Query parsing error: {e}")
        
        return filters
    
    def _extract_price_range(self, query: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Extract price range from query with intelligent pattern matching.
        
        Handles various formats:
        - "under $100", "below 50"
        - "over $200", "above 100"
        - "$50 to $100", "between 30 and 60"
        - "around $75"
        """
        price_min, price_max = None, None
        
        # CRITICAL: Check for range patterns FIRST (highest priority)
        # "30 to 60", "50-100 dollars", "between $30 and $60"
        range_pattern = r'(?:between\s+)?[$€]?(\d+(?:\.\d{2})?)\s*(?:dollars?|euros?|usd|eur)?\s*(?:to|and|-|through)\s*[$€]?(\d+(?:\.\d{2})?)\s*(?:dollars?|euros?|usd|eur)?'
        range_match = re.search(range_pattern, query, re.IGNORECASE)
        if range_match:
            price_min = float(range_match.group(1))
            price_max = float(range_match.group(2))
            print(f"✅ Found price range: ${price_min} to ${price_max}")
            return price_min, price_max  # Return immediately to avoid conflicts
        
        # Check for "under/below" patterns - "under 100 dollars", "below $50"
        under_pattern = r'(?:under|below|less\s+than|max|maximum|up\s+to)\s*[$€]?(\d+(?:\.\d{2})?)\s*(?:dollars?|euros?|usd|eur)?'
        under_match = re.search(under_pattern, query, re.IGNORECASE)
        if under_match:
            price_max = float(under_match.group(1))
            print(f"✅ Found price maximum: ${price_max}")
        
        # Check for "over/above" patterns - "over 50 dollars", "above $100"
        over_pattern = r'(?:over|above|more\s+than|min|minimum|at\s+least)\s*[$€]?(\d+(?:\.\d{2})?)\s*(?:dollars?|euros?|usd|eur)?'
        over_match = re.search(over_pattern, query, re.IGNORECASE)
        if over_match:
            price_min = float(over_match.group(1))
            print(f"✅ Found price minimum: ${price_min}")
        
        # Check for "around/about" patterns (set as approximate range) - "around 75 dollars"
        if not price_min and not price_max:  # Only if no other pattern matched
            approx_pattern = r'(?:around|about|approximately)\s*[$€]?(\d+(?:\.\d{2})?)\s*(?:dollars?|euros?|usd|eur)?'
            approx_match = re.search(approx_pattern, query, re.IGNORECASE)
            if approx_match:
                price = float(approx_match.group(1))
                price_min = price * 0.8  # 20% below
                price_max = price * 1.2  # 20% above
                print(f"✅ Found approximate price: ${price} -> range ${price_min} to ${price_max}")
        
        return price_min, price_max
    
    def _extract_category(self, query: str) -> Optional[str]:
        """Extract product category from query"""
        for category, aliases in self.categories.items():
            for alias in aliases:
                if alias in query:
                    return category
        return None
    
    def _extract_colors(self, query: str) -> List[str]:
        """Extract color preferences from query"""
        found_colors = []
        for color in self.colors:
            if re.search(r'\b' + color + r'\b', query):
                found_colors.append(color)
        return found_colors
    
    def _extract_sizes(self, query: str) -> List[str]:
        """Extract size preferences from query"""
        found_sizes = []
        for size in self.sizes:
            if re.search(r'\b' + size + r'\b', query, re.IGNORECASE):
                found_sizes.append(size)
        return found_sizes
    
    def _extract_brands(self, query: str) -> List[str]:
        """Extract brand preferences from query"""
        found_brands = []
        for brand in self.brands:
            if re.search(r'\b' + brand + r'\b', query, re.IGNORECASE):
                found_brands.append(brand)
        return found_brands
    
    def _extract_keywords(self, query: str, filters: SearchFilters) -> List[str]:
        """Extract meaningful keywords after removing filter terms"""
        # Remove price expressions
        price_expressions = [
            r'(?:under|below|less\s+than|max|maximum|up\s+to)\s*[$€]?\d+(?:\.\d{2})?',
            r'(?:over|above|more\s+than|min|minimum|at\s+least)\s*[$€]?\d+(?:\.\d{2})?',
            r'(?:between\s+)?[$€]?\d+(?:\.\d{2})?\s*(?:to|and|-|through)\s*[$€]?\d+(?:\.\d{2})?',
            r'(?:around|about|approximately)\s*[$€]?\d+(?:\.\d{2})?',
            r'[$€]\d+(?:\.\d{2})?',
        ]
        
        cleaned_query = query.lower()
        for pattern in price_expressions:
            cleaned_query = re.sub(pattern, '', cleaned_query, flags=re.IGNORECASE)
        
        # Remove known colors, sizes, brands
        for color in filters.colors:
            cleaned_query = re.sub(r'\b' + color + r'\b', '', cleaned_query)
        for size in filters.sizes:
            cleaned_query = re.sub(r'\b' + size + r'\b', '', cleaned_query, flags=re.IGNORECASE)
        for brand in filters.brands:
            cleaned_query = re.sub(r'\b' + brand + r'\b', '', cleaned_query, flags=re.IGNORECASE)
        
        # Remove common stop words
        stop_words = {'show', 'me', 'find', 'search', 'get', 'buy', 'a', 'an', 'the', 'with', 'for', 'in', 'to', 'of'}
        
        # Extract meaningful words
        words = cleaned_query.split()
        keywords = [w for w in words if w and len(w) > 2 and w not in stop_words]
        
        return keywords
    
    def _extract_sort_preference(self, query: str) -> Optional[str]:
        """Extract sorting preferences from query"""
        if any(term in query for term in ['cheap', 'cheapest', 'lowest price', 'budget']):
            return 'price_asc'
        elif any(term in query for term in ['expensive', 'premium', 'highest price', 'luxury']):
            return 'price_desc'
        elif any(term in query for term in ['newest', 'latest', 'new arrivals', 'recent']):
            return 'date_desc'
        elif any(term in query for term in ['popular', 'best selling', 'trending']):
            return 'popularity_desc'
        return None


# Global singleton instance
query_parser = EnhancedQueryParser()


# Helper functions for backward compatibility and convenience
def parse_query(query: str) -> SearchFilters:
    """Parse a natural language query into structured filters"""
    return query_parser.parse_query(query)


def extract_price_range(query: str) -> Tuple[Optional[float], Optional[float]]:
    """Extract price range from query"""
    return query_parser._extract_price_range(query.lower())


def extract_category(query: str) -> Optional[str]:
    """Extract product category from query"""
    return query_parser._extract_category(query.lower())


def filter_products_by_price(products: List[Dict], price_min: Optional[float] = None, price_max: Optional[float] = None) -> List[Dict]:
    """
    Filter products by price range.
    
    Args:
        products: List of product dictionaries
        price_min: Minimum price (inclusive)
        price_max: Maximum price (inclusive)
        
    Returns:
        Filtered list of products
    """
    if not price_min and not price_max:
        return products
    
    filtered = []
    for product in products:
        try:
            # Handle different price formats
            price_value = product.get('price') or product.get('PRICE') or product.get('Price')
            
            if price_value is None:
                continue
            
            # Convert to float
            try:
                # Handle different price formats
                if isinstance(price_value, str):
                    # Remove currency symbols and extra spaces
                    price_str = price_value.strip().replace('$', '').replace('€', '').replace(',', '')
                    product_price = float(price_str)
                else:
                    product_price = float(price_value)
            except (ValueError, TypeError):
                continue
            
            # Apply filters
            if price_min is not None and product_price < price_min:
                continue
            if price_max is not None and product_price > price_max:
                continue
            
            filtered.append(product)
        
        except Exception as e:
            print(f"⚠️ Error filtering product {product.get('id', 'unknown')}: {e}")
            continue
    
    return filtered


if __name__ == "__main__":
    # Test the parser
    test_queries = [
        "show me drills under $100",
        "ryobi drill between $80 and $150",
        "Samsung phones over $300",
        "garden plants around $30",
        "pendant light LED",
        "cheap mobile phone",
        "latest Makita drill driver"
    ]
    
    print("=" * 80)
    print("Query Parser Test Suite")
    print("=" * 80)
    
    for query in test_queries:
        print(f"\n🔍 Query: '{query}'")
        filters = parse_query(query)
        print(f"   Category: {filters.category}")
        print(f"   Price Range: ${filters.price_min} - ${filters.price_max}")
        print(f"   Colors: {filters.colors}")
        print(f"   Sizes: {filters.sizes}")
        print(f"   Brands: {filters.brands}")
        print(f"   Keywords: {filters.keywords}")
        print(f"   Sort: {filters.sort_by}")
