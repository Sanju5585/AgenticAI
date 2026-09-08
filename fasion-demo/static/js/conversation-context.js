/**
 * Conversation Context Manager
 * Handles conversation memory in browser session storage for AI context awareness
 */

class ConversationContext {
  constructor() {
    this.storageKey = 'ai_conversation_context';
    this.maxHistoryLength = 10; // Keep last 10 conversation pairs
    this.currentSession = this.getSessionId();
    this.loadContext();
  }

  getSessionId() {
    // Generate session ID based on browser session and timestamp
    let sessionId = sessionStorage.getItem('conversation_session_id');
    if (!sessionId) {
      sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
      sessionStorage.setItem('conversation_session_id', sessionId);
    }
    return sessionId;
  }

  loadContext() {
    try {
      const stored = sessionStorage.getItem(this.storageKey);
      this.conversationHistory = stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.error('Error loading conversation context:', error);
      this.conversationHistory = [];
    }
  }

  saveContext() {
    try {
      // Keep only recent conversations to prevent storage overflow
      if (this.conversationHistory.length > this.maxHistoryLength) {
        this.conversationHistory = this.conversationHistory.slice(-this.maxHistoryLength);
      }
      sessionStorage.setItem(this.storageKey, JSON.stringify(this.conversationHistory));
    } catch (error) {
      console.error('Error saving conversation context:', error);
    }
  }

  addConversation(userMessage, aiResponse, metadata = {}) {
    const conversation = {
      id: Date.now(),
      timestamp: new Date().toISOString(),
      user: userMessage,
      ai: aiResponse,
      metadata: {
        session_id: this.currentSession,
        products: this.extractProducts(aiResponse),
        response_type: metadata.response_type || 'text',
        ...metadata
      }
    };

    this.conversationHistory.push(conversation);
    this.saveContext();
    
    console.log('🧠 Conversation saved to context:', {
      message: userMessage.substring(0, 50) + '...',
      products: conversation.metadata.products?.length || 0,
      type: conversation.metadata.response_type
    });
  }

  /**
   * Store displayed products in the conversation context
   * This is called when products are actually shown to the user
   * @param {Object} productContext - Object containing displayed products and metadata
   */
  storeDisplayedProducts(productContext) {
    try {
      const conversationHistory = this.getConversation();
      
      // Update the most recent conversation pair with the displayed products
      if (conversationHistory && conversationHistory.length > 0) {
        const lastEntry = conversationHistory[conversationHistory.length - 1];
        if (lastEntry.metadata) {
          // Add product context to the response
          lastEntry.metadata.displayed_products = productContext.products;
          lastEntry.metadata.search_type = productContext.search_type;
          lastEntry.metadata.display_timestamp = productContext.timestamp;
          
          // Save updated conversation
          this.saveContext();
          
          console.log('🧠 Enhanced conversation context with displayed products:', lastEntry);
        }
      }
      
      // Also store in a dedicated recent products cache for quick access
      const recentProducts = {
        products: productContext.products,
        timestamp: productContext.timestamp,
        search_type: productContext.search_type
      };
      
      sessionStorage.setItem('recent_displayed_products', JSON.stringify(recentProducts));
      console.log('🧠 Stored recent displayed products cache:', recentProducts);
      
    } catch (error) {
      console.error('Error storing displayed products:', error);
    }
  }

  /**
   * Get recently displayed products for context
   * @returns {Array} Array of recently displayed products
   */
  getRecentDisplayedProducts() {
    try {
      const recent = sessionStorage.getItem('recent_displayed_products');
      if (recent) {
        const data = JSON.parse(recent);
        // Check if data is recent (within last 10 minutes)
        const now = new Date();
        const timestamp = new Date(data.timestamp);
        const timeDiff = (now - timestamp) / (1000 * 60); // minutes
        
        if (timeDiff <= 10) {
          return data.products || [];
        }
      }
      return [];
    } catch (error) {
      console.error('Error getting recent displayed products:', error);
      return [];
    }
  }

  getConversation() {
    return this.conversationHistory;
  }

  extractProducts(aiResponse) {
    // Extract product information from AI response
    const products = [];
    
    try {
      // If response is an object with products_data
      if (typeof aiResponse === 'object' && aiResponse.products_data) {
        return aiResponse.products_data.map(product => ({
          product_id: product.product_id || product.PRODUCT_ID,
          product_name: product.product_name || product.PRODUCT_NAME,
          price: product.price || product.PRICE,
          image_url: product.image_url || product.IMAGE_URL,
          summary: product.summary || product.SUMMARY
        }));
      }

      // If response has product_data (single product)
      if (typeof aiResponse === 'object' && aiResponse.product_data) {
        return [{
          product_id: aiResponse.product_data.product_id || aiResponse.product_data.PRODUCT_ID,
          product_name: aiResponse.product_data.product_name || aiResponse.product_data.PRODUCT_NAME,
          price: aiResponse.product_data.price || aiResponse.product_data.PRICE,
          image_url: aiResponse.product_data.image_url || aiResponse.product_data.IMAGE_URL,
          summary: aiResponse.product_data.summary || aiResponse.product_data.SUMMARY
        }];
      }

      // Enhanced extraction from HTML/text content
      if (typeof aiResponse === 'string') {
        // Look for product card patterns in HTML
        const productCardMatches = aiResponse.match(/<div[^>]*class="[^"]*product-card[^"]*"[^>]*>[\s\S]*?<\/div>/gi);
        
        if (productCardMatches) {
          productCardMatches.forEach(cardHtml => {
            // Extract product ID from onclick attributes
            const productIdMatch = cardHtml.match(/openProductDetail\(['"]([^'"]+)['"]\)/);
            // Extract product name from alt attributes or title
            const productNameMatch = cardHtml.match(/alt=["']([^"']+)["']/) || 
                                   cardHtml.match(/<h[1-6][^>]*>([^<]+)<\/h[1-6]>/);
            // Extract price
            const priceMatch = cardHtml.match(/£(\d+\.?\d*)/);
            
            if (productIdMatch || productNameMatch) {
              products.push({
                product_id: productIdMatch ? productIdMatch[1] : '',
                product_name: productNameMatch ? productNameMatch[1].trim() : '',
                price: priceMatch ? parseFloat(priceMatch[1]) : 0,
                source: 'html_extracted'
              });
            }
          });
        }

        // Fallback: Look for structured data patterns
        if (products.length === 0) {
          const productIdMatches = aiResponse.match(/product[_\s]*id[:\s]*["\']?(\w+)["\']?/gi);
          const productNameMatches = aiResponse.match(/product[_\s]*name[:\s]*["\']([^"']+)["\']?/gi);
          
          if (productIdMatches && productNameMatches) {
            for (let i = 0; i < Math.min(productIdMatches.length, productNameMatches.length); i++) {
              products.push({
                product_id: productIdMatches[i].match(/(\w+)$/)[1],
                product_name: productNameMatches[i].match(/["\']([^"']+)["\']?/)[1],
                source: 'pattern_extracted'
              });
            }
          }
        }
      }
    } catch (error) {
      console.error('Error extracting products from response:', error);
    }

    console.log('🔍 Extracted products:', products);
    return products;
  }

  getLastProducts(limit = 5) {
    // Get products from recent conversations
    const recentProducts = [];
    
    // First check the recent displayed products cache
    const cachedProducts = this.getRecentDisplayedProducts();
    if (cachedProducts.length > 0) {
      recentProducts.push(...cachedProducts.slice(0, limit));
    }
    
    // If we don't have enough, look through conversations in reverse order
    if (recentProducts.length < limit) {
      for (let i = this.conversationHistory.length - 1; i >= 0 && recentProducts.length < limit; i--) {
        const conv = this.conversationHistory[i];
        
        // Check displayed_products first (more reliable)
        if (conv.metadata.displayed_products && conv.metadata.displayed_products.length > 0) {
          for (const product of conv.metadata.displayed_products) {
            if (!recentProducts.find(p => p.product_id === product.product_id)) {
              recentProducts.push(product);
              if (recentProducts.length >= limit) break;
            }
          }
        }
        // Fallback to extracted products
        else if (conv.metadata.products && conv.metadata.products.length > 0) {
          for (const product of conv.metadata.products) {
            if (!recentProducts.find(p => p.product_id === product.product_id)) {
              recentProducts.push(product);
              if (recentProducts.length >= limit) break;
            }
          }
        }
      }
    }
    
    return recentProducts;
  }

  getLastConversation() {
    return this.conversationHistory.length > 0 
      ? this.conversationHistory[this.conversationHistory.length - 1] 
      : null;
  }

  getConversationContext(lastN = 3) {
    // Get last N conversations for context
    return this.conversationHistory.slice(-lastN).map(conv => ({
      user: conv.user,
      ai: typeof conv.ai === 'string' ? conv.ai.substring(0, 200) + '...' : 'Product response',
      products: conv.metadata.displayed_products || conv.metadata.products || [],
      type: conv.metadata.response_type || 'text'
    }));
  }

  isContextAwareQuery(userMessage) {
    // Detect if user is asking about products from previous conversation
    const contextKeywords = [
      'these products', 'those products', 'them', 'these items', 'those items',
      'this product', 'that product', 'this item', 'that item',
      'accessories', 'accessories for', 'show accessories', 'accessories of',
      'similar', 'like these', 'like those', 'related to', 'for these',
      'more like this', 'more like these', 'other colors', 'different sizes',
      'above', 'above products', 'above items', 'previous', 'last search',
      'theses', 'theese', 'these' // Common typos
    ];

    const message = userMessage.toLowerCase();
    const hasContextKeyword = contextKeywords.some(keyword => message.includes(keyword));
    
    // Also check for accessory-specific patterns
    const accessoryPatterns = [
      /accessories?.*(?:of|for|to|with).*/,
      /show.*accessories?/,
      /what.*goes?.*with/,
      /complement/,
      /match/
    ];
    
    const hasAccessoryPattern = accessoryPatterns.some(pattern => pattern.test(message));
    
    console.log('🤔 Context query detection:', {
      message: message,
      hasContextKeyword: hasContextKeyword,
      hasAccessoryPattern: hasAccessoryPattern,
      hasRecentProducts: this.getLastProducts().length > 0
    });
    
    return (hasContextKeyword || hasAccessoryPattern) && this.getLastProducts().length > 0;
  }

  enhanceQueryWithContext(userMessage) {
    // Enhance user query with context from previous conversation
    if (!this.isContextAwareQuery(userMessage)) {
      return userMessage; // No context needed
    }

    const lastProducts = this.getLastProducts(10); // Get more products for better context
    if (lastProducts.length === 0) {
      return userMessage; // No context available
    }

    const lastConversation = this.getLastConversation();
    
    // Build context-enhanced query
    let enhancedQuery = userMessage;

    // Enhanced context building for accessories
    if (userMessage.toLowerCase().includes('accessories') || 
        userMessage.toLowerCase().includes('accessory') ||
        /what.*goes?.*with/.test(userMessage.toLowerCase())) {
      
      // Create detailed product context with IDs and names
      const productContext = lastProducts.map(p => {
        let contextStr = p.product_name;
        if (p.product_id) {
          contextStr += ` (ID: ${p.product_id})`;
        }
        return contextStr;
      }).join(', ');
      
      enhancedQuery = `${userMessage}. Context: User previously searched for these products: ${productContext}. Find accessories for these specific products.`;
    } else {
      // For other context-aware queries
      const productNames = lastProducts.map(p => p.product_name).filter(name => name).join(', ');
      const productIds = lastProducts.map(p => p.product_id).filter(id => id).join(', ');
      
      enhancedQuery = `${userMessage}. Context: User previously viewed these products: ${productNames}`;
      if (productIds) {
        enhancedQuery += ` (Product IDs: ${productIds})`;
      }
    }

    console.log('🔍 Enhanced query with context:', {
      original: userMessage,
      enhanced: enhancedQuery,
      productsUsed: lastProducts.length,
      productNames: lastProducts.map(p => p.product_name)
    });

    return enhancedQuery;
  }

  clearContext() {
    this.conversationHistory = [];
    sessionStorage.removeItem(this.storageKey);
    sessionStorage.removeItem('recent_displayed_products');
    console.log('🧹 Conversation context cleared');
  }

  // Debug methods
  debugContext() {
    console.log('🧠 Current Conversation Context:', {
      session: this.currentSession,
      conversations: this.conversationHistory.length,
      lastProducts: this.getLastProducts(),
      recentDisplayed: this.getRecentDisplayedProducts(),
      context: this.getConversationContext()
    });
  }

  exportContext() {
    return {
      session_id: this.currentSession,
      conversation_history: this.conversationHistory,
      last_products: this.getLastProducts(),
      recent_displayed: this.getRecentDisplayedProducts(),
      context: this.getConversationContext()
    };
  }
}

// Global conversation context instance
window.conversationContext = new ConversationContext();

// Auto-clear context when page is refreshed (optional)
window.addEventListener('beforeunload', function() {
  // Keep context in sessionStorage but could be cleared if needed
  console.log('🔄 Page unloading - conversation context preserved in session storage');
});

// Debug: Allow manual access to context in console
window.debugConversation = () => conversationContext.debugContext();
window.clearConversation = () => conversationContext.clearContext();