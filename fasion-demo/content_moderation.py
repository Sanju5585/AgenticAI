"""
Content Moderation Module
Filters and blocks inappropriate content including:
- Celebrity/public figure requests
- Hate speech
- Offensive content
- Inappropriate requests
"""

import re
from typing import Tuple, Optional

class ContentModerator:
    """Moderates user queries for inappropriate content"""
    
    def __init__(self):
        # Celebrity and public figure names (Indian and International)
        self.celebrities = [
            # Cricket players
            'virat kohli', 'virat', 'kohli', 'ms dhoni', 'dhoni', 'rohit sharma', 'rohit',
            'sachin tendulkar', 'sachin', 'kapil dev', 'hardik pandya', 'jasprit bumrah',
            'kl rahul', 'rishabh pant', 'shikhar dhawan', 'ravindra jadeja', 'ravichandran ashwin',
            
            # Bollywood actors
            'shah rukh khan', 'shahrukh', 'srk', 'salman khan', 'salman', 'aamir khan', 'aamir',
            'amitabh bachchan', 'amitabh', 'akshay kumar', 'akshay', 'hrithik roshan', 'hrithik',
            'ranveer singh', 'ranveer', 'ranbir kapoor', 'ranbir', 'varun dhawan', 'tiger shroff',
            'deepika padukone', 'deepika', 'priyanka chopra', 'priyanka', 'katrina kaif', 'katrina',
            'alia bhatt', 'alia', 'kareena kapoor', 'kareena', 'anushka sharma', 'anushka',
            'kangana ranaut', 'kangana', 'madhuri dixit', 'aishwarya rai', 'aishwarya',
            
            # Hollywood actors
            'tom cruise', 'brad pitt', 'leonardo dicaprio', 'will smith', 'robert downey',
            'chris hemsworth', 'chris evans', 'scarlett johansson', 'jennifer lawrence',
            'angelina jolie', 'johnny depp', 'dwayne johnson', 'the rock',
            
            # Politicians
            'narendra modi', 'modi', 'rahul gandhi', 'arvind kejriwal', 'amit shah',
            'donald trump', 'trump', 'joe biden', 'biden', 'barack obama', 'obama',
            
            # Sports stars
            'cristiano ronaldo', 'ronaldo', 'lionel messi', 'messi', 'neymar',
            'lebron james', 'michael jordan', 'tiger woods', 'roger federer', 'rafael nadal',
            'serena williams', 'usain bolt', 'muhammad ali',
            
            # Singers/Musicians
            'taylor swift', 'beyonce', 'justin bieber', 'ed sheeran', 'ariana grande',
            'arijit singh', 'sonu nigam', 'shreya ghoshal', 'lata mangeshkar',
            
            # Business leaders
            'elon musk', 'musk', 'bill gates', 'jeff bezos', 'mark zuckerberg',
            'mukesh ambani', 'ambani', 'ratan tata', 'tata', 'gautam adani', 'adani'
        ]
        
        # Hate speech and offensive keywords
        self.hate_keywords = [
            # Religious hate
            'hindu hate', 'muslim hate', 'christian hate', 'sikh hate', 'buddhist hate',
            'anti-hindu', 'anti-muslim', 'anti-christian', 'anti-sikh',
            
            # Racial slurs (mild detection - add more as needed)
            'racist', 'racism', 'racial slur', 'hate speech',
            
            # Violence
            'kill', 'murder', 'bomb', 'terrorist', 'terrorism', 'jihad', 'extremist',
            'violence', 'assault', 'attack',
            
            # Offensive
            'f**k', 'f*ck', 'sh*t', 'damn', 'hell', 'bastard', 'ass',
            'stupid', 'idiot', 'moron', 'dumb',
            
            # Sexual/Adult
            'porn', 'sex', 'nude', 'naked', 'xxx', 'adult content', 'nsfw',
            
            # Discriminatory
            'discrimination', 'discriminate', 'bigot', 'bigotry', 'prejudice',
            'sexist', 'sexism', 'homophobic', 'transphobic'
        ]
        
        # Political and controversial keywords (ENHANCED)
        self.political_keywords = [
            # General political terms
            'political', 'politics', 'politician', 'election', 'vote', 'voting', 'ballot',
            'campaign', 'rally', 'protest', 'demonstration',
            
            # Indian political parties
            'bjp', 'bharatiya janata party', 'congress', 'inc', 'indian national congress',
            'aap', 'aam aadmi party', 'tmc', 'trinamool congress', 'shiv sena',
            'ncp', 'nationalist congress', 'dmk', 'aiadmk', 'bsp', 'samajwadi party',
            'communist party', 'cpi', 'cpim', 'left front', 'jdu', 'rjd', 'bjd',
            'trs', 'tdp', 'ysrcp', 'akali dal', 'nc', 'pdp',
            
            # International parties
            'democrat', 'democratic party', 'republican', 'republican party',
            'labour party', 'conservative party', 'tory', 'liberal party',
            'green party', 'socialist party', 'communist party',
            
            # Political ideologies
            'left wing', 'right wing', 'leftist', 'rightist', 'liberal', 'conservative',
            'progressive', 'libertarian', 'socialist', 'communist', 'fascist', 'nationalist',
            'centrist', 'moderate', 'radical', 'extremist',
            
            # Government and policy
            'government', 'parliament', 'ministry', 'minister', 'prime minister',
            'president', 'senate', 'congress', 'legislation', 'law', 'policy',
            'ruling party', 'opposition', 'coalition', 'alliance',
            
            # Slogans and symbols
            'lotus symbol', 'hand symbol', 'broom symbol', 'cycle symbol',
            'elephant symbol', 'rising sun', 'hammer and sickle',
            
            # Political movements
            'independence movement', 'civil rights', 'freedom struggle',
            'revolution', 'uprising', 'coup', 'regime change'
        ]
        
        # Compile regex patterns for better matching
        self.celebrity_pattern = self._compile_pattern(self.celebrities)
        self.hate_pattern = self._compile_pattern(self.hate_keywords)
        self.political_pattern = self._compile_pattern(self.political_keywords)
    
    def _compile_pattern(self, keywords: list) -> re.Pattern:
        """Compile a regex pattern from keyword list"""
        # Sort by length (longest first) to match longer phrases first
        sorted_keywords = sorted(keywords, key=len, reverse=True)
        # Escape special regex characters and join with OR
        pattern = '|'.join(re.escape(keyword) for keyword in sorted_keywords)
        return re.compile(r'\b(' + pattern + r')\b', re.IGNORECASE)
    
    def check_content(self, query: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check if content is appropriate
        
        Args:
            query: User's input query
            
        Returns:
            Tuple of (is_blocked, reason, message)
            - is_blocked: True if content should be blocked
            - reason: Category of block (celebrity, hate, political)
            - message: User-friendly message to display
        """
        query_lower = query.lower().strip()
        
        # Check for celebrity/public figure content
        if self.celebrity_pattern.search(query_lower):
            matched_celebrity = self.celebrity_pattern.search(query_lower).group(0)
            return (
                True,
                'celebrity',
                f"⚠️ Sorry, we cannot support requests related to celebrities or public figures. "
                f"Our products do not feature celebrity images, names, or likenesses due to copyright "
                f"and licensing restrictions. Please browse our available designs instead! 🎨"
            )
        
        # Check for hate speech or offensive content
        if self.hate_pattern.search(query_lower):
            return (
                True,
                'inappropriate',
                "⚠️ We detected inappropriate content in your request. Our platform maintains a "
                "respectful and inclusive environment. Please rephrase your query without offensive "
                "language or hate speech. Thank you for understanding! 🙏"
            )
        
        # Check for political content
        if self.political_pattern.search(query_lower):
            return (
                True,
                'political',
                "⚠️ We avoid political content and affiliations. Our products are focused on "
                "fashion, style, and general designs. Please explore our non-political collections! 🛍️"
            )
        
        # Content is appropriate
        return (False, None, None)
    
    def sanitize_query(self, query: str) -> str:
        """
        Remove potentially problematic content from query
        (Use this if you want to clean rather than block)
        """
        sanitized = query
        
        # Remove celebrity names
        sanitized = self.celebrity_pattern.sub('[celebrity]', sanitized)
        
        # Remove hate keywords
        sanitized = self.hate_pattern.sub('[filtered]', sanitized)
        
        return sanitized.strip()


# Global instance
content_moderator = ContentModerator()


def check_content(query: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Convenience function to check content
    
    Returns:
        Tuple of (is_blocked, reason, message)
    """
    return content_moderator.check_content(query)


# Test the module
if __name__ == "__main__":
    test_queries = [
        # Celebrity tests
        "Show me t-shirts with Virat Kohli face",
        "I want a shirt with Shah Rukh Khan",
        "T-shirt with Elon Musk photo",
        "Sachin Tendulkar jersey",
        "Show me Salman Khan design",
        
        # Political tests
        "Do you have any political party merchandise?",
        "Show me BJP t-shirts",
        "I want Congress party flag shirt",
        "AAP broom symbol merchandise",
        "Republican party shirt",
        "Democratic party designs",
        "Show me leftist t-shirts",
        "Conservative party merchandise",
        "Modi government policy shirt",
        
        # Hate/Inappropriate tests
        "I hate this stupid design",
        "Show me racist designs",
        "Anti-muslim shirts",
        
        # Clean queries (should pass)
        "Show me blue t-shirts",
        "Show me casual wear",
        "I want a red hoodie",
        "Do you have cotton shirts?",
        "Show me accessories",
    ]
    
    print("=" * 70)
    print("CONTENT MODERATION TEST - ENHANCED")
    print("=" * 70)
    
    blocked_count = 0
    passed_count = 0
    
    for query in test_queries:
        is_blocked, reason, message = check_content(query)
        print(f"\nQuery: {query}")
        print(f"Blocked: {'❌ YES' if is_blocked else '✅ NO'}")
        if is_blocked:
            blocked_count += 1
            print(f"Reason: {reason.upper()}")
            print(f"Message: {message[:80]}...")
        else:
            passed_count += 1
        print("-" * 70)
    
    print(f"\n{'=' * 70}")
    print(f"SUMMARY: {blocked_count} blocked, {passed_count} passed")
    print(f"{'=' * 70}")
