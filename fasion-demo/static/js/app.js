/**
 * AI Shopping Assistant - Main JavaScript File
 * Handles chat functionality, product display, cart management, and UI interactions
 */

// Global variables
let cartCount = 0;
let cartItems = [];
let cartTotal = 0;
let currentUser = null;
let isLoggedIn = false;
let isVisualSearchInProgress = false;
let lastVisualSearchPreview = null;

function escapeHtml(value) {
  if (value === undefined || value === null) {
    return '';
  }
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Initialize AOS (Animate On Scroll) library
document.addEventListener('DOMContentLoaded', function() {
  if (typeof AOS !== 'undefined') {
    AOS.init({
      duration: 800,
      easing: 'ease-out-cubic',
      once: true,
      offset: 100
    });
  }
  
  // Check for PayPal return parameters
  handlePayPalReturn();
  
  console.log("Loading best selling products...");
  loadBestSellingProducts();
  
  // Clear cart on page load/refresh - cart should be empty on page refresh
  clearCartOnPageLoad();
  
  // Check if user was previously logged in (restore from localStorage)
  checkPreviousLogin();
  
  // 🧠 Initialize smart conversation features
  if (window.conversationContext) {
    console.log("🧠 Conversation context system initialized");
    addSmartFeatureIndicators();
    updateSmartPlaceholder();
    
    // Add welcome message about smart features
    setTimeout(() => {
      showNotification("💡 Smart AI features active! I can remember our conversation and provide context-aware responses.", "info");
    }, 3000);
  }
  
  // Add welcome animation
  setTimeout(() => {
    const queryInput = document.getElementById("query");
    queryInput.placeholder = "Try: 'Show me jackets' then ask 'show accessories'";
  }, 2000);
  
  // Initialize tooltips and other interactive elements
  initializeInteractiveElements();

  // Visual search is now initialized by voice-search.js
  
  // Close mini cart when clicking outside
  document.addEventListener('click', function(event) {
    const miniCartBtn = document.getElementById('mini-cart-btn');
    const miniCartDropdown = document.getElementById('mini-cart-dropdown');
    
    if (!miniCartBtn.contains(event.target) && !miniCartDropdown.contains(event.target)) {
      closeMiniCart();
    }
    
    // 🤖 AI SUGGESTIONS: Handle suggestion card clicks via event delegation
    const suggestionCard = event.target.closest('.suggestion-card');
    if (suggestionCard) {
      const type = suggestionCard.getAttribute('data-suggestion-type');
      const text = suggestionCard.getAttribute('data-suggestion-text');
      const queryContext = suggestionCard.getAttribute('data-query-context') || '';
      console.log('🎯 Suggestion card clicked via delegation:', type, text, 'Context:', queryContext);
      if (type && text) {
        handleAISuggestionClick(type, text, queryContext);
      }
    }
  });
  
  // Clear cart on page unload/refresh
  window.addEventListener('beforeunload', function() {
    console.log('Page is being refreshed/closed - clearing cart');
    try {
      sessionStorage.removeItem('shoppingCart');
      sessionStorage.removeItem('tempCart');
    } catch (error) {
      console.error('Error clearing cart on page unload:', error);
    }
  });
  
  // Also clear cart if user navigates away and comes back
  window.addEventListener('pageshow', function(event) {
    if (event.persisted) {
      console.log('Page restored from cache - clearing cart');
      clearCartOnPageLoad();
    }
  });
});

/**
 * PayPal Integration - DEPRECATED (Now using file-based polling)
 * Kept for backward compatibility only
 */
function handlePayPalReturn() {
  const urlParams = new URLSearchParams(window.location.search);
  const paymentSuccess = urlParams.get('payment_success');
  const paymentCancelled = urlParams.get('payment_cancelled');
  const error = urlParams.get('error');
  const message = urlParams.get('message');
  const restoreSession = urlParams.get('restore_session');
  const restorationKey = urlParams.get('restoration_key');
  
  // This function is deprecated - new implementation uses file polling
  // Only handle errors for backward compatibility
  if (error) {
    console.log('PayPal return with error (legacy):', error);
    const decodedError = decodeURIComponent(error);
    showNotification(decodedError, 'error');
    
    // Try to restore session from localStorage anyway
    restoreSessionFromLocalStorage();
    
    // Add error message to chat
    setTimeout(() => {
      appendBotMessage({
        response: `❌ <strong>Payment Processing Error</strong><br><br>
          <div style="background: linear-gradient(135deg, #ef4444, #dc2626); color: white; padding: 20px; border-radius: 15px; margin: 10px 0;">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
              <i class="fas fa-exclamation-triangle" style="font-size: 24px; margin-right: 10px;"></i>
              <div>
                <div style="font-size: 18px; font-weight: bold;">Processing Failed</div>
                <div style="font-size: 14px; opacity: 0.9;">There was an issue with your payment processing</div>
              </div>
            </div>
            <div style="font-size: 14px; opacity: 0.9;">
              <strong>Error Details:</strong><br>
              ${decodedError}<br><br>
              Please try again or contact support if the issue persists. Your session has been restored.
            </div>
          </div>`
      });
    }, 1000);
    
    // Clear the URL parameters
    window.history.replaceState({}, document.title, window.location.pathname);
    
  } else if (paymentSuccess === 'true') {
    // Payment was successful
    console.log('PayPal payment successful, restoring session...');
    
    // Show loading message first
    showNotification("Payment successful! Restoring your session...", 'info');
    
    // Try to restore from server first, then fallback to localStorage
    if (restorationKey) {
      restoreSessionFromServer(restorationKey, message);
    } else if (restoreSession === 'true') {
      restoreSessionFromLocalStorage(message);
    }
    
    // Clear the URL parameters
    window.history.replaceState({}, document.title, window.location.pathname);
    
  } else if (paymentCancelled === 'true') {
    // Payment was cancelled
    console.log('PayPal payment cancelled, restoring session...');
    
    // Restore session from localStorage
    restoreSessionFromLocalStorage();
    
    // Show cancellation message
    if (message) {
      const decodedMessage = decodeURIComponent(message);
      showNotification(decodedMessage, 'info');
      
      // Add cancellation message to chat
      setTimeout(() => {
        appendBotMessage({
          response: `ℹ️ <strong>Payment Cancelled</strong><br><br>
            <div style="background: linear-gradient(135deg, #f59e0b, #d97706); color: white; padding: 20px; border-radius: 15px; margin: 10px 0;">
              <div style="display: flex; align-items: center; margin-bottom: 15px;">
                <i class="fas fa-info-circle" style="font-size: 24px; margin-right: 10px;"></i>
                <div>
                  <div style="font-size: 18px; font-weight: bold;">Welcome Back!</div>
                  <div style="font-size: 14px; opacity: 0.9;">No payment was processed</div>
                </div>
              </div>
              <div style="font-size: 14px; opacity: 0.9;">
                ${decodedMessage}<br>
                Your cart items are still available if you'd like to try again.
              </div>
            </div>`
        });
      }, 1000);
    }
    
    // Clear the URL parameters
    window.history.replaceState({}, document.title, window.location.pathname);
  }
}

async function restoreSessionFromServer(restorationKey, message) {
  try {
    console.log('Attempting to restore session from server with key:', restorationKey);
    
    const response = await fetch(`/api/restore-session?restoration_key=${encodeURIComponent(restorationKey)}`);
    const data = await response.json();
    
    if (data.success && data.restoration_data) {
      const sessionData = data.restoration_data;
      console.log('Server session data retrieved:', sessionData);
      
      // Restore user information
      if (sessionData.customer_id) {
        // Simulate login without password (since they're already authenticated)
        currentUser = {
          email: sessionData.customer_id,
          name: sessionData.customer_id.split('@')[0] || 'User'
        };
        isLoggedIn = true;
        updateUIAfterLogin();
        console.log('User session restored from server:', currentUser);
      }
      
      // Restore conversation context
      if (sessionData.conversation_context && window.conversationContext) {
        try {
          window.conversationContext.importContext(sessionData.conversation_context);
          console.log('Conversation context restored from server');
        } catch (e) {
          console.warn('Could not restore conversation context from server:', e);
        }
      }
      
      // Restore chat history
      if (sessionData.chat_history && sessionData.chat_history.length > 0) {
        restoreChatHistory(sessionData.chat_history);
        console.log('Chat history restored from server:', sessionData.chat_history.length, 'messages');
      }
      
      // Show success message with order details
      if (message) {
        const decodedMessage = decodeURIComponent(message);
        showNotification(decodedMessage, 'success');
        
        // Add enhanced success message to chat
        setTimeout(() => {
          const orderDetails = sessionData.order_details || {};
          appendBotMessage({
            response: `🎉 <strong>Payment Successful!</strong><br><br>
              <div style="background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 20px; border-radius: 15px; margin: 10px 0;">
                <div style="display: flex; align-items: center; margin-bottom: 15px;">
                  <i class="fas fa-check-circle" style="font-size: 24px; margin-right: 10px;"></i>
                  <div>
                    <div style="font-size: 18px; font-weight: bold;">Welcome Back!</div>
                    <div style="font-size: 14px; opacity: 0.9;">Your payment was processed successfully</div>
                  </div>
                </div>
                <div style="font-size: 14px; opacity: 0.9;">
                  ${decodedMessage}<br>
                  ${orderDetails.order_id ? `Order ID: #${orderDetails.order_id}<br>` : ''}
                  ${sessionData.payment_id ? `Payment ID: ${sessionData.payment_id}<br>` : ''}
                  Your session has been fully restored and you can continue shopping!
                </div>
              </div>`
          });
        }, 1000);
      }
      
      return true;
    } else {
      throw new Error('No restoration data available on server');
    }
    
  } catch (error) {
    console.error('Failed to restore from server:', error);
    // Fallback to localStorage restoration
    showNotification("Restoring from local backup...", 'info');
    restoreSessionFromLocalStorage(message);
    return false;
  }
}

function restoreSessionFromLocalStorage(message = null) {
  try {
    // Try to restore from localStorage backup
    const sessionBackup = localStorage.getItem('paypal_session_backup');
    if (sessionBackup) {
      const sessionData = JSON.parse(sessionBackup);
      
      console.log('Restoring session from localStorage backup:', sessionData);
      
      // Restore user information
      if (sessionData.userInfo) {
        currentUser = sessionData.userInfo;
        isLoggedIn = true;
        updateUIAfterLogin();
        console.log('User session restored from localStorage:', currentUser);
      }
      
      // Restore cart items
      if (sessionData.cartItems && sessionData.cartItems.length > 0) {
        cartItems = sessionData.cartItems;
        updateCartDisplay();
        console.log('Cart restored from localStorage:', cartItems.length, 'items');
      }
      
      // Restore conversation context
      if (sessionData.conversationContext && window.conversationContext) {
        try {
          window.conversationContext.importContext(sessionData.conversationContext);
          console.log('Conversation context restored from localStorage');
        } catch (e) {
          console.warn('Could not restore conversation context from localStorage:', e);
        }
      }
      
      // Restore chat history
      if (sessionData.chatHistory && sessionData.chatHistory.length > 0) {
        restoreChatHistory(sessionData.chatHistory);
        console.log('Chat history restored from localStorage:', sessionData.chatHistory.length, 'messages');
      }
      
      // Clean up the backup
      localStorage.removeItem('paypal_session_backup');
      
      // Show appropriate message
      if (message) {
        const decodedMessage = decodeURIComponent(message);
        showNotification(decodedMessage, 'success');
        
        setTimeout(() => {
          appendBotMessage({
            response: `🎉 <strong>Congratulation Order placed Sucessfully </strong><br><br>
              <div style="background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 20px; border-radius: 15px; margin: 10px 0;">
                <div style="display: flex; align-items: center; margin-bottom: 15px;">
                  <i class="fas fa-check-circle" style="font-size: 24px; margin-right: 10px;"></i>
                  <div>
                    <div style="font-size: 18px; font-weight: bold;">Welcome Back!</div>
                    <div style="font-size: 14px; opacity: 0.9;">Your session has been restored</div>
                  </div>
                </div>
                <div style="font-size: 14px; opacity: 0.9;">
                  ${decodedMessage}<br>
                  Your conversation history and context have been restored. You can continue shopping!
                </div>
              </div>`
          });
        }, 1000);
      }
      
      return true;
    }
  } catch (error) {
    console.error('Error restoring session from localStorage:', error);
  }
  
  return false;
}

function getChatHistory() {
  const chatBox = document.getElementById("chat-box");
  const messages = [];
  
  if (chatBox) {
    const messageElements = chatBox.querySelectorAll('.chat-bubble-user, .chat-bubble-bot');
    messageElements.forEach((element, index) => {
      const isUser = element.classList.contains('chat-bubble-user');
      
      // Get text content, but preserve some HTML for bot messages
      let textContent;
      if (isUser) {
        textContent = element.textContent || element.innerText || '';
      } else {
        // For bot messages, preserve some HTML structure but clean it up
        textContent = element.innerHTML || element.textContent || element.innerText || '';
        // Remove script tags and clean up
        textContent = textContent.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');
        textContent = textContent.replace(/onclick="[^"]*"/gi, ''); // Remove onclick handlers
      }
      
      if (textContent.trim()) {
        messages.push({
          id: `msg_${index}`,
          sender: isUser ? 'user' : 'bot',
          message: textContent.trim(),
          timestamp: new Date().toISOString(),
          messageType: isUser ? 'text' : 'html' // Distinguish between text and HTML content
        });
      }
    });
  }
  
  console.log(`📝 Captured ${messages.length} chat messages for backup`);
  return messages;
}

function restoreChatHistory(chatHistory) {
  if (!chatHistory || chatHistory.length === 0) return;
  
  const chatBox = document.getElementById("chat-box");
  
  // Clear existing chat except welcome message
  const existingMessages = chatBox.querySelectorAll('.animate-slide-up');
  existingMessages.forEach(msg => msg.remove());
  
  console.log(`🔄 Restoring ${chatHistory.length} chat messages...`);
  
  // Restore messages with proper handling of HTML vs text content
  chatHistory.forEach((historyItem, index) => {
    if (historyItem.message && historyItem.message.trim()) {
      const messageDiv = document.createElement("div");
      
      if (historyItem.sender === "user") {
        messageDiv.className = "flex justify-end animate-slide-up";
        messageDiv.innerHTML = `
          <div class="chat-bubble-user p-4 max-w-2xl shadow-lg">
            <div class="flex items-start space-x-3">
              <div class="flex-1">
                <p class="text-white">${historyItem.message}</p>
              </div>
              <div class="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center flex-shrink-0">
                <i class="fas fa-user text-white text-sm"></i>
              </div>
            </div>
          </div>
        `;
      } else {
        messageDiv.className = "flex justify-start animate-slide-up";
        
        // Handle HTML content for bot messages
        const content = historyItem.messageType === 'html' ? historyItem.message : `<p class="text-gray-800">${historyItem.message}</p>`;
        
        messageDiv.innerHTML = `
          <div class="chat-bubble-bot p-4 max-w-4xl shadow-lg">
            <div class="flex items-start space-x-3">
              <div class="w-8 h-8 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full flex items-center justify-center flex-shrink-0">
                <i class="fas fa-robot text-white text-sm"></i>
              </div>
              <div class="flex-1">
                ${content}
              </div>
            </div>
          </div>
        `;
      }
      
      chatBox.appendChild(messageDiv);
    }
  });
  
  // Scroll to bottom
  chatBox.scrollTop = chatBox.scrollHeight;
  
  // Add restoration notice
  setTimeout(() => {
    const chatBox = document.getElementById("chat-box");
    const noticeDiv = document.createElement("div");
    noticeDiv.className = "flex justify-center my-2 animate-fade-in";
    noticeDiv.innerHTML = `
      <div class="bg-gradient-to-r from-green-100 to-emerald-100 border border-green-200 rounded-full px-4 py-2 flex items-center space-x-2 text-sm text-green-700 shadow-sm">
        <i class="fas fa-history text-green-500"></i>
        <span class="font-medium">Chat history successfully restored (${chatHistory.length} messages)</span>
        <i class="fas fa-check-circle text-green-500"></i>
      </div>
    `;
    
    chatBox.appendChild(noticeDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
    
    // Remove notice after a few seconds
    setTimeout(() => {
      noticeDiv.remove();
    }, 5000);
  }, 500);
}
function appendMessage(text, sender) {
  const chatBox = document.getElementById("chat-box");
  const messageDiv = document.createElement("div");
  
  if (sender === "user") {
    messageDiv.className = "flex justify-end animate-slide-up";
    messageDiv.innerHTML = `
      <div class="chat-bubble-user p-4 max-w-2xl shadow-lg">
        <div class="flex items-start space-x-3">
          <div class="flex-1">
            <p class="text-white">${text}</p>
          </div>
          <div class="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center flex-shrink-0">
            <i class="fas fa-user text-white text-sm"></i>
          </div>
        </div>
      </div>
    `;
  } else {
    messageDiv.className = "flex justify-start animate-slide-up";
    messageDiv.innerHTML = `
      <div class="chat-bubble-bot p-4 max-w-4xl shadow-lg">
        <div class="flex items-start space-x-3">
          <div class="w-8 h-8 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full flex items-center justify-center flex-shrink-0">
            <i class="fas fa-robot text-white text-sm"></i>
          </div>
          <div class="flex-1">
            <p class="text-gray-800">${text}</p>
          </div>
        </div>
      </div>
    `;
  }
  
  chatBox.appendChild(messageDiv);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function showTypingIndicator() {
  const chatBox = document.getElementById("chat-box");
  const typingDiv = document.createElement("div");
  typingDiv.className = "flex justify-start animate-slide-up";
  typingDiv.id = "typing-indicator";
  typingDiv.innerHTML = `
    <div class="chat-bubble-bot p-4 max-w-4xl shadow-lg">
      <div class="flex items-start space-x-3">
        <div class="w-8 h-8 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full flex items-center justify-center flex-shrink-0">
          <i class="fas fa-robot text-white text-sm"></i>
        </div>
        <div class="flex-1">
          <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>
    </div>
  `;
  chatBox.appendChild(typingDiv);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function removeTypingIndicator() {
  const typingBubble = document.getElementById("typing-indicator");
  if (typingBubble) {
    typingBubble.remove();
  }
}

/**
 * Product Display Functions
 */
function createProductCard(product, isInSidebar = false) {
  // Validate that this is a real product with proper data
  if (!product || !product.product_id || !product.product_name || !product.image_url) {
    return ''; // Return empty string for invalid products
  }
  
  const encodedName = encodeURIComponent(product.product_name);
  
  // Check if product has promotion
  const hasPromotion = product.has_promotion || (product.PROMO_DISCOUNT_PERCENT && product.PROMO_DISCOUNT_PERCENT > 0);
  const discountPercent = product.discount_percent || product.PROMO_DISCOUNT_PERCENT || 0;
  const originalPrice = product.original_price || product.PRICE || product.price || 0;
  const discountedPrice = product.discounted_price || product.price || 0;
  const promoTitle = product.promo_title || product.PROMO_TITLE || 'Special Offer';
  
  if (isInSidebar) {
    // Compact card for sidebar WITH PROMOTION SUPPORT
    return `
      <div class="bg-white/80 backdrop-blur-sm rounded-2xl p-4 hover:bg-white/95 transition-all duration-300 cursor-pointer product-card-hover border border-purple-200/50 hover:border-purple-300/70 group shadow-lg hover:shadow-xl relative" onclick="openProductDetail('${product.product_id}')">
        ${hasPromotion ? `
          <div class="absolute -top-2 -right-2 bg-gradient-to-r from-red-500 to-pink-500 text-white text-xs font-bold px-2 py-1 rounded-full shadow-lg z-10 animate-pulse">
            ${discountPercent}% OFF
          </div>
        ` : ''}
        <div class="flex items-center space-x-3">
          <div class="relative">
            <img src="${product.image_url}" alt="${product.product_name}" class="w-14 h-14 object-cover rounded-xl flex-shrink-0 shadow-md group-hover:scale-105 transition-transform duration-300" onerror="this.style.display='none'">
            <div class="absolute -top-1 -right-1 w-4 h-4 bg-gradient-to-r from-purple-500 to-pink-500 rounded-full flex items-center justify-center">
              <i class="fas fa-star text-white text-xs"></i>
            </div>
          </div>
          <div class="flex-1 min-w-0">
            <h4 class="font-bold text-gray-800 text-sm truncate group-hover:text-purple-600 transition-colors">${product.product_name}</h4>
            <p class="text-xs text-gray-500 mt-1 line-clamp-1">${product.summary || 'Premium quality product'}</p>
            <div class="flex items-center justify-between mt-2">
              <div class="flex flex-col">
                ${hasPromotion ? `
                  <span class="text-xs text-gray-400 line-through">£${originalPrice ? originalPrice.toFixed(2) : '0.00'}</span>
                  <span class="font-bold text-green-600 text-lg">£${discountedPrice ? discountedPrice.toFixed(2) : '0.00'}</span>
                ` : `
                  <span class="font-bold text-purple-600 text-lg">£${product.price ? product.price.toFixed(2) : '0.00'}</span>
                `}
              </div>
              <button 
                onclick="addToCart('${product.product_id}', '${product.product_name.replace(/'/g, "\\'")}', event)" 
                class="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white text-xs px-3 py-1.5 rounded-full transition-all duration-300 transform hover:scale-110 shadow-md hover:shadow-lg"
                title="Add to Cart"
              >
                <i class="fas fa-cart-plus"></i>
              </button>
            </div>
          </div>
        </div>
      </div>
    `;
  } else {
    // Compact modern card for main chat area WITH PROMOTION SUPPORT
    return `
      <div class="bg-white/90 backdrop-blur-sm rounded-3xl shadow-xl overflow-hidden product-card-modern border-2 border-purple-100/50 hover:border-purple-300/70 w-64 flex-shrink-0 group transition-all duration-500 relative" onclick="openProductDetail('${product.product_id}')">
        <div class="relative overflow-hidden">
          <img src="${product.image_url}" alt="${product.product_name}" class="w-full h-40 object-cover group-hover:scale-110 transition-transform duration-700" onerror="this.style.display='none'">
          <div class="absolute inset-0 bg-gradient-to-t from-black/30 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
          
          ${hasPromotion ? `
            <div class="absolute top-3 right-3 bg-gradient-to-r from-red-500 to-pink-500 backdrop-blur-sm rounded-full px-3 py-1.5 text-xs font-bold text-white shadow-lg transform -rotate-3 group-hover:rotate-0 transition-transform duration-300 z-10">
              <i class="fas fa-tag mr-1"></i>${discountPercent}% OFF
            </div>
            <div class="absolute top-3 left-3 bg-green-500/90 backdrop-blur-sm rounded-lg px-2 py-1 text-xs font-semibold text-white shadow-lg">
              SALE
            </div>
          ` : `
            <div class="absolute top-3 right-3 bg-gradient-to-r from-purple-500 to-pink-500 backdrop-blur-sm rounded-full px-3 py-1 text-xs font-bold text-white shadow-lg transform rotate-3 group-hover:rotate-0 transition-transform duration-300">
              Featured
            </div>
          `}
          
          <div class="absolute top-3 ${hasPromotion ? 'left-3' : 'left-3'} bg-white/20 backdrop-blur-sm rounded-full p-2 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
            <i class="fas fa-heart text-white text-sm"></i>
          </div>
        </div>
        <div class="p-5">
          ${hasPromotion ? `
            <div class="mb-2 text-xs text-red-600 font-semibold flex items-center">
              <i class="fas fa-fire mr-1 animate-pulse"></i>
              ${promoTitle}
            </div>
          ` : ''}
          
          <h3 class="font-bold text-gray-800 text-base mb-2 line-clamp-2 group-hover:text-purple-600 transition-colors duration-300">${product.product_name}</h3>
          <p class="text-gray-500 text-xs mb-4 line-clamp-2 leading-relaxed">${product.summary || 'Premium quality product with excellent features'}</p>
          
          <div class="flex items-center justify-between mb-3">
            <div class="flex flex-col">
              ${hasPromotion ? `
                <span class="text-sm text-gray-400 line-through">£${originalPrice ? originalPrice.toFixed(2) : '0.00'}</span>
                <div class="flex items-center gap-2">
                  <span class="text-xl font-bold text-green-600">£${discountedPrice ? discountedPrice.toFixed(2) : '0.00'}</span>
                  <span class="text-xs bg-red-100 text-red-600 px-2 py-0.5 rounded-full font-bold">-${discountPercent}%</span>
                </div>
                <span class="text-xs text-green-600 font-semibold">Save £${((originalPrice || 0) - (discountedPrice || 0)).toFixed(2)}</span>
              ` : `
                <span class="text-xl font-bold text-purple-600">£${product.price ? product.price.toFixed(2) : '0.00'}</span>
              `}
</div>
            <div class="flex items-center space-x-1">
              <div class="flex text-yellow-400">
                <i class="fas fa-star text-xs"></i>
                <i class="fas fa-star text-xs"></i>
                <i class="fas fa-star text-xs"></i>
                <i class="fas fa-star text-xs"></i>
                <i class="fas fa-star-half-alt text-xs"></i>
              </div>
              <span class="text-xs text-gray-400">(4.5)</span>
            </div>
          </div>
          
          <button 
            onclick="addToCart('${product.product_id}', '${product.product_name.replace(/'/g, "\\'")}', event)" 
            class="w-full ${hasPromotion ? 'bg-gradient-to-r from-green-600 via-green-500 to-emerald-500 hover:from-green-700 hover:via-green-600 hover:to-emerald-600' : 'bg-gradient-to-r from-purple-600 via-purple-500 to-pink-500 hover:from-purple-700 hover:via-purple-600 hover:to-pink-600'} text-white py-2.5 rounded-2xl font-semibold transition-all duration-300 transform hover:scale-105 shadow-lg hover:shadow-2xl flex items-center justify-center space-x-2"
            title="Add to Cart"
          >
            <i class="fas fa-cart-plus text-sm"></i>
            <span class="text-sm">${hasPromotion ? 'Get Deal' : 'Add to Cart'}</span>
          </button>
        </div>
      </div>
    `;
  }
}

function createDetailedProductView(product, aiResponse, crossSellProducts) {
  // Validate that this is a real product with proper data
  if (!product || !product.product_id || !product.product_name) {
    return ''; // Return empty string for invalid products
  }

  // Handle missing image URL
  const imageUrl = product.image_url || 'https://via.placeholder.com/400x400/667eea/ffffff?text=No+Image';
  const encodedName = encodeURIComponent(product.product_name);
  const categories = product.categories || [];
  const categoryTags = categories.length > 0 
    ? categories.map(cat => `<span class="inline-block bg-purple-100 text-purple-800 text-xs px-3 py-1 rounded-full mr-2 mb-2">${cat}</span>`).join('')
    : '<span class="inline-block bg-gray-100 text-gray-600 text-xs px-3 py-1 rounded-full">No categories</span>';

  return `
    <div class="detailed-product-view bg-gradient-to-br from-white via-purple-50 to-pink-50 rounded-3xl shadow-2xl overflow-hidden border border-purple-200/50 max-w-5xl mx-auto my-6">
      <!-- Product Header -->
      <div class="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 px-8 py-6 text-white">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-4">
            <div class="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center">
              <i class="fas fa-box-open text-white text-lg"></i>
            </div>
            <div>
              <h3 class="text-xl font-bold">Product Details</h3>
              <p class="text-sm opacity-90">Complete product information</p>
            </div>
          </div>
          <div class="flex items-center space-x-3">
            <div class="flex text-yellow-300">
              <i class="fas fa-star text-sm"></i>
              <i class="fas fa-star text-sm"></i>
              <i class="fas fa-star text-sm"></i>
              <i class="fas fa-star text-sm"></i>
              <i class="fas fa-star-half-alt text-sm"></i>
            </div>
            <span class="text-sm font-medium opacity-90">(4.5/5)</span>
          </div>
        </div>
      </div>

      <!-- Product Content -->
      <div class="p-8">
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-10 items-start">
          
          <!-- Product Image Section -->
          <div class="relative">
            <div class="relative overflow-hidden rounded-3xl shadow-2xl bg-gradient-to-br from-gray-50 to-gray-100 p-6">
              <img 
                src="${imageUrl}" 
                alt="${product.product_name}" 
                class="w-full h-96 object-cover rounded-2xl transition-all duration-500 hover:scale-105 shadow-lg"
                onerror="this.src='https://via.placeholder.com/400x400/667eea/ffffff?text=No+Image'"
              >
              <!-- Image Overlay Effects -->
              <div class="absolute inset-6 bg-gradient-to-t from-black/30 via-transparent to-transparent opacity-0 hover:opacity-100 transition-opacity duration-300 rounded-2xl pointer-events-none"></div>
              
              <!-- Product Badge -->
              <div class="absolute top-8 left-8 bg-gradient-to-r from-green-500 to-emerald-500 text-white px-4 py-2 rounded-full text-sm font-bold shadow-xl backdrop-blur-sm">
                <i class="fas fa-check-circle mr-2"></i>
                Available
              </div>
              
              <!-- Product ID Badge -->
              <div class="absolute top-8 right-8 bg-white/90 backdrop-blur-sm rounded-full px-3 py-1.5 shadow-lg">
                <span class="text-xs font-bold text-gray-600">ID: ${product.product_id}</span>
              </div>
              
              <!-- Favorite Button -->
              <div class="absolute bottom-8 right-8 bg-white/90 backdrop-blur-sm rounded-full p-3 shadow-xl hover:bg-white transition-all duration-300 cursor-pointer group hover:scale-110">
                <i class="fas fa-heart text-gray-400 group-hover:text-red-500 transition-colors duration-300 text-lg"></i>
              </div>
            </div>
            
            <!-- Product Gallery Thumbnails -->
            <div class="flex space-x-4 mt-6 justify-center">
              <div class="w-20 h-20 bg-gradient-to-br from-purple-100 to-pink-100 rounded-xl cursor-pointer border-3 border-purple-500 shadow-lg flex items-center justify-center">
                <i class="fas fa-image text-purple-500 text-lg"></i>
              </div>
              <div class="w-20 h-20 bg-gradient-to-br from-gray-100 to-gray-200 rounded-xl cursor-pointer hover:border-3 hover:border-purple-300 transition-all duration-300 shadow-md hover:shadow-lg flex items-center justify-center opacity-60">
                <i class="fas fa-camera text-gray-400"></i>
              </div>
              <div class="w-20 h-20 bg-gradient-to-br from-gray-100 to-gray-200 rounded-xl cursor-pointer hover:border-3 hover:border-purple-300 transition-all duration-300 shadow-md hover:shadow-lg flex items-center justify-center opacity-60">
                <i class="fas fa-video text-gray-400"></i>
              </div>
            </div>
          </div>

          <!-- Product Info Section -->
          <div class="space-y-8">
            <!-- Product Title & Price -->
            <div>
              <div class="flex items-start justify-between mb-4">
                <div class="flex-1">
                  <h1 class="text-3xl lg:text-4xl font-bold text-gray-900 mb-2 leading-tight">${product.product_name}</h1>
                  <div class="flex items-center space-x-2 text-sm text-gray-500">
                    <span>Product ID: ${product.product_id}</span>
                    <span>•</span>
                    <span class="text-green-600 font-medium">In Stock</span>
                  </div>
                </div>
              </div>
              
              <div class="bg-gradient-to-r from-purple-50 to-pink-50 rounded-2xl p-6 border border-purple-200/50">
                <div class="flex items-center justify-between flex-wrap gap-4">
                  <div class="flex items-baseline space-x-4">
                    <span class="text-4xl lg:text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-purple-600 to-pink-600">£${product.price ? product.price.toFixed(2) : '0.00'}</span>
                    <div class="flex flex-col">
                      <span class="text-lg text-gray-500 line-through">£${product.price ? (product.price * 1.2).toFixed(2) : '0.00'}</span>
                      <span class="bg-gradient-to-r from-red-500 to-pink-500 text-white text-sm px-3 py-1 rounded-full font-bold shadow-lg">Save 17%</span>
                    </div>
                  </div>
                  <div class="text-right">
                    <div class="text-sm text-gray-600">Free shipping</div>
                    <div class="text-sm text-green-600 font-medium">✓ 30-day returns</div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Product Categories -->
            <div>
              <h4 class="text-lg font-semibold text-gray-900 mb-3 flex items-center">
                <i class="fas fa-tags text-purple-500 mr-2"></i>
                Categories
              </h4>
              <div class="flex flex-wrap gap-2">
                ${categoryTags}
              </div>
            </div>

            <!-- Product Description -->
            <div>
              <h4 class="text-lg font-semibold text-gray-900 mb-3 flex items-center">
                <i class="fas fa-info-circle text-blue-500 mr-2"></i>
                Description
              </h4>
              <div class="bg-gray-50 rounded-2xl p-6 border border-gray-200">
                <p class="text-gray-700 leading-relaxed text-lg">${product.summary || 'This is a premium quality product with excellent features and craftsmanship. Perfect for customers who value quality and style.'}</p>
              </div>
            </div>

            <!-- Product Features -->
            <div>
              <h4 class="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                <i class="fas fa-star text-yellow-500 mr-2"></i>
                Key Features
              </h4>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div class="flex items-center space-x-3 p-3 bg-green-50 rounded-xl border border-green-200">
                  <i class="fas fa-check-circle text-green-500 text-lg"></i>
                  <span class="text-gray-700 font-medium">Premium Quality</span>
                </div>
                <div class="flex items-center space-x-3 p-3 bg-blue-50 rounded-xl border border-blue-200">
                  <i class="fas fa-shipping-fast text-blue-500 text-lg"></i>
                  <span class="text-gray-700 font-medium">Fast Delivery</span>
                </div>
                <div class="flex items-center space-x-3 p-3 bg-purple-50 rounded-xl border border-purple-200">
                  <i class="fas fa-undo text-purple-500 text-lg"></i>
                  <span class="text-gray-700 font-medium">30-Day Returns</span>
                </div>
                <div class="flex items-center space-x-3 p-3 bg-orange-50 rounded-xl border border-orange-200">
                  <i class="fas fa-headset text-orange-500 text-lg"></i>
                  <span class="text-gray-700 font-medium">24/7 Support</span>
                </div>
              </div>
            </div>

            <!-- Quantity Selector & Add to Cart -->
            <div class="bg-gradient-to-r from-purple-50 to-pink-50 rounded-2xl p-6 border border-purple-200/50">
              <div class="flex items-center space-x-4 mb-4">
                <div class="flex items-center space-x-3">
                  <label class="text-sm font-medium text-gray-700">Quantity:</label>
                  <div class="flex items-center bg-white rounded-xl border border-gray-300 shadow-sm">
                    <button class="px-3 py-2 text-gray-500 hover:text-purple-600 transition-colors duration-300" onclick="decreaseQuantity('${product.product_id}')">
                      <i class="fas fa-minus text-sm"></i>
                    </button>
                    <input 
                      type="number" 
                      id="quantity-${product.product_id}" 
                      value="1" 
                      min="1" 
                      max="10"
                      class="w-16 text-center border-0 focus:outline-none focus:ring-0 py-2 text-sm font-medium text-gray-900"
                    >
                    <button class="px-3 py-2 text-gray-500 hover:text-purple-600 transition-colors duration-300" onclick="increaseQuantity('${product.product_id}')">
                      <i class="fas fa-plus text-sm"></i>
                    </button>
                  </div>
                </div>
              </div>

              <!-- Action Buttons -->
              <div class="flex space-x-4">
                <button 
                  onclick="addToCartDetailed('${product.product_id}', '${product.product_name.replace(/'/g, "\\'")}', ${product.price || 0})"
                  class="flex-1 bg-gradient-to-r from-purple-600 via-purple-500 to-pink-500 hover:from-purple-700 hover:via-purple-600 hover:to-pink-600 text-white py-4 px-6 rounded-2xl font-bold text-lg transition-all duration-300 transform hover:scale-105 shadow-xl hover:shadow-2xl flex items-center justify-center space-x-3 group"
                >
                  <i class="fas fa-cart-plus text-xl group-hover:animate-pulse"></i>
                  <span>Add to Cart</span>
                </button>
                
                <button 
                  class="bg-white hover:bg-gray-50 border-2 border-purple-300 text-purple-600 hover:text-purple-700 py-4 px-6 rounded-2xl font-bold transition-all duration-300 hover:shadow-lg flex items-center justify-center min-w-fit"
                  title="Add to Wishlist"
                >
                  <i class="fas fa-heart text-xl"></i>
                </button>
              </div>
            </div>

            <!-- Delivery Information -->
            <div class="grid grid-cols-2 gap-4 text-sm">
              <div class="flex items-center space-x-3 p-3 bg-green-50 rounded-xl border border-green-200">
                <i class="fas fa-shipping-fast text-green-600 text-lg"></i>
                <div>
                  <p class="font-medium text-green-800">Free Delivery</p>
                  <p class="text-green-600">2-3 business days</p>
                </div>
              </div>
              <div class="flex items-center space-x-3 p-3 bg-blue-50 rounded-xl border border-blue-200">
                <i class="fas fa-shield-alt text-blue-600 text-lg"></i>
                <div>
                  <p class="font-medium text-blue-800">Secure Payment</p>
                  <p class="text-blue-600">SSL Encrypted</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}

/**
 * 🔗 ADD CROSS-SELL TO PRODUCT DETAILS
 * Appends "You May Also Like" section with related products
 */
function appendCrossSellToProductView(baseHtml, crossSellProducts) {
  console.log('🔗 appendCrossSellToProductView called');
  console.log('🔗 crossSellProducts:', crossSellProducts);
  console.log('🔗 Is array?', Array.isArray(crossSellProducts));
  console.log('🔗 Length:', crossSellProducts ? crossSellProducts.length : 0);
  
  if (!crossSellProducts || !Array.isArray(crossSellProducts) || crossSellProducts.length === 0) {
    console.warn('⚠️ appendCrossSellToProductView: No valid cross-sell data, returning base HTML');
    return baseHtml; // No cross-sell data, return base HTML
  }

  console.log('🔗 Adding', crossSellProducts.length, 'cross-sell products to product detail view');
  
  const crossSellCarousel = createProductCarousel(crossSellProducts);
  console.log('🔗 crossSellCarousel created:', crossSellCarousel ? 'YES' : 'NO');
  
  if (!crossSellCarousel) {
    console.warn('⚠️ appendCrossSellToProductView: Carousel creation failed');
    return baseHtml;
  }

  // Append cross-sell section after product details
  const result = baseHtml + `
    <div class="mt-8 px-4">
      <div class="flex items-center justify-start mb-6">
        <div class="flex items-center space-x-3">
          <div class="w-12 h-12 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full flex items-center justify-center shadow-lg">
            <i class="fas fa-heart text-white text-xl"></i>
          </div>
          <h3 class="text-2xl lg:text-3xl font-bold text-gray-800">You May Also Like</h3>
        </div>
      </div>
      ${crossSellCarousel}
    </div>
  `;
  
  console.log('✅ appendCrossSellToProductView: Cross-sell section appended successfully');
  return result;
}

/**
 * 🤖 AI-DRIVEN SEARCH SUGGESTIONS
 * Renders Copilot-like intelligent suggestions after search results
 * Provides contextual, actionable recommendations based on AI analysis
 */
function createAISuggestionsPanel(ai_suggestions) {
  if (!ai_suggestions || !ai_suggestions.has_suggestions || !Array.isArray(ai_suggestions.suggestions)) {
    return '';
  }

  const suggestions = ai_suggestions.suggestions;
  if (suggestions.length === 0) {
    return '';
  }

  // Extract original query context for maintaining search context
  const queryContext = ai_suggestions.query_context || '';

  // Map suggestion types to icons and colors
  const suggestionStyles = {
    'accessories': { icon: 'fa-puzzle-piece', color: 'purple', gradient: 'from-purple-500 to-pink-500' },
    'budget': { icon: 'fa-wallet', color: 'green', gradient: 'from-green-500 to-emerald-500' },
    'category': { icon: 'fa-th-large', color: 'blue', gradient: 'from-blue-500 to-indigo-500' },
    'personalization': { icon: 'fa-user-circle', color: 'orange', gradient: 'from-orange-500 to-red-500' },
    'promotions': { icon: 'fa-tag', color: 'red', gradient: 'from-red-500 to-pink-500' },
    'general': { icon: 'fa-lightbulb', color: 'yellow', gradient: 'from-yellow-400 to-orange-400' }
  };

  // Create suggestion cards with proper data attributes
  const suggestionCards = suggestions.map((suggestion, index) => {
    const style = suggestionStyles[suggestion.type] || suggestionStyles['general'];
    const sanitizedText = escapeHtml(suggestion.text);
    
    return `
      <div class="suggestion-card group relative bg-white rounded-2xl p-4 border-2 border-${style.color}-100 hover:border-${style.color}-300 hover:shadow-xl transition-all duration-300 cursor-pointer transform hover:-translate-y-1"
           data-suggestion-type="${suggestion.type}" 
           data-suggestion-text="${escapeHtml(suggestion.text)}"
           data-suggestion-index="${index}"
           data-query-context="${escapeHtml(queryContext)}">
        <div class="flex items-start space-x-4">
          <div class="flex-shrink-0">
            <div class="w-12 h-12 rounded-xl bg-gradient-to-br ${style.gradient} flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform duration-300">
              <i class="fas ${style.icon} text-white text-lg"></i>
            </div>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-gray-800 text-sm leading-relaxed group-hover:text-${style.color}-700 transition-colors duration-300">
              ${sanitizedText}
            </p>
          </div>
          <div class="flex-shrink-0">
            <i class="fas fa-chevron-right text-gray-300 group-hover:text-${style.color}-500 group-hover:translate-x-1 transition-all duration-300 text-sm"></i>
          </div>
        </div>
      </div>
    `;
  }).join('');

  const panelHtml = `
    <div class="ai-suggestions-panel mt-4">
      <div class="grid grid-cols-1 ${suggestions.length === 2 ? 'md:grid-cols-2' : 'md:grid-cols-2 lg:grid-cols-3'} gap-3" id="ai-suggestions-container">
        ${suggestionCards}
      </div>
    </div>
  `;
  
  return panelHtml;
}

/**
 * Handle AI suggestion click events
 * Processes user interaction with AI suggestions and triggers appropriate actions
 */
function handleAISuggestionClick(type, text, queryContext) {
  console.log('🤖 AI Suggestion clicked:', type, text, 'Context:', queryContext);
  
  // Extract actionable intent from suggestion text
  let query = '';
  
  // Extract product category from original query context for price-based suggestions
  const extractProductCategory = (context) => {
    if (!context) return '';
    const lowerContext = context.toLowerCase();
    // Common product categories
    const categories = ['tshirts', 't-shirts', 'jackets', 'shoes', 'watches', 'sunglasses', 'bags', 'caps', 'shorts', 'hoodies', 'sweatshirts', 'socks', 'accessories'];
    for (const cat of categories) {
      if (lowerContext.includes(cat)) {
        return cat;
      }
    }
    return '';
  };
  
  switch(type) {
    case 'accessories': {
      // User clicked on accessories suggestion - grab product IDs now for backend
      query = 'show me accessories for these products';
      if (window.conversationContext) {
        const recentProducts = window.conversationContext.getRecentDisplayedProducts();
        const lastProducts = window.conversationContext.getLastProducts(10);
        const products = recentProducts.length > 0 ? recentProducts : lastProducts;
        if (products.length > 0) {
          const ids = products.map(p => p.product_id).filter(id => id);
          const names = products.map(p => p.product_name).filter(n => n);
          if (ids.length > 0) {
            // Store context so submitQuery can embed it without changing the user-visible text
            window._pendingAccessoryProducts = { ids, names };
          }
        }
      }
      break;
    }
    
    case 'budget':
      // Extract budget from text if possible, otherwise ask
      const dollarMatch = text.match(/\$(\d+)/i);
      const poundMatch = text.match(/£(\d+)/i);
      const numberMatch = text.match(/(\d+)\s*(?:dollars?|pounds?)/i);
      
      // Extract product category from original query to maintain context
      const productCategory = extractProductCategory(queryContext);
      
      if (dollarMatch) {
        query = productCategory ? `show ${productCategory} under ${dollarMatch[1]}` : 'show products under ' + dollarMatch[1];
      } else if (poundMatch) {
        query = productCategory ? `show ${productCategory} under ${poundMatch[1]}` : 'show products under ' + poundMatch[1];
      } else if (numberMatch) {
        query = productCategory ? `show ${productCategory} under ${numberMatch[1]}` : 'show products under ' + numberMatch[1];
      } else {
        // Show budget input dialog
        showBudgetFilterDialog();
        return;
      }
      break;
    
    case 'category':
      // Extract category name from text - look for common patterns
      const categoryMatch = text.match(/collection of ([a-z\s]+)/i);
      const ourMatch = text.match(/our ([a-z\s]+)\./i);
      const interestedMatch = text.match(/interested in ([a-z\s]+)/i);
      
      if (categoryMatch) {
        query = 'show me ' + categoryMatch[1];
      } else if (ourMatch) {
        query = 'show me ' + ourMatch[1];
      } else if (interestedMatch) {
        query = 'show me ' + interestedMatch[1];
      } else {
        query = text;
      }
      break;
    
    case 'promotions':
      query = 'show me any offers on these products';
      break;
    
    case 'personalization':
      // For personalization, extract the question and convert to action
      query = text;
      break;
    
    case 'general':
    default:
      query = text;
      break;
  }
  
  console.log('🎯 Executing suggestion query:', query);
  
  // Send query to chat - using correct element ID and function
  const chatInput = document.getElementById('query'); // ✅ FIXED: Correct ID
  if (!chatInput) {
    console.error('❌ Chat input element not found! ID: query');
    return;
  }
  
  if (!query) {
    console.error('❌ Query is empty!');
    return;
  }
  
  console.log('✅ Setting chat input value to:', query);
  chatInput.value = query;
  
  // Focus on input
  chatInput.focus();
  
  // Small delay to ensure value is set, then submit
  setTimeout(() => {
    // Trigger submitQuery function (the actual send function)
    if (typeof submitQuery === 'function') {
      console.log('✅ Calling submitQuery function');
      submitQuery();
    } else {
      console.error('❌ submitQuery function not found!');
      console.log('Attempting to click send button as fallback...');
      const sendButton = document.querySelector('[onclick="submitQuery()"]');
      if (sendButton) {
        sendButton.click();
      }
    }
  }, 100);
}

/**
 * Show budget filter dialog for user input
 */
function showBudgetFilterDialog() {
  // Use browser prompt for simplicity (can be enhanced with modal later)
  const budget = prompt('What is your budget? (e.g., 50, 100, 200)');
  if (budget && !isNaN(budget)) {
    const chatInput = document.getElementById('query'); // ✅ FIXED: Correct ID
    if (chatInput) {
      chatInput.value = 'show products under ' + budget;
      if (typeof submitQuery === 'function') {
        submitQuery();
      }
    }
  }
}

function createProductCarousel(products) {
  // Filter out invalid products and create cards
  const validProducts = products.filter(product => 
    product && product.product_id && product.product_name && product.image_url
  );
  
  if (validProducts.length === 0) {
    return ''; // Return empty string if no valid products
  }
  
  const carouselId = 'carousel-' + Date.now();
  
  if (validProducts.length === 1) {
    // Single product display with enhanced styling
    const productHtml = createProductCard(validProducts[0], false);
    return `
      <div class="relative">
        <div class="bg-gradient-to-r from-purple-50 to-pink-50 rounded-3xl p-6 border border-purple-100">
          <div class="flex items-center justify-center mb-4">
            <div class="flex items-center space-x-3 text-purple-600">
              <i class="fas fa-star text-xl animate-pulse"></i>
              <h3 class="text-lg font-bold">Featured Product</h3>
              <i class="fas fa-star text-xl animate-pulse"></i>
            </div>
          </div>
          <div class="flex justify-center">
            ${productHtml}
          </div>
        </div>
      </div>
    `;
  } else if (validProducts.length <= 3) {
    // Small number of products - enhanced grid display
    const productsHtml = validProducts.map(product => createProductCard(product, false)).join('');
    return `
      <div class="relative">
        <div class="bg-gradient-to-br from-purple-50 via-white to-pink-50 rounded-3xl p-6 border border-purple-100">
          <div class="flex items-center justify-between mb-6">
            <div class="flex items-center space-x-3">
              <div class="w-10 h-10 bg-gradient-to-r from-purple-500 to-pink-500 rounded-full flex items-center justify-center">
                <i class="fas fa-shopping-bag text-white"></i>
              </div>
              <div>
                <h3 class="text-lg font-bold text-gray-800">Product Results</h3>
                <p class="text-sm text-gray-500">${validProducts.length} items found</p>
              </div>
            </div>
            <div class="bg-white/70 backdrop-blur-sm rounded-full px-4 py-2 border border-purple-200">
              <span class="text-sm font-semibold text-purple-600">${validProducts.length} Products</span>
            </div>
          </div>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 place-items-center">
            ${productsHtml}
          </div>
        </div>
      </div>
    `;
  } else {
    // Multiple products - enhanced carousel with better styling
    const productsHtml = validProducts.map(product => createProductCard(product, false)).join('');
    return `
      <div class="relative">
        <div class="bg-gradient-to-br from-purple-50 via-white to-pink-50 rounded-3xl p-6 border border-purple-100">
          <div class="flex items-center justify-between mb-6">
            <div class="flex items-center space-x-3">
              <div class="w-12 h-12 bg-gradient-to-r from-purple-500 to-pink-500 rounded-2xl flex items-center justify-center shadow-lg">
                <i class="fas fa-shopping-bag text-white text-lg"></i>
              </div>
              <div>
                <h3 class="text-xl font-bold text-gray-800 flex items-center">
                  Product Collection
                  <span class="ml-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white text-xs px-3 py-1 rounded-full">${validProducts.length}</span>
                </h3>
                <p class="text-sm text-gray-500 flex items-center mt-1">
                  <i class="fas fa-fire text-orange-500 mr-1"></i>
                  Trending products just for you
                </p>
              </div>
            </div>
            <div class="flex items-center space-x-3">
              <div class="bg-white/70 backdrop-blur-sm rounded-full px-4 py-2 border border-purple-200 flex items-center space-x-2">
                <i class="fas fa-eye text-purple-500 text-sm"></i>
                <span class="text-sm font-semibold text-purple-600">View All</span>
              </div>
              <div class="flex space-x-2">
                <button onclick="scrollCarousel('${carouselId}', -280)" class="w-10 h-10 bg-white hover:bg-purple-50 rounded-full flex items-center justify-center shadow-lg transition-all duration-300 hover:scale-110 border border-purple-200 group">
                  <i class="fas fa-chevron-left text-gray-600 group-hover:text-purple-600 transition-colors"></i>
                </button>
                <button onclick="scrollCarousel('${carouselId}', 280)" class="w-10 h-10 bg-white hover:bg-purple-50 rounded-full flex items-center justify-center shadow-lg transition-all duration-300 hover:scale-110 border border-purple-200 group">
                  <i class="fas fa-chevron-right text-gray-600 group-hover:text-purple-600 transition-colors"></i>
                </button>
              </div>
            </div>
          </div>
          <div id="${carouselId}" class="flex space-x-5 overflow-x-auto pb-4 scroll-smooth custom-scrollbar" style="scrollbar-width: none; -ms-overflow-style: none;">
            ${productsHtml}
          </div>
        </div>
      </div>
    `;
  }
}

function createVisualSearchResponse(data) {
  if (!data || typeof data !== 'object') {
    return '';
  }

  const previewUrl = data.image_preview ? escapeHtml(data.image_preview) : '';
  const imageName = data.image_name ? escapeHtml(data.image_name) : 'Uploaded image';
  const hasProducts = Array.isArray(data.products_data) && data.products_data.length > 0;
  const insightsHtml = renderVisualSearchInsights(data.analysis || {});
  const aiSummary = data.ai_response ? `<p class="text-sm md:text-base text-gray-600 leading-relaxed">${data.ai_response}</p>` : '';
  const searchFocus = data.query_generated ? `<p class="text-xs text-gray-500">Search focus: ${escapeHtml(data.query_generated)}</p>` : '';
  const errorNotice = data.success === false && data.error
    ? `<div class="bg-red-50 border border-red-200 text-red-700 rounded-2xl px-4 py-3 text-sm">${escapeHtml(data.error)}</div>`
    : '';

  let productsSection = '';
  if (hasProducts) {
    productsSection = `<div class="mt-6">${createProductCarousel(data.products_data)}</div>`;
  } else if (data.success) {
    productsSection = `
      <div class="mt-6 bg-white/80 border border-dashed border-purple-200 rounded-3xl p-6 text-center text-gray-600">
        <i class="fas fa-search-minus text-2xl text-purple-400 mb-3"></i>
        <p class="font-semibold text-gray-700">I couldn't find exact catalog matches for this image.</p>
        <p class="text-sm text-gray-500 mt-2">Try a different angle or ensure the product is well lit for better results.</p>
      </div>
    `;
  }

  const imagePreviewHtml = previewUrl
    ? `
      <div class="w-full md:w-48">
        <div class="relative rounded-2xl overflow-hidden shadow-lg border border-white/80">
          <img src="${previewUrl}" alt="${imageName}" class="w-full h-44 object-cover" loading="lazy"/>
          <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent px-3 py-2 text-xs text-white">
            <i class="fas fa-camera mr-2"></i>${imageName}
          </div>
        </div>
      </div>
    `
    : '';

  return `
    <div class="space-y-6">
      <div class="bg-gradient-to-r from-purple-50 via-white to-blue-50 border border-purple-100 rounded-3xl p-6 shadow-inner">
        <div class="flex flex-col md:flex-row md:items-center md:space-x-6 space-y-4 md:space-y-0">
          ${imagePreviewHtml}
          <div class="flex-1 space-y-4">
            <div class="flex items-center space-x-3">
              <div class="w-12 h-12 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white shadow-lg">
                <i class="fas fa-image"></i>
              </div>
              <div>
                <h3 class="text-lg md:text-xl font-bold text-gray-800">Visual Search Insights</h3>
                ${searchFocus}
              </div>
            </div>
            ${aiSummary}
            ${insightsHtml}
            ${errorNotice}
          </div>
        </div>
      </div>
      ${productsSection}
    </div>
  `;
}

function renderVisualSearchInsights(analysis) {
  if (!analysis || typeof analysis !== 'object') {
    return '';
  }

  const sections = [];
  const productType = typeof analysis.product_type === 'string' ? analysis.product_type.trim() : '';
  const category = typeof analysis.category === 'string' ? analysis.category.trim() : '';

  if (productType || category) {
    const badges = [];
    if (productType) {
      badges.push(`<span class="text-base font-semibold text-purple-600">${escapeHtml(productType)}</span>`);
    }
    if (category) {
      badges.push(`<span class="text-sm text-gray-500">Category: ${escapeHtml(category)}</span>`);
    }
    if (badges.length > 0) {
      sections.push(`<div class="flex flex-wrap items-center gap-3">${badges.join('<span class="text-gray-300">•</span>')}</div>`);
    }
  }

  const colorsHtml = renderColorChips(analysis.colors);
  if (colorsHtml) {
    sections.push(colorsHtml);
  }

  const attributesHtml = renderInsightPills('Attributes', analysis.attributes);
  if (attributesHtml) {
    sections.push(attributesHtml);
  }

  const keywordsHtml = renderInsightPills('Keywords', analysis.keywords);
  if (keywordsHtml) {
    sections.push(keywordsHtml);
  }

  if (sections.length === 0) {
    return '';
  }

  return `<div class="space-y-3">${sections.join('')}</div>`;
}

function renderColorChips(values) {
  if (!Array.isArray(values) || values.length === 0) {
    return '';
  }

  const chips = values
    .map(createColorChip)
    .filter(Boolean)
    .slice(0, 6)
    .join('');

  if (!chips) {
    return '';
  }

  return `
    <div class="flex flex-wrap items-center gap-2">
      <span class="text-xs font-semibold uppercase tracking-wide text-gray-500">Colors</span>
      ${chips}
    </div>
  `;
}

function createColorChip(color) {
  if (typeof color !== 'string') {
    return '';
  }

  const rawValue = color.trim();
  if (!rawValue) {
    return '';
  }

  const cssColor = sanitizeColorValue(rawValue);
  const displayLabel = escapeHtml(rawValue.toUpperCase());

  if (cssColor) {
    return `
      <span class="inline-flex items-center gap-2 bg-white/80 border border-gray-200 px-3 py-1 rounded-full text-xs font-medium text-gray-700 shadow-sm">
        <span class="w-3.5 h-3.5 rounded-full border border-gray-200 shadow-sm" style="background:${escapeHtml(cssColor)};"></span>
        ${displayLabel}
      </span>
    `;
  }

  return `
    <span class="inline-flex items-center bg-white/80 border border-gray-200 px-3 py-1 rounded-full text-xs font-medium text-gray-700 shadow-sm">
      ${escapeHtml(rawValue)}
    </span>
  `;
}

function renderInsightPills(label, values) {
  if (!Array.isArray(values) || values.length === 0) {
    return '';
  }

  const pills = values
    .map(value => (typeof value === 'string' ? value.trim() : ''))
    .filter(Boolean)
    .slice(0, 6)
    .map(value => `<span class="inline-flex items-center bg-white/80 border border-gray-200 px-3 py-1 rounded-full text-xs font-medium text-gray-700 shadow-sm">${escapeHtml(value)}</span>`)
    .join('');

  if (!pills) {
    return '';
  }

  return `
    <div class="flex flex-wrap items-center gap-2">
      <span class="text-xs font-semibold uppercase tracking-wide text-gray-500">${escapeHtml(label)}</span>
      ${pills}
    </div>
  `;
}

function sanitizeColorValue(value) {
  if (typeof value !== 'string') {
    return null;
  }

  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  if (/^#([0-9a-f]{3}|[0-9a-f]{6})$/i.test(trimmed)) {
    return trimmed;
  }

  if (/^[a-z]+$/i.test(trimmed)) {
    return trimmed.toLowerCase();
  }

  return null;
}

/**
 * API and Data Handling Functions
 */
async function submitQuery() {
  console.log("🚀 submitQuery function called");
  
  const queryInput = document.getElementById("query");
  
  console.log("📝 Query input element:", queryInput);
  
  if (!queryInput) {
    console.error("❌ Query input element not found!");
    alert("Error: Query input not found. Please refresh the page.");
    return;
  }
  
  let queryValue = queryInput.value.trim();
  
  console.log("💬 Query value:", queryValue);

  if (!queryValue) {
    console.warn("⚠️ Empty query, showing alert");
    alert("Please enter a query");
    return;
  }

  // 🔐 Check if awaiting payment confirmation
  if (awaitingPaymentConfirmation) {
    const response = queryValue.toLowerCase();
    
    // AI-driven confirmation check (flexible understanding)
    const isConfirmation = 
      response === 'yes' || 
      response === 'y' || 
      response === 'yeah' || 
      response === 'yep' || 
      response === 'sure' || 
      response === 'ok' || 
      response === 'okay' || 
      response === 'confirm' || 
      response === 'proceed' || 
      response === 'continue' || 
      response.includes('yes') ||
      response.includes('confirm');
    
    const isCancellation = 
      response === 'no' || 
      response === 'n' || 
      response === 'nope' || 
      response === 'cancel' || 
      response === 'stop' || 
      response.includes('no') ||
      response.includes('cancel');
    
    // Show user's response
    appendMessage(queryValue, "user");
    queryInput.value = "";
    
    if (isConfirmation) {
      // User confirmed payment
      awaitingPaymentConfirmation = false;
      
      appendBotMessage({
        response: `✅ <strong>Payment Confirmed!</strong><br><br>
          <div style="background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 15px; border-radius: 12px; margin: 10px 0;">
            <div style="display: flex; align-items-center;">
              <i class="fas fa-check-circle" style="font-size: 20px; margin-right: 10px;"></i>
              <div style="font-size: 14px;">
                Great! Processing your payment now. Opening PayPal gateway...
              </div>
            </div>
          </div>`
      });
      
      // Proceed with actual checkout
      setTimeout(() => {
        executePayPalCheckout(pendingCheckoutData);
      }, 1500);
      
    } else if (isCancellation) {
      // User cancelled payment
      awaitingPaymentConfirmation = false;
      pendingCheckoutData = null;
      
      appendBotMessage({
        response: `❌ <strong>Payment Cancelled</strong><br><br>
          <div style="background: linear-gradient(135deg, #f59e0b, #d97706); color: white; padding: 15px; border-radius: 12px; margin: 10px 0;">
            <div style="display: flex; align-items-center;">
              <i class="fas fa-times-circle" style="font-size: 20px; margin-right: 10px;"></i>
              <div style="font-size: 14px;">
                No problem! Your cart items are still safe. You can checkout anytime you're ready.
              </div>
            </div>
          </div>`
      });
      
    } else {
      // Unclear response - ask again
      appendBotMessage({
        response: `🤔 <strong>Confirmation Required</strong><br><br>
          <div style="background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 15px; border-radius: 12px; margin: 10px 0;">
            <div style="font-size: 14px;">
              I'm not sure what you meant. Please respond with:<br>
              • <strong>"yes"</strong> to proceed with payment<br>
              • <strong>"no"</strong> to cancel
            </div>
          </div>`
      });
    }
    
    return; // Exit early, don't process as regular query
  }

  // 🧠 CONVERSATION CONTEXT ENHANCEMENT
  // Check if this query needs context from previous conversation
  const originalQuery = queryValue;
  let contextUsed = false;
  let contextProducts = [];

  // 🎯 ACCESSORIES: Use pre-captured products from suggestion click if available
  if (window._pendingAccessoryProducts && queryValue.toLowerCase().includes('accessor')) {
    const pending = window._pendingAccessoryProducts;
    window._pendingAccessoryProducts = null; // consume it
    queryValue = `Find accessories for these specific products: ${pending.names.join(', ')}. Product IDs: ${pending.ids.join(', ')}. Original query: ${originalQuery}`;
    contextUsed = true;
    console.log('🎯 Using pre-captured accessory products:', pending.ids);
  } else if (window.conversationContext && window.conversationContext.isContextAwareQuery(queryValue)) {
    // Get the actual products from context
    contextProducts = window.conversationContext.getLastProducts(10);
    const recentDisplayed = window.conversationContext.getRecentDisplayedProducts();
    
    // Use recent displayed products if available (more reliable)
    if (recentDisplayed.length > 0) {
      contextProducts = recentDisplayed;
    }
    
    if (contextProducts.length > 0) {
      // Create more explicit context for the backend
      const productNames = contextProducts.map(p => p.product_name).filter(name => name);
      const productIds = contextProducts.map(p => p.product_id).filter(id => id);
      
      // For accessory queries, be very explicit
      if (queryValue.toLowerCase().includes('accessor')) {
        queryValue = `Find accessories for these specific products: ${productNames.join(', ')}. Product IDs: ${productIds.join(', ')}. Original query: ${originalQuery}`;
      } else {
        queryValue = window.conversationContext.enhanceQueryWithContext(queryValue);
      }
      
      contextUsed = true;
      console.log('🎯 Context-enhanced query:', {
        original: originalQuery,
        enhanced: queryValue,
        products: contextProducts.map(p => `${p.product_name} (${p.product_id})`)
      });
      
      // Show context indicator in UI
      showContextIndicator(originalQuery);
    }
  }

  // Check if authentication is required for this query
  if (checkAuthenticationRequired(queryValue)) {
    appendMessage(originalQuery, "user");
    queryInput.value = "";
    showLoginForm("Please login to access orders or add items to cart");
    return;
  }

  appendMessage(originalQuery, "user");
  queryInput.value = "";
  showTypingIndicator();

  try {
    // Use logged-in user's email if available, otherwise empty string for anonymous
    const customerEmail = isLoggedIn ? currentUser.email : "";
    
    // 🧠 ENHANCED: Include conversation context in the request
    const requestBody = { 
      query: queryValue, 
      customer_id: customerEmail 
    };
    
    // If this is a context-aware query, include the actual product context
    if (contextUsed && window.conversationContext && contextProducts.length > 0) {
      const lastProducts = window.conversationContext.getLastProducts(10);
      const recentDisplayed = window.conversationContext.getRecentDisplayedProducts();
      
      requestBody.conversation_context = {
        last_products: lastProducts,
        recent_displayed_products: recentDisplayed,
        current_context_products: contextProducts, // Most immediate context
        original_query: originalQuery,
        enhanced_query: queryValue,
        context_type: originalQuery.toLowerCase().includes('accessories') ? 'accessories_search' : 'general_context'
      };
      
      // 🧠 SIMPLE BACKUP: Also include direct product IDs in a simple format (cleaned)
      requestBody.product_context_ids = contextProducts.map(p => (p.product_id || '').trim()).filter(id => id);
      requestBody.product_context_names = contextProducts.map(p => (p.product_name || '').trim()).filter(name => name);
      
      console.log('🧠 Sending conversation context to backend:', requestBody.conversation_context);
      console.log('🧠 Simple product IDs:', requestBody.product_context_ids);
      console.log('🧠 Simple product names:', requestBody.product_context_names);
    }
    
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });

    const data = await response.json();
    removeTypingIndicator();
    
    // Debug log to see what we're getting
    console.log('Response data:', data);
    
    // 🧠 SAVE TO CONVERSATION CONTEXT
    if (window.conversationContext) {
      window.conversationContext.addConversation(originalQuery, data, {
        response_type: data.response_type,
        products_count: data.products_data?.length || 0,
        enhanced_query: queryValue !== originalQuery ? queryValue : null
      });
    }
    
    // Use the new function to handle different response types
    appendBotMessage(data);
    
  } catch (error) {
    console.error("Error:", error);
    removeTypingIndicator();
    appendMessage("Error processing your query. Please try again.", "bot");
  }
}

// Make submitQuery globally accessible
window.submitQuery = submitQuery;

function appendBotMessage(data) {
  const chatBox = document.getElementById("chat-box");
  const messageDiv = document.createElement("div");
  messageDiv.className = "flex justify-start animate-slide-up";
  
  let messageContent = '';
  
  // Debug log to understand the structure
  console.log('appendBotMessage received data:', data);
  console.log('Data type:', typeof data);
  
  // Handle if data is just a string
  if (typeof data === 'string') {
    messageContent = data;
  } 
  // Handle if data is an object but might be empty or malformed
  else if (typeof data === 'object' && data !== null) {
    // Debug log
    console.log('Processing object with response_type:', data.response_type);
    console.log('Keys in data object:', Object.keys(data));
    
    // Check for specific response types
    if (data.response_type === 'product' && data.product_data) {
      // Single product response - show detailed product view
      console.log('🔍 DEBUG: Product data received:', data.product_data);
      
      let productDetailView = createDetailedProductView(data.product_data, data.ai_response);
      if (productDetailView) {
        console.log('Rendering detailed product view');
        
        // Cross-sell section removed from product detail page
        // Cross-sell products now only display below chat window via A2UI
        
        messageContent = productDetailView;
      } else {
        messageContent = data.ai_response || 'Sorry, I could not find any matching products.';
      }
    } else if (data.response_type === 'products_list' && data.products_data && data.products_data.length > 0) {
      // Multiple products response - show product carousel
      const productCarousel = createProductCarousel(data.products_data);
      if (productCarousel) {
        console.log('Rendering products carousel');
        messageContent = productCarousel;
        
        // 🤖 ADD AI SUGGESTIONS: Render intelligent suggestions after product carousel
        if (data.ai_suggestions && data.ai_suggestions.has_suggestions) {
          const suggestionsPanel = createAISuggestionsPanel(data.ai_suggestions);
          if (suggestionsPanel) {
            messageContent += suggestionsPanel;
            console.log('✅ Added AI suggestions panel with', data.ai_suggestions.suggestions.length, 'suggestions');
          }
        }
        
        // Store products in conversation context
        if (window.conversationContext) {
          const productContext = {
            products: data.products_data.map(product => ({
              product_id: (product.product_id || '').trim(),
              product_name: (product.product_name || '').trim(),
              price: product.price,
              image_url: product.image_url,
              summary: product.summary
            })),
            timestamp: new Date().toISOString(),
            search_type: 'products_list'
          };
          
          window.conversationContext.storeDisplayedProducts(productContext);
          console.log('🧠 Stored displayed products in context:', productContext.products.length);
        }
      } else {
        messageContent = data.ai_response || 'Sorry, I could not find any matching products.';
      }
    } else if (data.response_type === 'visual_search') {
      const visualContent = createVisualSearchResponse(data);
      if (visualContent) {
        console.log('Rendering visual search response');
        messageContent = visualContent;
      } else {
        messageContent = data.ai_response || data.message || 'Visual search processed.';
      }

      if (window.conversationContext && Array.isArray(data.products_data) && data.products_data.length > 0) {
        const productContext = {
          products: data.products_data.map(product => ({
            product_id: (product.product_id || '').trim(),
            product_name: (product.product_name || '').trim(),
            price: product.price,
            image_url: product.image_url,
            summary: product.summary
          })),
          timestamp: new Date().toISOString(),
          search_type: 'visual_search'
        };

        window.conversationContext.storeDisplayedProducts(productContext);
        console.log('🧠 Stored visual search products in context:', productContext.products.length);
      }
    } else if (data.response_type === 'conversation' && data.ai_response) {
      // Conversation response - show AI's conversational response
      console.log('Rendering conversation response');
      messageContent = data.ai_response;
    } else if (data.response_type === 'order' && data.order_data) {
      // Single order response
      messageContent = data.ai_response || 'Order information:';
      if (data.order_data.product_data) {
        messageContent += createProductCarousel([data.order_data.product_data]);
      }
    } else if (data.response_type === 'order_history' && data.orders_data) {
      // Order history response - display orders in beautiful table
      messageContent = `
        <div class="mb-4">
          <h3 class="text-2xl font-bold text-gray-800 mb-4">
            <i class="fas fa-shopping-bag text-purple-600 mr-2"></i>
            Your Order History 
            <span class="text-sm font-normal text-gray-500">(${data.orders_data.length} orders)</span>
          </h3>
        </div>
        
        <div class="overflow-x-auto rounded-lg shadow-lg">
          <table class="min-w-full bg-white border border-gray-200">
            <thead class="bg-gradient-to-r from-purple-600 to-indigo-600 text-white">
              <tr>
                <th class="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider">Order ID</th>
                <th class="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider">Product</th>
                <th class="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider">Image</th>
                <th class="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider">Order Date</th>
                <th class="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider">Status</th>
                <th class="px-6 py-4 text-left text-xs font-semibold uppercase tracking-wider">Price</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
      `;
      
      data.orders_data.forEach((order, index) => {
        const imageUrl = order.image_url || 'https://via.placeholder.com/80';
        const productName = order.product_name || 'Unknown Product';
        const price = order.total_price ? `£${parseFloat(order.total_price).toFixed(2)}` : 'N/A';
        const orderDate = order.order_date ? new Date(order.order_date).toLocaleDateString('en-GB', {
          day: '2-digit',
          month: 'short',
          year: 'numeric'
        }) : 'N/A';
        const orderStatus = order.order_status || 'N/A';
        const orderId = order.order_id || 'N/A';
        
        // Status badge colors
        let statusColor = 'bg-gray-100 text-gray-800';
        if (orderStatus.toLowerCase() === 'open') statusColor = 'bg-blue-100 text-blue-800';
        else if (orderStatus.toLowerCase() === 'approved') statusColor = 'bg-green-100 text-green-800';
        else if (orderStatus.toLowerCase() === 'ready') statusColor = 'bg-yellow-100 text-yellow-800';
        else if (orderStatus.toLowerCase() === 'shipped') statusColor = 'bg-indigo-100 text-indigo-800';
        else if (orderStatus.toLowerCase() === 'delivered') statusColor = 'bg-green-100 text-green-800';
        
        // Alternating row colors
        const rowBg = index % 2 === 0 ? 'bg-white' : 'bg-gray-50';
        
        messageContent += `
          <tr class="${rowBg} hover:bg-purple-50 transition-colors duration-150">
            <td class="px-6 py-4 whitespace-nowrap">
              <div class="text-sm font-bold text-purple-600">#${orderId}</div>
            </td>
            <td class="px-6 py-4">
              <div class="text-sm font-medium text-gray-900 max-w-xs">${productName}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <img src="${imageUrl}" alt="${productName}" 
                   class="h-16 w-16 object-cover rounded-lg shadow-sm border border-gray-200"
                   onerror="this.src='https://via.placeholder.com/80'">
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <div class="text-sm text-gray-900">
                <i class="far fa-calendar text-gray-400 mr-1"></i>
                ${orderDate}
              </div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <span class="px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${statusColor}">
                ${orderStatus}
              </span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
              <div class="text-lg font-bold text-green-600">${price}</div>
            </td>
          </tr>
        `;
      });
      
      messageContent += `
            </tbody>
          </table>
        </div>
        
        <div class="mt-4 text-sm text-gray-500 italic">
          <i class="fas fa-info-circle mr-1"></i>
          Showing all ${data.orders_data.length} orders from your purchase history
        </div>
      `;
    } else if (data.success !== undefined || data.error !== undefined || data.message !== undefined) {
      // Handle tool responses with success/error/message
      if (data.success && data.message) {
        messageContent = data.message;
      } else if (data.error) {
        messageContent = `<div class="text-red-600"><i class="fas fa-exclamation-circle mr-2"></i>${data.error}</div>`;
      } else if (data.message) {
        messageContent = data.message;
      } else {
        messageContent = data.response || data.ai_response || 'Request processed.';
      }
    } 
    // Handle responses with just ai_response or response fields
    else if (data.ai_response) {
      messageContent = data.ai_response;
    } else if (data.response) {
      messageContent = data.response;
    }
    // Handle any other object structure - try to extract text
    else {
      console.warn('Unknown object structure:', data);
      // Try to find any text content in the object
      const textFields = ['message', 'text', 'content', 'result'];
      let foundText = '';
      
      for (const field of textFields) {
        if (data[field] && typeof data[field] === 'string') {
          foundText = data[field];
          break;
        }
      }
      
      if (foundText) {
        messageContent = foundText;
      } else {
        // Last resort: convert object to readable format
        try {
          messageContent = JSON.stringify(data, null, 2);
        } catch {
          messageContent = 'Sorry, I received an unexpected response format.';
        }
      }
    }
  } else {
    // Handle null, undefined, or other unexpected types
    console.warn('Unexpected data type or null data:', data);
    messageContent = 'Sorry, I couldn\'t process that request properly.';
  }
  
  // Ensure messageContent is not empty
  if (!messageContent || messageContent.trim() === '') {
    messageContent = 'Sorry, I couldn\'t provide a response to that request.';
  }
  
  messageDiv.innerHTML = `
    <div class="chat-bubble-bot p-4 max-w-4xl shadow-lg">
      <div class="flex items-start space-x-3">
        <div class="w-8 h-8 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full flex items-center justify-center flex-shrink-0">
          <i class="fas fa-robot text-white text-sm"></i>
        </div>
        <div class="flex-1">
          ${messageContent}
        </div>
      </div>
    </div>
  `;
  
  chatBox.appendChild(messageDiv);
  chatBox.scrollTop = chatBox.scrollHeight;
  
  // 🔗 TRIGGER A2UI CROSS-SELL for product responses
  if (data && data.response_type === 'product' && data.product_data && data.product_data.product_id) {
    const productId = data.product_data.product_id;
    console.log('🎯 Product displayed! Triggering A2UI cross-sell for product:', productId);
    
    // Call loadCrossSellViaA2UI after a short delay to ensure DOM is ready
    setTimeout(() => {
      if (typeof loadCrossSellViaA2UI === 'function') {
        console.log('✅ Calling loadCrossSellViaA2UI for product:', productId);
        loadCrossSellViaA2UI(productId);
      } else {
        console.error('❌ loadCrossSellViaA2UI function not found!');
      }
    }, 100);
  }
  
  // Check if this is a cart display message and trigger cart rendering
  if (data && (data.show_cart || data.trigger_cart_render)) {
    console.log('🛒 Cart display detected! Triggering renderChatCart');
    // Use multiple methods to ensure it executes
    // Method 1: Immediate call after DOM update
    setTimeout(() => {
      if (typeof renderChatCart === 'function') {
        console.log('✅ Calling renderChatCart (Method 1)');
        renderChatCart();
      }
    }, 50);
    
    // Method 2: Backup call with longer delay
    setTimeout(() => {
      if (typeof renderChatCart === 'function') {
        console.log('🔄 Backup call to renderChatCart (Method 2)');
        renderChatCart();
      }
    }, 150);
  }
}

/**
 * Visual Search Upload Functions
 * Note: Event listeners are now set up in voice-search.js where the buttons are created
 */

// Make handleVisualSearchFile globally accessible for voice-search.js
window.handleVisualSearchFile = function(file) {
  if (!file) {
    return;
  }

  if (!file.type || !file.type.startsWith('image/')) {
    appendBotMessage({
      response_type: 'visual_search',
      success: false,
      error: 'Please select a valid image file to start a visual search.'
    });
    return;
  }

  const maxSizeBytes = 4 * 1024 * 1024; // 4MB limit to match backend validation
  if (file.size > maxSizeBytes) {
    appendBotMessage({
      response_type: 'visual_search',
      success: false,
      error: 'Image too large. Please choose a photo under 4MB for analysis.'
    });
    return;
  }

  const reader = new FileReader();
  reader.onload = event => {
    const previewUrl = typeof event.target.result === 'string' ? event.target.result : '';
    lastVisualSearchPreview = previewUrl;
    appendImageUploadMessage(previewUrl, file.name);
    performVisualSearchRequest(file, previewUrl);
  };

  reader.onerror = () => {
    console.error('Failed to read image for visual search');
    appendBotMessage({
      response_type: 'visual_search',
      success: false,
      error: 'Unable to read the selected image. Please try another file.'
    });
  };

  reader.readAsDataURL(file);
}

function appendImageUploadMessage(previewUrl, fileName) {
  const chatBox = document.getElementById('chat-box');
  if (!chatBox) {
    return;
  }

  const messageDiv = document.createElement('div');
  messageDiv.className = 'flex justify-end animate-slide-up';

  const safeName = fileName ? escapeHtml(fileName) : 'Uploaded image';
  const previewHtml = previewUrl
    ? `<img src="${escapeHtml(previewUrl)}" alt="${safeName}" class="w-40 h-40 object-cover rounded-2xl border border-white/60 shadow-md" loading="lazy"/>`
    : '';

  messageDiv.innerHTML = `
    <div class="chat-bubble-user p-4 max-w-md shadow-lg">
      <div class="space-y-3">
        <div class="flex items-center justify-between gap-3">
          <span class="text-sm font-medium text-white/90">Image uploaded</span>
          <span class="text-xs text-white/70 truncate max-w-xs">${safeName}</span>
        </div>
        ${previewHtml}
        <div class="text-xs text-white/80">Analyzing your photo for similar products...</div>
      </div>
    </div>
  `;

  chatBox.appendChild(messageDiv);
  chatBox.scrollTop = chatBox.scrollHeight;
}

async function performVisualSearchRequest(file, previewUrl) {
  if (!file) {
    return;
  }

  if (isVisualSearchInProgress) {
    showNotification('Image search already running. Please wait for the results.', 'info');
    return;
  }

  isVisualSearchInProgress = true;
  showTypingIndicator();

  const formData = new FormData();
  formData.append('image', file, file.name || 'upload.jpg');

  if (isLoggedIn && currentUser && currentUser.email) {
    formData.append('customer_id', currentUser.email);
  }

  if (navigator.language) {
    formData.append('device_locale', navigator.language);
  }

  try {
    const response = await fetch('/api/visual-search', {
      method: 'POST',
      body: formData
    });

    let responseData = null;
    try {
      responseData = await response.json();
    } catch (parseError) {
      console.error('Visual search response parse error:', parseError);
      responseData = {
        response_type: 'visual_search',
        success: false,
        error: 'Unexpected server response while processing the image.'
      };
    }

    if (!responseData || typeof responseData !== 'object') {
      responseData = {
        response_type: 'visual_search',
        success: false,
        error: 'Empty response received from the visual search service.'
      };
    }

    if (!responseData.response_type) {
      responseData.response_type = 'visual_search';
    }

    if (!response.ok || responseData.success === false) {
      const errorMessage = responseData.error || 'Image search failed. Please try again.';
      appendBotMessage({
        response_type: 'visual_search',
        success: false,
        error: errorMessage,
        image_preview: previewUrl,
        image_name: file.name
      });
      return;
    }

    responseData.image_preview = previewUrl || lastVisualSearchPreview;
    responseData.image_name = file.name;
    if (responseData.success === undefined) {
      responseData.success = true;
    }

    appendBotMessage(responseData);
  } catch (error) {
    console.error('Visual search request failed:', error);
    appendBotMessage({
      response_type: 'visual_search',
      success: false,
      error: 'Unable to complete visual search. Please check your connection and try again.',
      image_preview: previewUrl,
      image_name: file.name
    });
  } finally {
    removeTypingIndicator();
    isVisualSearchInProgress = false;
    lastVisualSearchPreview = null;
  }
}

/**
 * Best Selling Products Functions
 */
async function loadBestSellingProducts() {
  try {
    // Show loading state with animation
    const carousel = document.getElementById("best-selling-carousel");
    const sectionTitle = document.querySelector('.best-selling-section-title');
    const sectionSubtitle = document.querySelector('.best-selling-section-subtitle');
    
    // If user is logged in, show personalized loading
    const isPersonalizedLoad = isLoggedIn && currentUser;
    
    if (isPersonalizedLoad) {
      // Show loading state for personalized recommendations
      showRecommendationLoading(carousel, sectionTitle, sectionSubtitle);
    }
    
    const customerParam = isPersonalizedLoad ? `&customer_id=${encodeURIComponent(currentUser.email)}` : '';
    console.log('🛍️ Loading products. Logged in:', isLoggedIn, 'Customer:', currentUser?.email);
    console.log('🔗 API URL:', `/api/best-selling-products?pageSize=8${customerParam}`);
    
    const response = await fetch(`/api/best-selling-products?pageSize=8${customerParam}`);
    const data = await response.json();
    console.log('📦 Products API response:', data);
    console.log('🎯 Personalized flag:', data.personalized);
    console.log('📊 Source:', data.source);
    console.log('🔢 Product count:', data.products?.length);
    
    if (data.error) {
      console.error("Error loading best selling products:", data.error);
      displayBestSellingError("Failed to load best selling products. Please try again later.");
      return;
    }
    
    if (data.products && data.products.length > 0) {
      console.log('✅ Calling displayBestSellingProducts with personalized:', data.personalized);
      // Add a small delay to show loading animation
      setTimeout(() => {
        displayBestSellingProducts(data.products, data.personalized);
      }, isPersonalizedLoad && data.personalized ? 1200 : 300);
    } else {
      displayBestSellingError("No best selling products available at the moment.");
    }
    
  } catch (error) {
    console.error("Error fetching best selling products:", error);
    displayBestSellingError("Failed to load best selling products. Please check your connection.");
  }
}

/**
 * Show loading animation for personalized recommendations
 */
function showRecommendationLoading(carousel, sectionTitle, sectionSubtitle) {
  // Update header with animated heart
  if (sectionTitle) {
    sectionTitle.innerHTML = `
      <i class="fas fa-heart text-pink-500 heart-beat"></i> Analyzing Your Preferences
    `;
    sectionTitle.classList.add('section-transition');
  }
  if (sectionSubtitle) {
    sectionSubtitle.innerHTML = `
      <div class="flex items-center justify-center space-x-1">
        <span>Finding perfect matches</span>
        <span class="dot-pulse inline-block w-1.5 h-1.5 bg-pink-500 rounded-full mx-0.5"></span>
        <span class="dot-pulse inline-block w-1.5 h-1.5 bg-pink-500 rounded-full mx-0.5"></span>
        <span class="dot-pulse inline-block w-1.5 h-1.5 bg-pink-500 rounded-full mx-0.5"></span>
      </div>
    `;
  }
  
  // Show loading skeleton with progress bar
  carousel.innerHTML = `
    <div class="space-y-4">
      <!-- Progress Bar -->
      <div class="bg-gray-200 rounded-full h-2 overflow-hidden mb-6">
        <div class="loading-progress-bar h-full bg-gradient-to-r from-pink-500 via-purple-500 to-pink-500"></div>
      </div>
      
      <!-- Loading Skeletons -->
      ${[...Array(4)].map((_, i) => `
        <div class="flex items-center space-x-4 p-4 bg-white rounded-xl shadow-sm" style="animation-delay: ${i * 0.1}s">
          <div class="w-20 h-20 recommendation-skeleton rounded-lg"></div>
          <div class="flex-1 space-y-3">
            <div class="h-4 recommendation-skeleton rounded w-3/4"></div>
            <div class="h-3 recommendation-skeleton rounded w-1/2"></div>
            <div class="h-4 recommendation-skeleton rounded w-1/4"></div>
          </div>
        </div>
      `).join('')}
      
      <!-- Fun Loading Message -->
      <div class="text-center py-4 fade-in-scale">
        <div class="inline-flex items-center space-x-2 text-sm text-gray-600">
          <i class="fas fa-sparkles text-pink-500 animate-pulse"></i>
          <span>AI is crafting your personalized selection...</span>
          <i class="fas fa-sparkles text-purple-500 animate-pulse"></i>
        </div>
      </div>
    </div>
  `;
}

function displayBestSellingProducts(products, isPersonalized = false) {
  console.log('🎨 displayBestSellingProducts called with:', products.length, 'products, personalized:', isPersonalized);
  
  const carousel = document.getElementById("best-selling-carousel");
  
  // Update section header if personalized
  const sectionTitle = document.querySelector('.best-selling-section-title');
  const sectionSubtitle = document.querySelector('.best-selling-section-subtitle');
  
  console.log('🔍 Section elements found - Title:', !!sectionTitle, 'Subtitle:', !!sectionSubtitle);
  
  if (sectionTitle) {
    if (isPersonalized) {
      console.log('✅ Setting PERSONALIZED header');
      sectionTitle.innerHTML = `
        <i class="fas fa-heart text-pink-500 heart-beat"></i> Recommended for You
      `;
      sectionTitle.classList.add('section-transition');
      if (sectionSubtitle) {
        sectionSubtitle.innerHTML = `
          <span class="fade-in-scale">Based on your purchase history</span>
        `;
      }
    } else {
      console.log('📊 Setting TRENDING header');
      sectionTitle.innerHTML = `
        <i class="fas fa-fire text-orange-500"></i> Trending Now
      `;
      if (sectionSubtitle) {
        sectionSubtitle.textContent = 'Our most popular products';
      }
    }
  } else {
    console.error('❌ Section title element not found!');
  }
  
  // Create products with animation class
  const productsHtml = products.map((product, index) => {
    const productCard = createProductCard(product, true);
    // Wrap each product card with animation class
    return `<div class="product-card-animated" style="animation-delay: ${index * 0.1}s">${productCard}</div>`;
  }).join('');
  
  carousel.innerHTML = productsHtml;
  
  // Show navigation controls if there are many products
  const container = document.getElementById("best-selling-carousel-container");
  const navControls = container.querySelector(".carousel-nav-controls");
  
  if (products.length > 4) {
    navControls?.classList.remove('hidden');
  } else {
    navControls?.classList.add('hidden');
  }
}

function displayBestSellingError(message) {
  const carousel = document.getElementById("best-selling-carousel");
  carousel.innerHTML = `
    <div class="flex flex-col items-center justify-center py-12 text-center">
      <div class="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mb-4">
        <i class="fas fa-exclamation-triangle text-red-500 text-xl"></i>
      </div>
      <p class="text-gray-600 text-sm">${message}</p>
      <button 
        onclick="loadBestSellingProducts()" 
        class="mt-3 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white px-4 py-2 rounded-full text-sm transition-all duration-300"
      >
        Try Again
      </button>
    </div>
  `;
  
  // Hide navigation controls when there's an error
  const container = document.getElementById("best-selling-carousel-container");
  const navControls = container.querySelector(".carousel-nav-controls");
  navControls?.classList.add('hidden');
}

/**
 * Cart Management Functions
 */
function clearCartOnPageLoad() {
  // Load cart from sessionStorage instead of clearing it
  console.log('🛒 Loading cart from storage...');
  loadCartFromStorage();
}

function loadCartFromStorage() {
  try {
    const savedCart = sessionStorage.getItem('shoppingCart');
    if (savedCart) {
      const parsed = JSON.parse(savedCart);
      cartItems = parsed.items || [];
      cartCount = parsed.count || 0;
      cartTotal = parsed.total || 0;
      console.log('✅ Cart loaded from storage:', { cartCount, cartTotal });
    } else {
      cartItems = [];
      cartCount = 0;
      cartTotal = 0;
      console.log('🛒 No saved cart found - starting with empty cart');
    }
    updateCartDisplay();
  } catch (error) {
    console.error('❌ Error loading cart from storage:', error);
    cartItems = [];
    cartCount = 0;
    cartTotal = 0;
    updateCartDisplay();
  }
}

function saveCartToStorage() {
  try {
    const cartData = {
      items: cartItems,
      count: cartCount,
      total: cartTotal
    };
    sessionStorage.setItem('shoppingCart', JSON.stringify(cartData));
    console.log('✅ Cart saved to storage:', { cartCount, cartTotal });
  } catch (error) {
    console.error('❌ Error saving cart to storage:', error);
  }
}

async function addToCart(productId, productName, event, showMessages = true) {
  // Prevent the card click event from firing only if event is provided
  if (event) {
    event.stopPropagation();
  }
  
  // Check if user is logged in
  if (!isLoggedIn) {
    showLoginForm("Please login to add items to your cart");
    return;
  }
  
  // Get the customer email (from logged-in user)
  const customerEmail = currentUser.email;
  
  // Get the button that was clicked (only if event is provided)
  const button = event ? event.target.closest('button') : null;
  const originalHTML = button ? button.innerHTML : null;
  
  // Show loading state (only if button exists)
  if (button) {
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
    button.classList.add("opacity-75");
  }
  
  try {
    // Get product details first
    const response = await fetch("/api/add-to-cart", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        product_id: productId,
        quantity: 1,
        customer_id: customerEmail 
      }),
    });

    const data = await response.json();
    
    if (data.error) {
      throw new Error(data.error);
    }
    
    if (data.success && data.product_details) {
      // Add to local cart
      addProductToCart(data.product_details);
      
      // Show success state (only if button exists)
      if (button) {
        button.innerHTML = '<i class="fas fa-check"></i>';
        button.classList.remove("opacity-75");
        button.classList.add("bg-gradient-to-r", "from-green-500", "to-emerald-600");
      }
      
      // Show success notification (only if showMessages is true)
      if (showMessages) {
        showNotification(`${productName} added to cart!`, "success");
      }
      
      // Show brief cart animation
      animateCartIcon();

      // 👗 Trigger "Complete the Look" outfit builder via A2UI
      if (typeof loadOutfitBuilderViaA2UI === 'function') {
        loadOutfitBuilderViaA2UI(productId, productName);
      }

      // ✨ Trigger AI Personal Stylist invitation
      triggerStylistInvitation(productId, productName, data.product_details?.price || 0);
      
    } else {
      throw new Error(data.message || "Failed to add product to cart");
    }
    
    // Reset button after 2 seconds (only if button exists)
    if (button) {
      setTimeout(() => {
        button.disabled = false;
        button.innerHTML = originalHTML;
        button.classList.remove("bg-gradient-to-r", "from-green-500", "to-emerald-600", "opacity-75");
      }, 2000);
    }
    
  } catch (error) {
    console.error("Error adding to cart:", error);
    
    // Show error state (only if button exists)
    if (button) {
      button.innerHTML = '<i class="fas fa-times"></i>';
      button.classList.remove("opacity-75");
      button.classList.add("bg-gradient-to-r", "from-red-500", "to-rose-600");
    }
    
    // Show error notification (only if showMessages is true)
    if (showMessages) {
      showNotification("Failed to add item to cart. Please try again.", "error");
    }
    
    // Reset button after 2 seconds (only if button exists)
    if (button) {
      setTimeout(() => {
        button.disabled = false;
        button.innerHTML = originalHTML;
        button.classList.remove("bg-gradient-to-r", "from-red-500", "to-rose-600");
      }, 2000);
    }
    
    throw error; // Re-throw for the detailed cart function to handle
  }
}

function addProductToCart(productDetails) {
  // Check if product already exists in cart
  const existingItem = cartItems.find(item => item.product_id === productDetails.product_id);
  
  if (existingItem) {
    existingItem.quantity += productDetails.quantity;
  } else {
    cartItems.push({
      ...productDetails,
      addedAt: new Date().toISOString()
    });
  }
  
  // Mark that user had items in cart (for page refresh notification)
  try {
    sessionStorage.setItem('hadCartItems', 'true');
  } catch (error) {
    console.error('Error setting cart flag:', error);
  }
  
  saveCartToStorage();
  updateCartDisplay();
}

function removeFromCart(productId) {
  cartItems = cartItems.filter(item => item.product_id !== productId);
  saveCartToStorage();
  updateCartDisplay();
  showNotification("Item removed from cart", "info");
}

function updateQuantity(productId, newQuantity) {
  const item = cartItems.find(item => item.product_id === productId);
  if (item) {
    if (newQuantity <= 0) {
      removeFromCart(productId);
    } else {
      item.quantity = newQuantity;
      saveCartToStorage();
      updateCartDisplay();
    }
  }
}

function updateCartDisplay() {
  // Update cart count and total
  cartCount = cartItems.reduce((total, item) => total + item.quantity, 0);
  cartTotal = cartItems.reduce((total, item) => total + (item.price * item.quantity), 0);
  
  // Update cart badge
  const cartBadge = document.getElementById("cart-badge");
  const cartTotalElement = document.getElementById("cart-total");
  const cartFooter = document.getElementById("cart-footer");
  const emptyCart = document.getElementById("empty-cart");
  const cartItemsContainer = document.getElementById("cart-items");
  
  if (cartCount > 0) {
    cartBadge.textContent = cartCount;
    cartBadge.classList.remove("hidden");
    cartTotalElement.textContent = `£${cartTotal.toFixed(2)}`;
    cartFooter.classList.remove("hidden");
    emptyCart.style.display = "none";
  } else {
    cartBadge.classList.add("hidden");
    cartFooter.classList.add("hidden");
    emptyCart.style.display = "block";
  }
  
  // Update cart items display
  renderCartItems();
}

function renderCartItems() {
  const cartItemsContainer = document.getElementById("cart-items");
  const emptyCart = document.getElementById("empty-cart");
  
  if (cartItems.length === 0) {
    emptyCart.style.display = "block";
    return;
  }
  
  emptyCart.style.display = "none";
  
  const itemsHTML = cartItems.map(item => `
    <div class="flex items-center space-x-3 p-3 border-b border-gray-100 hover:bg-gray-50 transition-colors">
      <img src="${item.image_url}" alt="${item.product_name}" class="w-12 h-12 object-cover rounded-lg flex-shrink-0" onerror="this.style.display='none'">
      <div class="flex-1 min-w-0">
        <h4 class="text-sm font-medium text-gray-800 truncate">${item.product_name}</h4>
        <p class="text-xs text-gray-500">£${item.price.toFixed(2)} each</p>
        <div class="flex items-center space-x-2 mt-1">
          <button onclick="updateQuantity('${item.product_id}', ${item.quantity - 1})" class="w-6 h-6 bg-gray-200 hover:bg-gray-300 rounded-full flex items-center justify-center text-xs transition-colors">
            <i class="fas fa-minus"></i>
          </button>
          <span class="text-sm font-medium px-2">${item.quantity}</span>
          <button onclick="updateQuantity('${item.product_id}', ${item.quantity + 1})" class="w-6 h-6 bg-gray-200 hover:bg-gray-300 rounded-full flex items-center justify-center text-xs transition-colors">
            <i class="fas fa-plus"></i>
          </button>
        </div>
      </div>
      <div class="text-right">
        <p class="text-sm font-bold text-purple-600">£${(item.price * item.quantity).toFixed(2)}</p>
        <button onclick="removeFromCart('${item.product_id}')" class="text-xs text-red-500 hover:text-red-700 transition-colors mt-1">
          <i class="fas fa-trash"></i> Remove
        </button>
      </div>
    </div>
  `).join('');
  
  // Replace empty cart with items, but keep the empty cart div for later
  const existingItems = cartItemsContainer.querySelector('.cart-items-list');
  if (existingItems) {
    existingItems.innerHTML = itemsHTML;
  } else {
    const itemsList = document.createElement('div');
    itemsList.className = 'cart-items-list';
    itemsList.innerHTML = itemsHTML;
    cartItemsContainer.appendChild(itemsList);
  }
}

function toggleMiniCart() {
  const dropdown = document.getElementById("mini-cart-dropdown");
  const isHidden = dropdown.classList.contains("hidden");
  
  if (isHidden) {
    dropdown.classList.remove("hidden");
    setTimeout(() => {
      dropdown.classList.remove("opacity-0", "translate-y-2");
    }, 10);
  } else {
    closeMiniCart();
  }
}

function closeMiniCart() {
  const dropdown = document.getElementById("mini-cart-dropdown");
  dropdown.classList.add("opacity-0", "translate-y-2");
  setTimeout(() => {
    dropdown.classList.add("hidden");
  }, 300);
}

function clearCart() {
  if (cartItems.length === 0) return;
  
  if (confirm("Are you sure you want to clear your cart?")) {
    cartItems = [];
    cartCount = 0;
    cartTotal = 0;
    
    // Clear from all storage
    try {
      sessionStorage.removeItem('shoppingCart');
      sessionStorage.removeItem('tempCart');
    } catch (error) {
      console.error('Error clearing cart storage:', error);
    }
    
    updateCartDisplay();
    showNotification("Cart cleared successfully", "info");
  }
}

function viewFullCart() {
  closeMiniCart();
  
  if (cartItems.length === 0) {
    showNotification("Your cart is empty", "info");
    return;
  }
  
  // Use the chatbot's smart cart display
  const queryInput = document.getElementById("query");
  queryInput.value = "Show my cart";
  
  // Submit the query to get the agent's smart cart display
  submitQuery();
}

function animateCartIcon() {
  const cartBtn = document.getElementById("mini-cart-btn");
  cartBtn.classList.add("animate-bounce");
  setTimeout(() => {
    cartBtn.classList.remove("animate-bounce");
  }, 1000);
}

function displayCartInChat() {
  console.log('🛒 ========================================');
  console.log('🛒 displayCartInChat CALLED');
  console.log('🛒 ========================================');
  console.log('🛒 Cart state:', { 
    cartCount, 
    cartItemsLength: cartItems.length, 
    cartTotal,
    cartItems: JSON.stringify(cartItems)
  });
  
  // Update cart display in chat interface
  const cartCountDisplay = document.getElementById('cart-display-count');
  const cartItemsDisplay = document.getElementById('cart-display-items');
  const cartTotalDisplay = document.getElementById('cart-total-display');
  
  console.log('🔍 Looking for DOM elements...');
  console.log('   - cart-display-count:', !!cartCountDisplay);
  console.log('   - cart-display-items:', !!cartItemsDisplay);
  console.log('   - cart-total-display:', !!cartTotalDisplay);
  
  if (!cartCountDisplay || !cartItemsDisplay || !cartTotalDisplay) {
    console.log('⚠️ Cart display elements not found in DOM yet');
    return;
  }
  
  console.log('✅ All DOM elements found!');
  console.log('📊 Updating cart display with', cartItems.length, 'items');
  
  // Update count
  if (cartCount > 0) {
    cartCountDisplay.innerHTML = `<i class="fas fa-shopping-cart mr-1"></i>${cartCount} items`;
    console.log('✅ Updated cart count to:', cartCount);
  } else {
    cartCountDisplay.innerHTML = `<i class="fas fa-shopping-cart mr-1"></i>Empty`;
    console.log('✅ Set cart count to Empty');
  }
  
  // Update total
  cartTotalDisplay.textContent = `£${cartTotal.toFixed(2)}`;
  console.log('✅ Updated cart total to: £' + cartTotal.toFixed(2));
  
  // Update items display
  if (cartItems.length === 0) {
    console.log('📭 Cart is empty, showing empty state');
    cartItemsDisplay.innerHTML = `
      <div class='text-center py-8 text-gray-500'>
        <i class='fas fa-shopping-cart text-4xl mb-3 opacity-30'></i>
        <p class='text-lg font-medium'>Your cart is empty</p>
        <p class='text-sm text-gray-400 mt-1'>Add some products to get started!</p>
        <button onclick='document.getElementById("query").focus(); document.getElementById("query").value="show me products"' class='mt-3 bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600 text-white px-4 py-2 rounded-lg font-medium transition-all duration-300 text-sm'>
          <i class='fas fa-search mr-2'></i>Browse Products
        </button>
      </div>
    `;
    console.log('✅ Empty cart message displayed');
  } else {
    console.log(`🛍️ Displaying ${cartItems.length} cart items...`);
    const itemsHTML = cartItems.map((item, index) => {
      console.log(`   Item ${index + 1}:`, item.product_name);
      return `
      <div class='flex items-center justify-between bg-white rounded-xl p-4 shadow-sm border border-gray-100 hover:shadow-md transition-shadow'>
        <div class='flex items-center space-x-3'>
          <img src='${item.image_url}' alt='${item.product_name}' class='w-16 h-16 object-cover rounded-lg border border-gray-200' onerror="this.style.display='none'">
          <div class='flex-1'>
            <h4 class='font-semibold text-gray-800 text-sm'>${item.product_name}</h4>
            <p class='text-xs text-gray-500 mt-1'>£${item.price.toFixed(2)} each</p>
            <div class='flex items-center space-x-2 mt-2'>
              <button onclick='updateQuantityInChat("${item.product_id}", ${item.quantity - 1})' class='w-7 h-7 bg-gray-100 hover:bg-gray-200 rounded-full flex items-center justify-center text-xs transition-colors border border-gray-300'>
                <i class='fas fa-minus'></i>
              </button>
              <span class='text-sm font-medium px-3 py-1 bg-purple-100 text-purple-800 rounded-full min-w-[2rem] text-center'>${item.quantity}</span>
              <button onclick='updateQuantityInChat("${item.product_id}", ${item.quantity + 1})' class='w-7 h-7 bg-gray-100 hover:bg-gray-200 rounded-full flex items-center justify-center text-xs transition-colors border border-gray-300'>
                <i class='fas fa-plus'></i>
              </button>
            </div>
          </div>
        </div>
        <div class='text-right'>
          <p class='text-lg font-bold text-purple-600'>£${(item.price * item.quantity).toFixed(2)}</p>
          <button onclick='removeFromCartInChat("${item.product_id}")' class='text-xs text-red-500 hover:text-red-700 transition-colors mt-2 bg-red-50 hover:bg-red-100 px-2 py-1 rounded'>
            <i class='fas fa-trash mr-1'></i>Remove
          </button>
        </div>
      </div>
    `;
    }).join('');
    
    cartItemsDisplay.innerHTML = itemsHTML;
    console.log('✅ Cart items HTML updated');
  }
  
  console.log('✅ ========================================');
  console.log('✅ displayCartInChat COMPLETED SUCCESSFULLY');
  console.log('✅ ========================================');
}

// New simplified cart rendering function for chat window
function renderChatCart() {
  console.log('🛒 renderChatCart called');
  console.log('🛒 Current cart state:', { cartCount, cartItemsCount: cartItems.length, cartTotal });
  
  const countEl = document.getElementById('chat-cart-count');
  const itemsEl = document.getElementById('chat-cart-items');
  const totalEl = document.getElementById('chat-cart-total');
  
  if (!countEl || !itemsEl || !totalEl) {
    console.error('❌ Chat cart elements not found');
    return;
  }
  
  console.log('✅ Chat cart elements found');
  
  // Update count
  countEl.innerHTML = cartCount > 0 
    ? `<i class='fas fa-shopping-cart mr-1'></i>${cartCount} item${cartCount !== 1 ? 's' : ''}`
    : `<i class='fas fa-shopping-cart mr-1'></i>Empty`;
  
  // Update total
  totalEl.textContent = `£${cartTotal.toFixed(2)}`;
  
  // Update items
  if (cartItems.length === 0) {
    itemsEl.innerHTML = `
      <div class='text-center py-8 text-gray-500'>
        <i class='fas fa-shopping-cart text-4xl mb-3 opacity-30'></i>
        <p class='text-lg font-medium'>Your cart is empty</p>
        <p class='text-sm text-gray-400 mt-1'>Add some products to get started!</p>
      </div>`;
  } else {
    itemsEl.innerHTML = cartItems.map(item => `
      <div class='flex items-center justify-between bg-white rounded-xl p-4 shadow-sm border border-gray-100 hover:shadow-md transition-shadow'>
        <div class='flex items-center space-x-3 flex-1'>
          <img src='${item.image_url}' alt='${item.product_name}' class='w-16 h-16 object-cover rounded-lg border border-gray-200' onerror="this.style.display='none'">
          <div class='flex-1 min-w-0'>
            <h4 class='font-semibold text-gray-800 text-sm truncate'>${item.product_name}</h4>
            <p class='text-xs text-gray-500 mt-1'>£${item.price.toFixed(2)} each</p>
            <div class='flex items-center space-x-2 mt-2'>
              <button onclick='updateCartQuantity("${item.product_id}", ${item.quantity - 1})' class='w-7 h-7 bg-gray-100 hover:bg-gray-200 rounded-full flex items-center justify-center text-xs transition-colors border border-gray-300'>
                <i class='fas fa-minus'></i>
              </button>
              <span class='text-sm font-medium px-3 py-1 bg-purple-100 text-purple-800 rounded-full min-w-[2rem] text-center'>${item.quantity}</span>
              <button onclick='updateCartQuantity("${item.product_id}", ${item.quantity + 1})' class='w-7 h-7 bg-gray-100 hover:bg-gray-200 rounded-full flex items-center justify-center text-xs transition-colors border border-gray-300'>
                <i class='fas fa-plus'></i>
              </button>
            </div>
          </div>
        </div>
        <div class='text-right ml-4'>
          <p class='text-lg font-bold text-purple-600'>£${(item.price * item.quantity).toFixed(2)}</p>
          <button onclick='removeCartItem("${item.product_id}")' class='text-xs text-red-500 hover:text-red-700 transition-colors mt-2 bg-red-50 hover:bg-red-100 px-2 py-1 rounded'>
            <i class='fas fa-trash mr-1'></i>Remove
          </button>
        </div>
      </div>
    `).join('');
  }
  
  console.log('✅ Chat cart rendered successfully');
}

// Helper functions for chat cart
function updateCartQuantity(productId, newQuantity) {
  updateQuantity(productId, newQuantity);
  renderChatCart();
}

function removeCartItem(productId) {
  removeFromCart(productId);
  renderChatCart();
}

function updateQuantityInChat(productId, newQuantity) {
  updateQuantity(productId, newQuantity);
  // Refresh the display after a short delay
  setTimeout(displayCartInChat, 100);
}

function removeFromCartInChat(productId) {
  removeFromCart(productId);
  // Refresh the display after a short delay
  setTimeout(displayCartInChat, 100);
}

function refreshCartDisplay() {
  showNotification("Cart refreshed", "info");
  displayCartInChat();
}

// Global variable to store polling interval
let paymentPollingInterval = null;

// Global variable to track payment confirmation state
let awaitingPaymentConfirmation = false;
let pendingCheckoutData = null;

async function proceedToCheckout() {
  if (cartItems.length === 0) {
    showNotification("Your cart is empty. Add some products to proceed to checkout.", "error");
    return;
  }
  
  if (!isLoggedIn || !currentUser || !currentUser.email) {
    showLoginForm("Please login to proceed to checkout");
    console.error("Checkout failed: User not properly logged in", { isLoggedIn, currentUser });
    return;
  }
  
  // Show checkout confirmation dialog
  const totalAmount = cartTotal.toFixed(2);
  const itemCount = cartItems.length;
  
  // Set confirmation state
  awaitingPaymentConfirmation = true;
  pendingCheckoutData = {
    customer_email: currentUser.email,
    cart_items: cartItems,
    total_amount: totalAmount,
    item_count: itemCount
  };
  
  // Ask AI-driven confirmation question
  appendBotMessage({
    response: `🛒 <strong>Ready for Checkout</strong><br><br>
      <div style="background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 20px; border-radius: 15px; margin: 10px 0;">
        <div style="display: flex; align-items-center; margin-bottom: 15px;">
          <i class="fas fa-shopping-cart" style="font-size: 24px; margin-right: 10px;"></i>
          <div>
            <div style="font-size: 18px; font-weight: bold;">Order Summary</div>
            <div style="font-size: 14px; opacity: 0.9;">${itemCount} item${itemCount > 1 ? 's' : ''} • Total: £${totalAmount}</div>
          </div>
        </div>
        <div style="font-size: 14px; opacity: 0.9; margin-bottom: 15px;">
          📦 ${itemCount} item${itemCount > 1 ? 's' : ''} in your cart<br>
          💰 Total amount: £${totalAmount}<br>
          🔒 Secure PayPal payment
        </div>
        <div style="background: rgba(255,255,255,0.15); padding: 12px; border-radius: 8px; font-size: 14px; margin-top: 10px;">
          <strong>⚡ Are you sure you want to proceed with the payment?</strong><br>
          <span style="opacity: 0.9;">Please reply with "yes" to confirm, or "no" to cancel.</span>
        </div>
      </div>`
  });
  
  console.log("Awaiting payment confirmation from user");
}

// Separate function to execute PayPal checkout after confirmation
async function executePayPalCheckout(checkoutData) {
  console.log("Executing PayPal checkout for user:", checkoutData.customer_email);
  
  // Show checkout initiation message in chat
  appendBotMessage({
    response: `🛒 <strong>Processing Checkout</strong><br><br>
      <div style="background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; padding: 20px; border-radius: 15px; margin: 10px 0;">
        <div style="display: flex; align-items-center; margin-bottom: 15px;">
          <i class="fas fa-shopping-cart" style="font-size: 24px; margin-right: 10px;"></i>
          <div>
            <div style="font-size: 18px; font-weight: bold;">Processing Payment</div>
            <div style="font-size: 14px; opacity: 0.9;">${checkoutData.item_count} item${checkoutData.item_count > 1 ? 's' : ''} • Total: £${checkoutData.total_amount}</div>
          </div>
        </div>
        <div style="font-size: 14px; opacity: 0.9;">
          ✨ Opening PayPal payment gateway...<br>
          🔒 Secure payment processing<br>
          ⚡ Keep this window open to see your payment status
        </div>
      </div>`
  });
  
  try {
    // Save current chat history and context to include in session
    const chatHistory = getChatHistory();
    const conversationContext = window.conversationContext ? window.conversationContext.exportContext() : {};
    
    // Make API call for PayPal checkout
    const response = await fetch("/api/checkout", {
      method: "POST",
      headers: { 
        "Content-Type": "application/json" 
      },
      body: JSON.stringify({
        customer_id: checkoutData.customer_email,
        cart_items: checkoutData.cart_items,
        chat_history: chatHistory,
        conversation_context: conversationContext
      })
    });

    console.log("PayPal checkout API response status:", response.status);
    const result = await response.json();
    console.log("PayPal checkout API result:", result);
    
    if (result.error) {
      throw new Error(result.error);
    }
    
    if (result.success && result.approval_url && result.polling_enabled) {
      // Show success message
      showNotification("Opening PayPal in new tab...", "info");
      
      // Store session ID for polling
      const sessionId = result.session_id;
      
      // Add waiting message to chat
      appendBotMessage({
        response: `💳 <strong>PayPal Payment</strong><br><br>
          <div style="background: linear-gradient(135deg, #3b82f6, #1d4ed8); color: white; padding: 20px; border-radius: 15px; margin: 10px 0;">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
              <i class="fas fa-credit-card" style="font-size: 24px; margin-right: 10px;"></i>
              <div>
                <div style="font-size: 18px; font-weight: bold;">Secure Payment Processing</div>
                <div style="font-size: 14px; opacity: 0.9;">Total: £${checkoutData.total_amount}</div>
              </div>
            </div>
            <div style="font-size: 14px; opacity: 0.9;">
              ✨ PayPal has opened in a new tab<br>
              🔄 Waiting for payment confirmation...<br>
              ⏳ Please complete your payment and I'll update you here automatically!
            </div>
          </div>`
      });
      
      // Open PayPal in new tab
      window.open(result.approval_url, '_blank');
      
      // Start polling for payment status (every 10 seconds)
      startPaymentPolling(sessionId);
      
    } else {
      throw new Error("Unexpected response from checkout API");
    }
    
  } catch (error) {
    console.error("PayPal checkout error:", error);
    
    // Parse error response for better messaging
    let errorMessage = 'An error occurred during checkout. Please try again.';
    let helpMessage = '';
    
    if (error.message) {
      errorMessage = error.message;
    }
    
    // Check if this is a connection error to PayPal server
    if (errorMessage.toLowerCase().includes('paypal mcp server') || 
        errorMessage.toLowerCase().includes('not running') ||
        errorMessage.toLowerCase().includes('connection') ||
        errorMessage.toLowerCase().includes('503')) {
      helpMessage = '<br><br><strong>💡 Solution:</strong> The PayPal server needs to be running. Please ask the administrator to start the server using <code>python run_all_servers.py</code>';
    }
    
    // Show error message
    showNotification(`Checkout failed: ${errorMessage}`, "error");
    
    // Show detailed error in chat
    appendBotMessage({
      response: `❌ <strong>Checkout Error</strong><br><br>
        <div style="background: linear-gradient(135deg, #ef4444, #dc2626); color: white; padding: 20px; border-radius: 12px; margin: 10px 0;">
          <div style="display: flex; align-items-center; margin-bottom: 15px;">
            <i class="fas fa-exclamation-triangle" style="font-size: 24px; margin-right: 10px;"></i>
            <div>
              <div style="font-size: 16px; font-weight: bold;">Payment Gateway Error</div>
              <div style="font-size: 13px; opacity: 0.9; margin-top: 5px;">Unable to process checkout</div>
            </div>
          </div>
          <div style="font-size: 14px; opacity: 0.95; background: rgba(0,0,0,0.2); padding: 12px; border-radius: 8px;">
            ${errorMessage}
            ${helpMessage}
          </div>
          <div style="font-size: 12px; opacity: 0.8; margin-top: 12px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.2);">
            Your cart items are safe. You can try checking out again once the issue is resolved.
          </div>
        </div>`
    });
  }
}

/**
 * Payment Polling Functions
 */
function startPaymentPolling(sessionId) {
  console.log(`🔄 Starting payment polling for session: ${sessionId}`);
  
  let pollCount = 0;
  const maxPolls = 60; // 60 polls × 10 seconds = 10 minutes max
  
  // Clear any existing polling interval
  if (paymentPollingInterval) {
    clearInterval(paymentPollingInterval);
  }
  
  // Poll immediately
  checkPaymentStatus(sessionId);
  
  // Then poll every 10 seconds
  paymentPollingInterval = setInterval(async () => {
    pollCount++;
    
    if (pollCount >= maxPolls) {
      console.log('⏱️ Payment polling timeout reached');
      clearInterval(paymentPollingInterval);
      showNotification('Payment status check timed out. Please check your order history.', 'warning');
      return;
    }
    
    await checkPaymentStatus(sessionId);
  }, 10000); // 10 seconds
}

async function checkPaymentStatus(sessionId) {
  try {
    console.log(`🔍 Checking payment status for session: ${sessionId}`);
    const response = await fetch(`/api/check-payment-status?session_id=${sessionId}`);
    
    if (!response.ok) {
      console.error(`❌ Payment status API error: ${response.status}`);
      return;
    }
    
    const result = await response.json();
    
    console.log(`� Payment status response:`, result);
    console.log(`📊 Status value: "${result.status}"`);
    
    if (result.status === 'success') {
      // Payment successful!
      clearInterval(paymentPollingInterval);
      paymentPollingInterval = null;
      
      const orderDetails = result.order_details || {};
      const orderId = orderDetails.order_id || 'N/A';
      const orderTotal = orderDetails.order_total || cartTotal;
      
      console.log('✅ Payment successful! Showing success message in chat...');
      console.log('Order ID:', orderId);
      console.log('Order Total:', orderTotal);
      
      // Clear cart
      cartItems = [];
      cartCount = 0;
      cartTotal = 0;
      updateCartDisplay();
      
      // Show congratulations message with order ID
      appendBotMessage({
        response: `🎉 <strong>Congratulations!</strong><br><br>
          <div style="background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 25px; border-radius: 15px; margin: 10px 0; box-shadow: 0 8px 20px rgba(16, 185, 129, 0.3);">
            <div style="display: flex; align-items: center; margin-bottom: 20px;">
              <i class="fas fa-check-circle" style="font-size: 48px; margin-right: 15px; animation: pulse 2s infinite;"></i>
              <div>
                <div style="font-size: 24px; font-weight: bold; margin-bottom: 5px;">🎊 Order Placed Successfully!</div>
                <div style="font-size: 18px; opacity: 0.95; font-weight: 600;">Order ID: #${orderId}</div>
              </div>
            </div>
            <div style="background: rgba(255, 255, 255, 0.15); padding: 15px; border-radius: 10px; margin-bottom: 15px;">
              <div style="font-size: 15px; margin-bottom: 8px;">
                <strong>✅ Congratulations!</strong> Your order has been placed successfully.
              </div>
              <div style="font-size: 14px; opacity: 0.9; line-height: 1.6;">
                💳 Payment ID: ${result.payment_id || 'N/A'}<br>
                💰 Total Amount: £${orderTotal.toFixed(2)}<br>
                � Order ID: <strong>#${orderId}</strong><br>
                �📧 Confirmation email sent to your inbox!
              </div>
            </div>
            <div style="font-size: 13px; opacity: 0.9; border-top: 1px solid rgba(255,255,255,0.3); padding-top: 12px; margin-top: 12px; text-align: center;">
              <strong>🚚 Your order is being processed!</strong><br>
              Track your order anytime by asking: "show my orders" or "track order #${orderId}"
            </div>
          </div>
          <style>
            @keyframes pulse {
              0%, 100% { transform: scale(1); opacity: 1; }
              50% { transform: scale(1.1); opacity: 0.8; }
            }
          </style>`
      });
      
      showNotification(`🎉 Congratulations! Order #${orderId} placed successfully!`, 'success');
      
    } else if (result.status === 'cancelled') {
      // Payment cancelled
      clearInterval(paymentPollingInterval);
      paymentPollingInterval = null;
      
      appendBotMessage({
        response: `⚠️ <strong>Payment Cancelled</strong><br><br>
          <div style="background: linear-gradient(135deg, #f59e0b, #d97706); color: white; padding: 20px; border-radius: 15px; margin: 10px 0;">
            <div style="display: flex; align-items: center; margin-bottom: 15px;">
              <i class="fas fa-exclamation-triangle" style="font-size: 24px; margin-right: 10px;"></i>
              <div>
                <div style="font-size: 18px; font-weight: bold;">Payment Cancelled</div>
              </div>
            </div>
            <div style="font-size: 14px; opacity: 0.9;">
              Your payment was cancelled. Your cart items are still here if you'd like to try again!
            </div>
          </div>`
      });
      
      showNotification('Payment cancelled. Your cart is preserved.', 'warning');
      
    } else if (result.status === 'pending') {
      // Still waiting - just log it
      console.log('⏳ Payment still pending...');
    }
    
  } catch (error) {
    console.error('❌ Error checking payment status:', error);
  }
}

/**
 * UI Interaction Functions
 */
function openProductDetail(productId) {
  console.log('Opening product details for:', productId);
  
  // Add a subtle click animation
  const clickedCard = event.currentTarget;
  if (clickedCard) {
    clickedCard.style.transform = 'scale(0.98)';
    setTimeout(() => {
      clickedCard.style.transform = '';
    }, 150);
  }
  
  // Show loading message in chat
  appendMessage(`📱 Loading product details for ${productId}...`, "user");
  
  // Automatically ask the chatbot about this product and submit
  const queryInput = document.getElementById("query");
  queryInput.value = `Show me detailed information about product ${productId}`;
  
  // Add visual feedback
  queryInput.classList.add("ring-2", "ring-purple-500");
  setTimeout(() => {
    queryInput.classList.remove("ring-2", "ring-purple-500");
  }, 1000);
  
  // Auto-submit the query to get product details in chat
  setTimeout(() => {
    submitQuery();
  }, 200);
}

function scrollCarousel(carouselId, distance) {
  const carousel = document.getElementById(carouselId);
  if (carousel) {
    carousel.scrollTo({
      left: carousel.scrollLeft + distance,
      behavior: 'smooth'
    });
  }
}

function smoothScrollToBottom() {
  const chatBox = document.getElementById("chat-box");
  chatBox.scrollTo({
    top: chatBox.scrollHeight,
    behavior: 'smooth'
  });
}

/**
 * Notification System
 */
function showNotification(message, type = "info") {
  const notification = document.createElement("div");
  notification.className = `fixed top-4 right-4 z-50 p-4 rounded-xl shadow-2xl transform transition-all duration-300 translate-x-full opacity-0`;
  
  if (type === "success") {
    notification.className += " bg-gradient-to-r from-green-500 to-emerald-600 text-white";
    notification.innerHTML = `
      <div class="flex items-center space-x-3">
        <i class="fas fa-check-circle text-xl"></i>
        <span class="font-medium">${message}</span>
      </div>
    `;
  } else if (type === "error") {
    notification.className += " bg-gradient-to-r from-red-500 to-rose-600 text-white";
    notification.innerHTML = `
      <div class="flex items-center space-x-3">
        <i class="fas fa-exclamation-circle text-xl"></i>
        <span class="font-medium">${message}</span>
      </div>
    `;
  } else {
    notification.className += " bg-gradient-to-r from-blue-500 to-indigo-600 text-white";
    notification.innerHTML = `
      <div class="flex items-center space-x-3">
        <i class="fas fa-info-circle text-xl"></i>
        <span class="font-medium">${message}</span>
      </div>
    `;
  }
  
  document.body.appendChild(notification);
  
  // Animate in
  setTimeout(() => {
    notification.classList.remove("translate-x-full", "opacity-0");
  }, 100);
  
  // Animate out
  setTimeout(() => {
    notification.classList.add("translate-x-full", "opacity-0");
    setTimeout(() => {
      document.body.removeChild(notification);
    }, 300);
  }, 3000);
}

/**
 * Event Listeners and Initialization
 */
function initializeInteractiveElements() {
  // Add hover effects to category cards
  const categoryCards = document.querySelectorAll('[data-category]');
  categoryCards.forEach(card => {
    card.addEventListener('click', function() {
      const category = this.getAttribute('data-category');
      const queryInput = document.getElementById("query");
      queryInput.value = `Show me ${category} products`;
      submitQuery();
    });
  });
  
  // Add input focus effects
  const inputs = document.querySelectorAll('input');
  inputs.forEach(input => {
    input.addEventListener('focus', function() {
      this.parentElement.classList.add('ring-2', 'ring-purple-500/30');
    });
    
    input.addEventListener('blur', function() {
      this.parentElement.classList.remove('ring-2', 'ring-purple-500/30');
    });
  });
}

// Quantity control functions for detailed product view
function increaseQuantity(productId) {
  const quantityInput = document.getElementById(`quantity-${productId}`);
  if (quantityInput) {
    const currentValue = parseInt(quantityInput.value) || 1;
    const maxValue = parseInt(quantityInput.getAttribute('max')) || 10;
    if (currentValue < maxValue) {
      quantityInput.value = currentValue + 1;
      
      // Add visual feedback
      quantityInput.classList.add('ring-2', 'ring-purple-500', 'bg-purple-50');
      setTimeout(() => {
        quantityInput.classList.remove('ring-2', 'ring-purple-500', 'bg-purple-50');
      }, 300);
    }
  }
}

function decreaseQuantity(productId) {
  const quantityInput = document.getElementById(`quantity-${productId}`);
  if (quantityInput) {
    const currentValue = parseInt(quantityInput.value) || 1;
    const minValue = parseInt(quantityInput.getAttribute('min')) || 1;
    if (currentValue > minValue) {
      quantityInput.value = currentValue - 1;
      
      // Add visual feedback
      quantityInput.classList.add('ring-2', 'ring-purple-500', 'bg-purple-50');
      setTimeout(() => {
        quantityInput.classList.remove('ring-2', 'ring-purple-500', 'bg-purple-50');
      }, 300);
    }
  }
}

// Enhanced add to cart function for detailed product view
async function addToCartDetailed(productId, productName, productPrice) {
  const quantityInput = document.getElementById(`quantity-${productId}`);
  const quantity = quantityInput ? parseInt(quantityInput.value) || 1 : 1;
  
  // Show loading state on the button
  const button = event.currentTarget;
  const originalContent = button.innerHTML;
  button.disabled = true;
  button.innerHTML = `
    <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
    <span>Adding...</span>
  `;
  
  try {
    // Add to cart with quantity
    for (let i = 0; i < quantity; i++) {
      await addToCart(productId, productName, null, false); // Don't show individual messages
    }
    
    // Show success message with quantity
    button.innerHTML = `
      <i class="fas fa-check text-xl animate-pulse"></i>
      <span>Added ${quantity} item${quantity > 1 ? 's' : ''}!</span>
    `;
    button.classList.remove('from-purple-600', 'to-pink-500');
    button.classList.add('from-green-500', 'to-emerald-500');
    
    // Show success notification
    showNotification(`Added ${quantity} x ${productName} to cart!`, 'success');
    
    // Reset button after 3 seconds
    setTimeout(() => {
      button.innerHTML = originalContent;
      button.classList.remove('from-green-500', 'to-emerald-500');
      button.classList.add('from-purple-600', 'via-purple-500', 'to-pink-500');
      button.disabled = false;
    }, 3000);
    
  } catch (error) {
    console.error('Error adding to cart:', error);
    button.innerHTML = `
      <i class="fas fa-exclamation-triangle text-xl"></i>
      <span>Error</span>
    `;
    button.classList.remove('from-purple-600', 'to-pink-500');
    button.classList.add('from-red-500', 'to-red-600');
    
    // Reset button after 3 seconds
    setTimeout(() => {
      button.innerHTML = originalContent;
      button.classList.remove('from-red-500', 'to-red-600');
      button.classList.add('from-purple-600', 'via-purple-500', 'to-pink-500');
      button.disabled = false;
    }, 3000);
  }
}

// Notification function
function showNotification(message, type = 'info') {
  // Create notification element
  const notification = document.createElement('div');
  notification.className = `
    fixed top-4 right-4 z-50 max-w-sm bg-white rounded-xl shadow-2xl border-l-4 
    ${type === 'success' ? 'border-green-500' : type === 'error' ? 'border-red-500' : 'border-blue-500'}
    transform translate-x-full transition-transform duration-300 ease-out
  `;
  
  notification.innerHTML = `
    <div class="p-4 flex items-center space-x-3">
      <div class="flex-shrink-0">
        <i class="fas ${type === 'success' ? 'fa-check-circle text-green-500' : type === 'error' ? 'fa-exclamation-circle text-red-500' : 'fa-info-circle text-blue-500'} text-xl"></i>
      </div>
      <div class="flex-1">
        <p class="text-sm font-medium text-gray-900">${message}</p>
      </div>
      <button onclick="this.parentElement.parentElement.remove()" class="text-gray-400 hover:text-gray-600">
        <i class="fas fa-times text-sm"></i>
      </button>
    </div>
  `;
  
  document.body.appendChild(notification);
  
  // Show notification
  setTimeout(() => {
    notification.classList.remove('translate-x-full');
  }, 100);
  
  // Auto-remove after 5 seconds
  setTimeout(() => {
    notification.classList.add('translate-x-full');
    setTimeout(() => {
      notification.remove();
    }, 300);
  }, 5000);
}

// Event listeners for form submission
document.addEventListener('DOMContentLoaded', function() {
  const queryInput = document.getElementById("query");
  if (queryInput) {
    queryInput.addEventListener("keydown", function(event) {
      if (event.key === "Enter") {
        submitQuery();
      }
    });
  }
});

// Add keyboard shortcuts
document.addEventListener('keydown', function(event) {
  // Ctrl/Cmd + Enter to send message
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    submitQuery();
  }
  
  // Escape to clear input
  if (event.key === 'Escape') {
    const queryInput = document.getElementById("query");
    queryInput.value = '';
    queryInput.blur();
  }
});

// Refresh best selling products periodically (every 5 minutes)
setInterval(loadBestSellingProducts, 5 * 60 * 1000);

/**
 * Conversation Context UI Functions
 */
function showContextIndicator(originalQuery) {
  // Show a subtle indicator that context is being used
  const chatBox = document.getElementById("chat-box");
  const contextIndicator = document.createElement("div");
  contextIndicator.className = "flex justify-center my-2 animate-fade-in";
  contextIndicator.innerHTML = `
    <div class="bg-gradient-to-r from-purple-100 to-blue-100 border border-purple-200 rounded-full px-4 py-2 flex items-center space-x-2 text-sm text-purple-700 shadow-sm">
      <i class="fas fa-brain text-purple-500 animate-pulse"></i>
      <span class="font-medium">Using conversation context to understand your request</span>
      <div class="flex space-x-1">
        <div class="w-1 h-1 bg-purple-400 rounded-full animate-bounce"></div>
        <div class="w-1 h-1 bg-purple-400 rounded-full animate-bounce" style="animation-delay: 0.1s"></div>
        <div class="w-1 h-1 bg-purple-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
      </div>
    </div>
  `;
  
  chatBox.appendChild(contextIndicator);
  chatBox.scrollTop = chatBox.scrollHeight;
  
  // Remove indicator after a few seconds
  setTimeout(() => {
    contextIndicator.remove();
  }, 3000);
}

function showConversationDebugPanel() {
  // Debug function to show conversation context
  if (window.conversationContext) {
    const context = window.conversationContext.exportContext();
    console.log('🧠 Conversation Context Debug:', context);
    
    // Show in a modal or alert for debugging
    const summary = `
Conversation Context Debug:
- Session ID: ${context.session_id}
- Total Conversations: ${context.conversation_history.length}
- Last Products: ${context.last_products.length}
- Recent Context: ${context.context.length} pairs

Last Products: ${context.last_products.map(p => p.product_name).join(', ')}
    `;
    
    alert(summary);
  }
}

// Add keyboard shortcut for debug panel (Ctrl+Shift+D)
document.addEventListener('keydown', function(event) {
  if (event.ctrlKey && event.shiftKey && event.key === 'D') {
    event.preventDefault();
    showConversationDebugPanel();
  }
});

/**
 * Enhanced UI Indicators for Smart Features
 */
function addSmartFeatureIndicators() {
  // Add indicators to show AI features are active
  const queryInput = document.getElementById("query");
  
  // Show smart suggestions when user types
  queryInput.addEventListener('input', function() {
    const value = this.value.toLowerCase();
    
    // Check for context-aware patterns
    if (window.conversationContext && window.conversationContext.isContextAwareQuery(value)) {
      showSmartSuggestion("💡 I can use our conversation history to understand this better!");
    } else if (value.includes('accessories') || value.includes('goes with')) {
      showSmartSuggestion("🔗 I can suggest accessories based on your recent product views!");
    } else if (value.includes('similar') || value.includes('like this')) {
      showSmartSuggestion("🎯 I'll use AI to find similar products for you!");
    }
  });
}

function showSmartSuggestion(message) {
  // Remove any existing suggestion
  const existingSuggestion = document.querySelector('.smart-suggestion');
  if (existingSuggestion) {
    existingSuggestion.remove();
  }
  
  // Create new suggestion
  const suggestion = document.createElement('div');
  suggestion.className = 'smart-suggestion absolute top-full left-0 right-0 mt-2 bg-gradient-to-r from-blue-50 to-purple-50 border border-blue-200 rounded-xl p-3 text-sm text-blue-700 shadow-lg z-10 animate-slide-down';
  suggestion.innerHTML = `
    <div class="flex items-center space-x-2">
      <i class="fas fa-lightbulb text-yellow-500 animate-pulse"></i>
      <span>${message}</span>
    </div>
  `;
  
  const inputContainer = document.getElementById("query").parentElement;
  inputContainer.style.position = 'relative';
  inputContainer.appendChild(suggestion);
  
  // Auto-remove after 4 seconds
  setTimeout(() => {
    suggestion.remove();
  }, 4000);
}

/**
 * Context-Aware Placeholder Updates
 */
function updateSmartPlaceholder() {
  const queryInput = document.getElementById("query");
  if (!queryInput) return;
  
  const suggestions = [
    "Try: 'Show me accessories for these products'",
    "Ask me: 'Find similar items to what I just viewed'",
    "Try: 'What colors are available for these?'",
    "Ask: 'Show me jackets under £100'",
    "Try: 'What goes well with this outfit?'"
  ];
  
  let currentIndex = 0;
  
  setInterval(() => {
    if (queryInput.value === "" && !queryInput.matches(':focus')) {
      queryInput.placeholder = suggestions[currentIndex];
      currentIndex = (currentIndex + 1) % suggestions.length;
    }
  }, 4000);
}

/**
 * Authentication Functions
 */
function checkAuthenticationRequired(query) {
  // Check if query requires authentication (orders or add to cart)
  const orderKeywords = ['my orders', 'my order', 'order history', 'show my orders', 'get my orders', 'list my orders', 'show order', 'view my orders', 'check my orders'];
  const cartKeywords = ['add to cart', 'add product', 'add item'];
  
  const needsAuth = orderKeywords.some(keyword => query.toLowerCase().includes(keyword)) ||
                   cartKeywords.some(keyword => query.toLowerCase().includes(keyword));
  
  return needsAuth && !isLoggedIn;
}

function showLoginForm(message = "Please login to continue") {
  const loginForm = document.getElementById("login-form");
  const chatBox = document.getElementById("chat-box");
  
  // Add login required message to chat
  appendMessage("Login required to access this feature", "bot");
  
  // Show login form
  loginForm.classList.remove("hidden");
  loginForm.scrollIntoView({ behavior: 'smooth' });
  
  // Focus on email input
  setTimeout(() => {
    document.getElementById("login-email").focus();
  }, 300);
}

function hideLoginForm() {
  const loginForm = document.getElementById("login-form");
  loginForm.classList.add("hidden");
}

async function handleLogin(event) {
  event.preventDefault();
  
  const emailInput = document.getElementById("login-email");
  const passwordInput = document.getElementById("login-password");
  const submitBtn = event.target.querySelector('button[type="submit"]');
  
  const email = emailInput.value.trim();
  const password = passwordInput.value.trim();
  
  if (!email || !password) {
    showNotification("Please enter both email and password", "error");
    return;
  }
  
  // Show loading state
  const originalText = submitBtn.innerHTML;
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Logging in...';
  
  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    
    const data = await response.json();
    
    if (data.success) {
      // Login successful
      currentUser = {
        name: data.customer_name,
        email: data.customer_email
      };
      isLoggedIn = true;
      
      // Save login state to localStorage
      try {
        localStorage.setItem('user_logged_in', 'true');
        localStorage.setItem('user_email', data.customer_email);
        localStorage.setItem('user_name', data.customer_name);
      } catch (e) {
        console.warn('Could not save login state:', e);
      }
      
      // Update UI
      updateUIAfterLogin();
      
      // Hide login form
      hideLoginForm();
      
      // Reload personalized products
      loadBestSellingProducts();
      
      // Show personalized welcome message with order history
      showPersonalizedWelcome(data);
      
      // Clear login form
      emailInput.value = "";
      passwordInput.value = "";
      
    } else {
      throw new Error(data.error || "Login failed");
    }
    
  } catch (error) {
    console.error("Login error:", error);
    showNotification(error.message || "Login failed. Please try again.", "error");
  } finally {
    // Reset button
    submitBtn.disabled = false;
    submitBtn.innerHTML = originalText;
  }
}

function updateUIAfterLogin() {
  // Hide login button, show user info button
  const loginBtn = document.getElementById("login-btn");
  const userInfoBtn = document.getElementById("user-info-btn");
  const loggedInName = document.getElementById("logged-in-name");
  const userMenuName = document.getElementById("user-menu-name");
  const userMenuEmail = document.getElementById("user-menu-email");
  
  if (loginBtn) loginBtn.classList.add("hidden");
  if (userInfoBtn) userInfoBtn.classList.remove("hidden");
  if (loggedInName) loggedInName.textContent = currentUser.name;
  if (userMenuName) userMenuName.textContent = currentUser.name;
  if (userMenuEmail) userMenuEmail.textContent = currentUser.email;
  
  // Also update old email input for compatibility
  const emailInput = document.getElementById("email");
  if (emailInput) emailInput.value = currentUser.email;
}

function checkPreviousLogin() {
  // Check if user was previously logged in
  try {
    const wasLoggedIn = localStorage.getItem('user_logged_in');
    const savedEmail = localStorage.getItem('user_email');
    const savedName = localStorage.getItem('user_name');
    
    if (wasLoggedIn === 'true' && savedEmail && savedName) {
      currentUser = {
        name: savedName,
        email: savedEmail
      };
      isLoggedIn = true;
      updateUIAfterLogin();
      console.log('✅ Restored previous login session for:', savedEmail);
    }
  } catch (e) {
    console.warn('Could not restore login state:', e);
  }
}

function showPersonalizedWelcome(loginData) {
  console.log('🎉 showPersonalizedWelcome called with data:', loginData);
  const { customer_name, recent_orders, total_orders } = loginData;
  console.log('📦 Orders data:', recent_orders, 'Total:', total_orders);
  
  // Create personalized welcome message
  let welcomeHtml = `
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 25px; border-radius: 15px; margin: 10px 0; box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3);">
      <div style="display: flex; align-items: center; margin-bottom: 20px;">
        <div style="background: rgba(255,255,255,0.2); border-radius: 50%; width: 50px; height: 50px; display: flex; align-items: center; justify-content: center; margin-right: 15px; font-size: 24px;">
          👋
        </div>
        <div>
          <h3 style="margin: 0; font-size: 22px; font-weight: 700;">Welcome back, ${customer_name}!</h3>
          <p style="margin: 5px 0 0 0; font-size: 14px; opacity: 0.9;">Your personalized shopping experience is ready</p>
        </div>
      </div>
  `;
  
  if (recent_orders && recent_orders.length > 0) {
    welcomeHtml += `
      <div style="background: rgba(255,255,255,0.15); padding: 18px; border-radius: 12px; margin-top: 15px;">
        <h4 style="margin: 0 0 15px 0; font-size: 16px; font-weight: 600; display: flex; align-items: center;">
          <i class="fas fa-history" style="margin-right: 8px;"></i>
          Your Recent Orders
        </h4>
    `;
    
    recent_orders.forEach((order, index) => {
      const orderDate = order.order_date ? new Date(order.order_date).toLocaleDateString('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
      }) : 'N/A';
      
      const statusColor = order.order_status.toLowerCase() === 'approved' ? '#10b981' : 
                         order.order_status.toLowerCase() === 'open' ? '#3b82f6' : '#6b7280';
      
      welcomeHtml += `
        <div style="background: rgba(255,255,255,0.1); padding: 12px; border-radius: 8px; margin-bottom: ${index < recent_orders.length - 1 ? '10px' : '0'}; display: flex; align-items: center; justify-content: space-between;">
          <div style="display: flex; align-items: center; flex: 1;">
            ${order.image_url ? `<img src="${order.image_url}" alt="${order.product_name}" style="width: 40px; height: 40px; object-fit: cover; border-radius: 8px; margin-right: 12px; border: 2px solid rgba(255,255,255,0.3);" onerror="this.style.display='none'">` : ''}
            <div style="flex: 1; min-width: 0;">
              <div style="font-size: 13px; font-weight: 600; margin-bottom: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${order.product_name}</div>
              <div style="font-size: 11px; opacity: 0.8;">
                <span style="margin-right: 10px;">📅 ${orderDate}</span>
                <span style="background: ${statusColor}; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 600;">${order.order_status}</span>
              </div>
            </div>
          </div>
          <div style="text-align: right; margin-left: 12px;">
            <div style="font-size: 14px; font-weight: 700;">£${order.total_price.toFixed(2)}</div>
            <div style="font-size: 10px; opacity: 0.7;">#${order.order_id}</div>
          </div>
        </div>
      `;
    });
    
    welcomeHtml += `
      </div>
      <div style="margin-top: 15px; text-align: center; font-size: 13px; opacity: 0.9;">
        <i class="fas fa-info-circle" style="margin-right: 5px;"></i>
        I've personalized your Trending Now section based on your purchase history!
      </div>
    `;
  } else {
    welcomeHtml += `
      <div style="background: rgba(255,255,255,0.15); padding: 15px; border-radius: 12px; margin-top: 15px; text-align: center;">
        <i class="fas fa-shopping-bag" style="font-size: 32px; opacity: 0.5; margin-bottom: 10px;"></i>
        <p style="margin: 0; font-size: 14px; opacity: 0.9;">No order history yet. Start shopping to get personalized recommendations!</p>
      </div>
    `;
  }
  
  welcomeHtml += `
    </div>
  `;
  
  // Display in chat
  appendBotMessage({ ai_response: welcomeHtml });

  // Show success notification
  showNotification(`Welcome back, ${customer_name}!`, "success");

  // Start guided selling after a short pause
  const persona = loginData.persona || {};
  setTimeout(() => startGuidedSelling(customer_name, persona, recent_orders || []), 600);
}

// ═══════════════════════════════════════════════════════════════
// 🛍️  GUIDED SELLING CONVERSATION  — post-login
// ═══════════════════════════════════════════════════════════════

const _gs = {
  step: 0,
  answers: {},
  persona: {},
  customerName: '',
  recentOrders: [],
};

function startGuidedSelling(customerName, persona, recentOrders) {
  _gs.step = 0;
  _gs.answers = {};
  _gs.persona = persona;
  _gs.customerName = customerName;
  _gs.recentOrders = recentOrders;

  const chatBox = document.getElementById('chat-box');
  if (!chatBox) return;

  // Build persona-aware category chips for Q1
  const CATEGORY_ICONS = {
    jackets:'🧥', dresses:'👗', accessories:'💍', shoes:'👟',
    watches:'⌚', coats:'🧥', shirts:'👔', bags:'👜',
    trousers:'👖', activewear:'🏃', tops:'👕',
  };
  const favCats = (persona.favorite_categories || '')
    .split(',').map(c => c.trim().toLowerCase()).filter(Boolean);
  const allCats = favCats.length
    ? favCats.slice(0, 4)
    : ['jackets','shoes','accessories','shirts'];

  const catChips = allCats.map(cat => {
    const icon = CATEGORY_ICONS[cat] || '🔍';
    const label = cat.charAt(0).toUpperCase() + cat.slice(1);
    return _gsChip(icon + ' ' + label, 'category', cat);
  }).join('') + _gsChip('🛍️ Just Browsing', 'category', 'browse');

  const shopPersona = persona.shopping_persona || '';
  let opener = `Hi <strong>${customerName}</strong>! 👋 `;
  if (shopPersona === 'Fashion Forward') opener += "Ready to explore the latest styles?";
  else if (shopPersona === 'Deal Hunter') opener += "Let's find you some great value today!";
  else if (shopPersona === 'Brand Conscious') opener += "I'll help you find something perfect.";
  else opener += "Let me help you find exactly what you need today.";

  // Q1 bubble
  const bubble = document.createElement('div');
  bubble.id = 'gs-bubble-0';
  bubble.className = 'flex justify-start animate-slide-up';
  bubble.innerHTML = `
    <div class="chat-bubble-bot p-4 shadow-lg rounded-2xl"
         style="border-left:4px solid #7c3aed; max-width:500px;">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
        <div style="background:linear-gradient(135deg,#7c3aed,#db2777);
                    width:36px;height:36px;border-radius:50%;display:flex;
                    align-items:center;justify-content:center;flex-shrink:0;">
          <i class="fas fa-magic" style="color:#fff;font-size:14px;"></i>
        </div>
        <p style="margin:0;font-size:14px;color:#374151;">${opener}</p>
      </div>
      <p style="margin:0 0 12px;font-size:15px;font-weight:700;color:#4c1d95;">
        What are you shopping for today? 🛍️
      </p>
      <div style="display:flex;flex-wrap:wrap;gap:6px;">${catChips}</div>
      <p style="margin:12px 0 0;font-size:11px;color:#9ca3af;">
        💬 Or skip this and type directly in the chat below.
      </p>
    </div>`;
  chatBox.appendChild(bubble);
  chatBox.scrollTop = chatBox.scrollHeight;
  _gs.step = 1;
}

function _gsChip(label, key, value) {
  return `<button
    onclick="handleGuidedAnswer('${key}','${value.replace(/'/g,"\\'")}')"
    style="display:inline-flex;align-items:center;gap:5px;
           background:#fff;border:2px solid #7c3aed;color:#7c3aed;
           padding:7px 14px;border-radius:24px;font-size:13px;
           font-weight:600;cursor:pointer;transition:all 0.2s;"
    onmouseover="this.style.background='#7c3aed';this.style.color='#fff';"
    onmouseout="this.style.background='#fff';this.style.color='#7c3aed';"
  >${label}</button>`;
}

window.handleGuidedAnswer = function(key, value) {
  const chatBox = document.getElementById('chat-box');
  if (!chatBox) return;

  // Disable all chips in the current question bubble
  const currentBubble = document.getElementById(`gs-bubble-${_gs.step - 1}`);
  if (currentBubble) {
    currentBubble.querySelectorAll('button').forEach(b => {
      b.disabled = true;
      b.style.opacity = '0.5';
      b.style.cursor = 'default';
    });
  }

  // Show user's answer as a user chat bubble
  const userLabel = value === 'browse' ? 'Just Browsing'
    : value === 'skip' ? 'Skip ➜'
    : value.charAt(0).toUpperCase() + value.slice(1);

  const userBubble = document.createElement('div');
  userBubble.className = 'flex justify-end animate-slide-up';
  userBubble.innerHTML = `
    <div style="background:linear-gradient(135deg,#7c3aed,#db2777);
                color:#fff;padding:10px 16px;border-radius:18px 18px 4px 18px;
                font-size:14px;font-weight:600;max-width:280px;">
      ${userLabel}
    </div>`;
  chatBox.appendChild(userBubble);
  chatBox.scrollTop = chatBox.scrollHeight;

  _gs.answers[key] = value;

  // ── Step logic ──────────────────────────────────────────────
  if (key === 'category' && value !== 'browse') {
    // Q2: Occasion
    setTimeout(() => _gsAskOccasion(), 400);
  } else if (key === 'category' && value === 'browse') {
    // User wants to browse freely
    setTimeout(() => _gsEndSkip(), 400);
  } else if (key === 'occasion' && value !== 'skip') {
    // Q3: Style / Mood
    setTimeout(() => _gsAskStyle(), 400);
  } else if (key === 'occasion' && value === 'skip') {
    setTimeout(() => _gsSubmitQuery(), 400);
  } else if (key === 'style') {
    // All answered → submit
    setTimeout(() => _gsSubmitQuery(), 400);
  }
};

function _gsChipPink(label, key, value) {
  return `<button
    onclick="handleGuidedAnswer('${key}','${value.replace(/'/g,"\\'")}')"
    style="display:inline-flex;align-items:center;gap:5px;
           background:#fff;border:2px solid #db2777;color:#db2777;
           padding:7px 14px;border-radius:24px;font-size:13px;
           font-weight:600;cursor:pointer;transition:all 0.2s;"
    onmouseover="this.style.background='#db2777';this.style.color='#fff';"
    onmouseout="this.style.background='#fff';this.style.color='#db2777';"
  >${label}</button>`;
}

function _gsAskOccasion() {
  const chatBox = document.getElementById('chat-box');
  const OCCASION_MAP = {
    casual:   '😎 Casual Day',
    office:   '💼 Office / Work',
    party:    '🎉 Night Out',
    sport:    '💪 Sport / Active',
    outdoor:  '🏔️ Outdoor',
    formal:   '🎩 Formal',
  };
  const favOcc = (_gs.persona.occasion_preference || 'casual,office')
    .split(',').map(o => o.trim().toLowerCase()).filter(Boolean);
  const occList = [...new Set([...favOcc, 'casual', 'office', 'party'])].slice(0, 4);
  const chips = occList.map(o => {
    const label = OCCASION_MAP[o] || (o.charAt(0).toUpperCase() + o.slice(1));
    return _gsChipPink(label, 'occasion', o);
  }).join('') + _gsChipPink('⚡ Surprise me', 'occasion', 'skip');

  const bubble = document.createElement('div');
  bubble.id = `gs-bubble-${_gs.step}`;
  bubble.className = 'flex justify-start animate-slide-up';
  bubble.innerHTML = `
    <div class="chat-bubble-bot p-4 shadow-lg rounded-2xl"
         style="border-left:4px solid #db2777; max-width:500px;">
      <p style="margin:0 0 12px;font-size:15px;font-weight:700;color:#831843;">
        What's the occasion? 🎯
      </p>
      <div style="display:flex;flex-wrap:wrap;gap:6px;">${chips}</div>
    </div>`;
  chatBox.appendChild(bubble);
  chatBox.scrollTop = chatBox.scrollHeight;
  _gs.step++;
}

function _gsAskStyle() {
  const chatBox = document.getElementById('chat-box');
  const styleChips = ['Trendy 🌟','Classic ✨','Minimalist ◽','Bold & Colourful 🎨','Relaxed & Comfy 😌']
    .map(s => _gsChip(s, 'style', s.split(' ')[0].toLowerCase()))
    .join('');
  const bubble = document.createElement('div');
  bubble.id = `gs-bubble-${_gs.step}`;
  bubble.className = 'flex justify-start animate-slide-up';
  bubble.innerHTML = `
    <div class="chat-bubble-bot p-4 shadow-lg rounded-2xl"
         style="border-left:4px solid #7c3aed; max-width:500px;">
      <p style="margin:0 0 12px;font-size:15px;font-weight:700;color:#4c1d95;">
        What style are you in the mood for? ✨
      </p>
      <div style="display:flex;flex-wrap:wrap;gap:6px;">${styleChips}</div>
    </div>`;
  chatBox.appendChild(bubble);
  chatBox.scrollTop = chatBox.scrollHeight;
  _gs.step++;
}

function _gsEndSkip() {
  const chatBox = document.getElementById('chat-box');
  const bubble = document.createElement('div');
  bubble.className = 'flex justify-start animate-slide-up';
  bubble.innerHTML = `
    <div class="chat-bubble-bot p-4 rounded-2xl" style="max-width:420px;">
      <p style="margin:0 0 8px;font-size:14px;color:#374151;">
        No problem! Let me show you our <strong style="color:#7c3aed;">best-selling products</strong> to inspire you. 🌟
      </p>
      <p style="margin:0;font-size:13px;color:#6b7280;">
        Feel free to type anything in the chat below — I'm here to help whenever you're ready. 😊
      </p>
    </div>`;
  chatBox.appendChild(bubble);
  chatBox.scrollTop = chatBox.scrollHeight;

  // Auto-submit best selling products query
  setTimeout(() => {
    const chatInput = document.getElementById('query');
    if (chatInput) {
      chatInput.value = 'Show me best selling products';
      chatInput.focus();
    }
    if (typeof submitQuery === 'function') submitQuery();
  }, 600);
}

function _gsSubmitQuery() {
  const chatBox = document.getElementById('chat-box');
  const cat     = _gs.answers.category || '';
  const occ     = _gs.answers.occasion  || '';
  const style   = _gs.answers.style     || (_gs.persona.style_preference || '');
  const budget  = _gs.persona.budget_range || '';
  const color   = _gs.persona.color_preference || '';

  // Build natural language query
  let parts = ['Show me'];
  if (style && style !== 'skip') parts.push(style.toLowerCase());
  if (cat && cat !== 'skip')     parts.push(cat);
  if (occ && occ !== 'skip')     parts.push(`for ${occ}`);
  if (budget)                    parts.push(`within ${budget} budget`);
  if (color)                     parts.push(`preferably in ${color.toLowerCase()} tones`);
  const query = parts.join(' ');

  // Show a "searching" transition message
  const bubble = document.createElement('div');
  bubble.className = 'flex justify-start animate-slide-up';
  bubble.innerHTML = `
    <div class="chat-bubble-bot p-4 rounded-2xl" style="max-width:420px;">
      <p style="margin:0;font-size:14px;color:#374151;">
        <i class="fas fa-spinner fa-spin" style="color:#7c3aed;margin-right:8px;"></i>
        Finding the perfect picks for you…
      </p>
    </div>`;
  chatBox.appendChild(bubble);
  chatBox.scrollTop = chatBox.scrollHeight;

  // Feed the query into the chat input and submit
  setTimeout(() => {
    const chatInput = document.getElementById('query');
    if (chatInput) {
      chatInput.value = query;
      chatInput.focus();
    }
    if (typeof submitQuery === 'function') submitQuery();
  }, 300);
}

function logout() {
  if (confirm("Are you sure you want to logout?")) {
    closeUserMenu();
    
    // Reset authentication state
    currentUser = null;
    isLoggedIn = false;
    
    // Clear cart on logout
    cartItems = [];
    cartCount = 0;
    cartTotal = 0;
    
    // Clear from all storage
    try {
      sessionStorage.removeItem('shoppingCart');
      sessionStorage.removeItem('tempCart');
      sessionStorage.removeItem('hadCartItems');
      localStorage.removeItem('user_logged_in');
      localStorage.removeItem('user_email');
      localStorage.removeItem('user_name');
    } catch (error) {
      console.error('Error clearing storage on logout:', error);
    }
    
    updateCartDisplay();
    
    // Update UI - show login button, hide user info
    const loginBtn = document.getElementById("login-btn");
    const userInfoBtn = document.getElementById("user-info-btn");
    
    if (loginBtn) loginBtn.classList.remove("hidden");
    if (userInfoBtn) userInfoBtn.classList.add("hidden");
    
    // Hide order history section
    const orderHistorySection = document.getElementById("order-history-section");
    if (orderHistorySection) orderHistorySection.classList.add("hidden");
    
    // Reload products (back to general trending)
    loadBestSellingProducts();
    
    // Show logout message
    appendMessage("You have been logged out successfully. Your cart has been cleared.", "bot");
    showNotification("Logged out successfully", "info");
  }
}

/**
 * Login Modal Functions
 */
function showLoginModal() {
  const modal = document.getElementById("login-modal");
  const modalContent = document.getElementById("login-modal-content");
  
  modal.classList.remove("hidden");
  setTimeout(() => {
    modalContent.classList.remove("scale-95", "opacity-0");
    modalContent.classList.add("scale-100", "opacity-100");
  }, 10);
  
  // Focus on email input
  setTimeout(() => {
    document.getElementById("modal-login-email").focus();
  }, 300);
}

function closeLoginModal() {
  const modal = document.getElementById("login-modal");
  const modalContent = document.getElementById("login-modal-content");
  
  modalContent.classList.remove("scale-100", "opacity-100");
  modalContent.classList.add("scale-95", "opacity-0");
  
  setTimeout(() => {
    modal.classList.add("hidden");
  }, 300);
}

async function handleModalLogin(event) {
  event.preventDefault();
  
  const emailInput = document.getElementById("modal-login-email");
  const passwordInput = document.getElementById("modal-login-password");
  const submitBtn = event.target.querySelector('button[type="submit"]');
  
  const email = emailInput.value.trim();
  const password = passwordInput.value.trim();
  
  if (!email || !password) {
    showNotification("Please enter both email and password", "error");
    return;
  }
  
  // Show loading state
  const originalText = submitBtn.innerHTML;
  submitBtn.disabled = true;
  submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Logging in...';
  
  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    
    const data = await response.json();
    
    if (data.success) {
      // Login successful
      currentUser = {
        name: data.customer_name,
        email: data.customer_email
      };
      isLoggedIn = true;
      
      // Save login state to localStorage
      try {
        localStorage.setItem('user_logged_in', 'true');
        localStorage.setItem('user_email', data.customer_email);
        localStorage.setItem('user_name', data.customer_name);
      } catch (e) {
        console.warn('Could not save login state:', e);
      }
      
      // Update UI
      updateUIAfterLogin();
      
      // Close modal
      closeLoginModal();
      
      // Reload personalized products
      loadBestSellingProducts();
      
      // Show personalized welcome message with order history
      showPersonalizedWelcome(data);
      
      // Clear login form
      emailInput.value = "";
      passwordInput.value = "";
      
    } else {
      throw new Error(data.error || "Login failed");
    }
    
  } catch (error) {
    console.error("Login error:", error);
    showNotification(error.message || "Login failed. Please try again.", "error");
  } finally {
    // Reset button
    submitBtn.disabled = false;
    submitBtn.innerHTML = originalText;
  }
}

/**
 * User Menu Functions
 */
function toggleUserMenu() {
  const dropdown = document.getElementById("user-menu-dropdown");
  const isHidden = dropdown.classList.contains("hidden");
  
  if (isHidden) {
    dropdown.classList.remove("hidden");
    setTimeout(() => {
      dropdown.classList.remove("opacity-0", "translate-y-2");
    }, 10);
  } else {
    closeUserMenu();
  }
}

function closeUserMenu() {
  const dropdown = document.getElementById("user-menu-dropdown");
  dropdown.classList.add("opacity-0", "translate-y-2");
  setTimeout(() => {
    dropdown.classList.add("hidden");
  }, 300);
}

/**
 * Order History Functions
 */
async function viewOrderHistory() {
  closeUserMenu();
  
  const section = document.getElementById("order-history-section");
  const loading = document.getElementById("order-loading");
  const noOrders = document.getElementById("no-orders");
  const table = document.getElementById("orders-table");
  
  // Show section
  section.classList.remove("hidden");
  section.scrollIntoView({ behavior: 'smooth' });
  
  // Show loading
  loading.classList.remove("hidden");
  noOrders.classList.add("hidden");
  table.classList.add("hidden");
  
  try {
    // Fetch order history
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        query: `show my order history`,
        customer_id: currentUser.email 
      }),
    });
    
    const data = await response.json();
    console.log('Order history data:', data);
    
    // Hide loading
    loading.classList.add("hidden");
    
    if (data.response_type === 'order_history' && data.orders_data && data.orders_data.length > 0) {
      displayOrdersInTable(data.orders_data);
    } else {
      noOrders.classList.remove("hidden");
    }
    
  } catch (error) {
    console.error("Error fetching order history:", error);
    loading.classList.add("hidden");
    noOrders.classList.remove("hidden");
    showNotification("Failed to load order history", "error");
  }
}

function displayOrdersInTable(orders) {
  const table = document.getElementById("orders-table");
  const tbody = document.getElementById("orders-table-body");
  
  tbody.innerHTML = '';
  
  orders.forEach((order, index) => {
    const imageUrl = order.image_url || 'https://via.placeholder.com/80';
    const productName = order.product_name || 'Unknown Product';
    const price = order.total_price ? `£${parseFloat(order.total_price).toFixed(2)}` : 'N/A';
    const orderDate = order.order_date ? new Date(order.order_date).toLocaleDateString('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric'
    }) : 'N/A';
    const orderStatus = order.order_status || 'N/A';
    const orderId = order.order_id || 'N/A';
    
    // Status badge colors
    let statusColor = 'bg-gray-100 text-gray-800';
    if (orderStatus.toLowerCase() === 'open') statusColor = 'bg-blue-100 text-blue-800';
    else if (orderStatus.toLowerCase() === 'approved') statusColor = 'bg-green-100 text-green-800';
    else if (orderStatus.toLowerCase() === 'ready') statusColor = 'bg-yellow-100 text-yellow-800';
    else if (orderStatus.toLowerCase() === 'shipped') statusColor = 'bg-indigo-100 text-indigo-800';
    else if (orderStatus.toLowerCase() === 'delivered') statusColor = 'bg-green-100 text-green-800';
    
    // Alternating row colors
    const rowBg = index % 2 === 0 ? 'bg-white' : 'bg-gray-50';
    
    const row = document.createElement('tr');
    row.className = `${rowBg} hover:bg-purple-50 transition-colors duration-150`;
    row.innerHTML = `
      <td class="px-6 py-4 whitespace-nowrap">
        <div class="text-sm font-bold text-purple-600">#${orderId}</div>
      </td>
      <td class="px-6 py-4">
        <div class="text-sm font-medium text-gray-900 max-w-xs">${productName}</div>
      </td>
      <td class="px-6 py-4 whitespace-nowrap">
        <img src="${imageUrl}" alt="${productName}" 
             class="h-16 w-16 object-cover rounded-lg shadow-sm border border-gray-200"
             onerror="this.src='https://via.placeholder.com/80'">
      </td>
      <td class="px-6 py-4 whitespace-nowrap">
        <div class="text-sm text-gray-900">
          <i class="far fa-calendar text-gray-400 mr-1"></i>
          ${orderDate}
        </div>
      </td>
      <td class="px-6 py-4 whitespace-nowrap">
        <span class="px-3 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${statusColor}">
          ${orderStatus}
        </span>
      </td>
      <td class="px-6 py-4 whitespace-nowrap">
        <div class="text-lg font-bold text-green-600">${price}</div>
      </td>
    `;
    
    tbody.appendChild(row);
  });


// ═══════════════════════════════════════════════════════════════════════════
// 👗 OUTFIT BUILDER / "Complete the Look"  — A2UI powered
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Called by addToCart() after a successful cart-add.
 * Sends the product to the backend outfit-builder endpoint which
 * computes complement sections and pushes them via A2UI WebSocket.
 */
async function loadOutfitBuilderViaA2UI(productId, productName) {
  console.log('👗 Outfit Builder triggered for:', productId, productName);

  if (!productId) return;

  const sessionId = window.a2uiSessionId || 'default_session';

  // Make the outfit section visible and show loading
  const section = document.getElementById('outfit-builder-section');
  if (section) {
    section.classList.remove('hidden');
    // Clear previous results
    const container = document.getElementById('outfit-builder-container');
    if (container) container.innerHTML = '';
    const subtitle = document.getElementById('outfit-builder-subtitle');
    if (subtitle) subtitle.textContent = `Perfect pairings for "${productName}"`;
  }

  try {
    const response = await fetch('/api/outfit-builder-a2ui', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        product_id:   productId,
        product_name: productName,
        session_id:   sessionId
      })
    });
    const result = await response.json();
    console.log('👗 Outfit builder API response:', result);

    if (result.success && result.data && result.data.length > 0) {
      // Render directly from API response — do not wait for A2UI WebSocket
      renderOutfitBuilder({
        cart_product_id:   productId,
        cart_product_name: productName,
        sections:          result.data,
        total_sections:    result.data.length
      });
    } else {
      console.warn('⚠️ Outfit builder: no sections found', result.error || '');
      if (section) section.classList.add('hidden');
    }
  } catch (err) {
    console.error('❌ Outfit builder error:', err);
    if (section) section.classList.add('hidden');
  }
}

/**
 * Renders the "Complete the Look" panel from the A2UI WebSocket payload.
 * data = { cart_product_name, sections: [ { complement_label, complement_category, products: [...] } ] }
 */
function renderOutfitBuilder(data) {
  console.log('👗 renderOutfitBuilder called:', data);

  const section   = document.getElementById('outfit-builder-section');
  const container = document.getElementById('outfit-builder-container');
  const subtitle  = document.getElementById('outfit-builder-subtitle');

  if (!container) return;

  const sections = data.sections || [];

  if (!sections.length) {
    if (section) section.classList.add('hidden');
    return;
  }

  if (subtitle) subtitle.textContent = `Perfect pairings for "${data.cart_product_name || 'your item'}"`;

  let html = '';
  sections.forEach(sec => {
    const products = sec.products || [];
    if (!products.length) return;

    html += `
      <div class="mb-4">
        <div class="flex items-center mb-2 px-1">
          <span class="text-xs font-semibold uppercase tracking-widest text-purple-600 mr-2">${escapeHtml(sec.complement_label)}</span>
          <div class="flex-1 h-px bg-gradient-to-r from-purple-200 to-transparent"></div>
        </div>
        <div class="flex gap-3 overflow-x-auto pb-2 custom-scrollbar">
          ${products.map(p => renderOutfitCard(p)).join('')}
        </div>
      </div>`;
  });

  container.innerHTML = html;
  if (section) section.classList.remove('hidden');

  // Smooth scroll to outfit section
  setTimeout(() => section && section.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 200);
}

/** Render a single outfit complement card */
function renderOutfitCard(p) {
  const hasDiscount = p.discount_pct > 0;
  const priceHtml = hasDiscount
    ? `<span class="line-through text-gray-400 text-xs">£${Number(p.price).toFixed(2)}</span>
       <span class="text-green-600 font-bold text-sm ml-1">£${Number(p.final_price).toFixed(2)}</span>
       <span class="ml-1 bg-red-100 text-red-600 text-xs px-1 rounded">-${Math.round(p.discount_pct)}%</span>`
    : `<span class="text-purple-700 font-bold text-sm">£${Number(p.final_price || p.price).toFixed(2)}</span>`;

  const img = p.image_url
    ? `<img src="${escapeHtml(p.image_url)}" alt="${escapeHtml(p.product_name)}"
            class="w-full h-28 object-cover rounded-t-xl"
            onerror="this.src='/static/assets/placeholder.png'">`
    : `<div class="w-full h-28 bg-gradient-to-br from-purple-100 to-pink-100 rounded-t-xl flex items-center justify-center">
         <i class="fas fa-tshirt text-3xl text-purple-300"></i></div>`;

  return `
    <div class="outfit-card flex-shrink-0 w-36 bg-white rounded-xl shadow hover:shadow-md transition-all duration-200 cursor-pointer border border-gray-100 hover:border-purple-300"
         onclick="openProductDetail('${escapeHtml(p.product_id)}')">
      ${img}
      <div class="p-2">
        <p class="text-xs font-medium text-gray-800 leading-tight line-clamp-2 mb-1">${escapeHtml(p.product_name)}</p>
        <div class="flex flex-wrap items-center gap-1">${priceHtml}</div>
        ${p.promo_title ? `<p class="text-xs text-orange-500 mt-1 truncate">🔥 ${escapeHtml(p.promo_title)}</p>` : ''}
        <button onclick="event.stopPropagation(); addToCart('${escapeHtml(p.product_id)}', '${escapeHtml(p.product_name).replace(/'/g,"\\'")}', event)"
                class="mt-2 w-full text-xs py-1 rounded-lg bg-gradient-to-r from-purple-500 to-pink-500 text-white hover:from-purple-600 hover:to-pink-600 transition-all font-medium">
          + Cart
        </button>
      </div>
    </div>`;
}

/** Simple HTML escape helper (if not already defined) */
// Note: escapeHtml is already defined at the top of this file
// ═══════════════════════════════════════════════════════════ end outfit builder

  
  table.classList.remove("hidden");
}

function closeOrderHistory() {
  const section = document.getElementById("order-history-section");
  section.classList.add("hidden");
}

// Add performance monitoring
window.addEventListener('load', function() {
  console.log('🚀 AI Shopping Assistant loaded successfully!');
  showNotification("Welcome! I'm ready to help you shop smarter.", "info");
  
  // Add login form event listeners
  const loginFormElement = document.getElementById("login-form-element");
  if (loginFormElement) {
    loginFormElement.addEventListener("submit", handleLogin);
  }
  
  const loginModalForm = document.getElementById("login-modal-form");
  if (loginModalForm) {
    loginModalForm.addEventListener("submit", handleModalLogin);
  }
  
  // Close user menu when clicking outside
  document.addEventListener('click', function(event) {
    const userMenuDropdown = document.getElementById('user-menu-dropdown');
    const userInfoBtn = document.getElementById('user-info-btn');
    
    if (userMenuDropdown && !userMenuDropdown.classList.contains('hidden')) {
      if (!userMenuDropdown.contains(event.target) && !userInfoBtn.contains(event.target)) {
        closeUserMenu();
      }
    }
  });
  
  // Close login modal when clicking outside
  const loginModal = document.getElementById('login-modal');
  if (loginModal) {
    loginModal.addEventListener('click', function(event) {
      if (event.target === loginModal) {
        closeLoginModal();
      }
    });
  }
});

/**
 * 🔗 PRODUCT DETAILS WITH CROSS-SELL
 * Sends a product details request to the agent when user clicks on a product card
 * The agent will return detailed product view with cross-sell products
 */
async function showProductDetails(productId) {
  console.log('🔍 showProductDetails called for product:', productId);
  
  if (!productId) {
    console.error('❌ Product ID is required');
    return;
  }
  
  // Show user message
  appendMessage(`Show me details of product ${productId}`, "user");
  showTypingIndicator();
  
  try {
    // Use logged-in user's email if available
    const customerEmail = isLoggedIn ? currentUser.email : "";
    
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        query: `Show me detailed information about product ${productId}`, 
        customer_id: customerEmail 
      }),
    });

    const data = await response.json();
    removeTypingIndicator();
    
    console.log('📦 Product details response:', data);
    console.log('📦 Response type:', data.response_type);
    console.log('📦 Product data:', data.product_data);
    
    // Display product details and trigger A2UI cross-sell below chat window
    if (data && data.response) {
      appendBotMessage(data);
      
      // Trigger A2UI cross-sell display
      loadCrossSellViaA2UI(productId);
    } else {
      appendBotMessage({
        response: 'Sorry, I could not retrieve product details. Please try again.'
      });
    }
    
  } catch (error) {
    console.error('❌ Error fetching product details:', error);
    removeTypingIndicator();
    appendBotMessage({
      response: 'Sorry, there was an error retrieving product details. Please try again.'
    });
  }
}

/**
 * Load cross-sell products via A2UI Protocol
 */
async function loadCrossSellViaA2UI(productId) {
  console.log('🔗 Loading cross-sell products via A2UI for product:', productId);
  console.log('📊 A2UI Session ID:', window.a2uiSessionId);
  console.log('📊 A2UI Client:', window.a2uiClient);
  console.log('📊 Cross-Sell Handler:', window.crossSellHandler);
  
  if (!productId) {
    console.error('❌ Product ID required for cross-sell');
    return;
  }
  
  // Check if A2UI is initialized
  if (!window.a2uiSessionId) {
    console.error('❌ A2UI not initialized! Session ID is missing.');
    console.log('⚠️ Attempting to initialize A2UI now...');
    if (typeof initializeA2UI === 'function') {
      initializeA2UI();
      // Wait a bit for initialization
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }
  
  // Show cross-sell section and loading state
  const crossSellSection = document.getElementById('crosssell-a2ui-section');
  console.log('📦 Cross-sell section element:', crossSellSection);
  
  if (crossSellSection) {
    crossSellSection.classList.remove('hidden');
    console.log('✅ Cross-sell section made visible');
  } else {
    console.error('❌ Cross-sell section not found in DOM!');
  }
  
  try {
    const requestPayload = {
      product_id: productId,
      session_id: window.a2uiSessionId || 'default_session'
    };
    
    console.log('📤 Sending request to /api/crosssell-a2ui:', requestPayload);
    
    // Call A2UI endpoint
    const response = await fetch('/api/crosssell-a2ui', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestPayload)
    });
    
    console.log('📥 Response status:', response.status, response.statusText);
    
    const result = await response.json();
    console.log('✅ Cross-sell A2UI response:', result);
    
    if (result.success) {
      console.log(`✅ ${result.count} cross-sell products sent via A2UI`);
      if (result.count === 0) {
        console.log('ℹ️ No cross-sell products available for this product');
      }
    } else {
      console.error('❌ Cross-sell A2UI failed:', result.error);
    }
    
  } catch (error) {
    console.error('❌ Error loading cross-sell via A2UI:', error);
    console.error('Stack trace:', error.stack);
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// ✨  AI PERSONAL STYLIST
// ═══════════════════════════════════════════════════════════════════════════════

/** State for the active stylist session */
const _stylistState = {
  sessionId:   null,
  cartProduct: null,
  step:        0,
};

const STYLIST_STEP_LABELS = [
  '', 'Occasion', 'Colour Palette', 'Fit Style', 'Budget', 'Your Outfit'
];

/**
 * Called after a successful addToCart().
 * Shows a gentle invitation bubble in the chat so the user can optionally
 * open the AI Stylist — no disruption to existing flow.
 */
function triggerStylistInvitation(productId, productName, price) {
  const chatBox = document.getElementById('chat-box');
  if (!chatBox) return;

  // Remove any previous invitation to avoid duplicates
  const prev = document.getElementById('stylist-invitation-bubble');
  if (prev) prev.remove();

  const bubble = document.createElement('div');
  bubble.id = 'stylist-invitation-bubble';
  bubble.className = 'flex justify-start animate-slide-up';
  bubble.innerHTML = `
    <div class="chat-bubble-bot p-4 max-w-sm shadow-lg rounded-2xl"
         style="border-left: 4px solid #7c3aed;">
      <div class="flex items-start space-x-3">
        <div class="w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0"
             style="background: linear-gradient(135deg,#7c3aed,#db2777);">
          <i class="fas fa-magic text-white text-sm"></i>
        </div>
        <div>
          <p class="text-gray-800 text-sm font-medium mb-2">
            Want a complete outfit to go with <strong>${productName}</strong>? ✨
          </p>
          <button onclick="openStylistModal('${productId}','${productName.replace(/'/g,"\\'")}',${price})"
                  class="px-4 py-1.5 rounded-full text-white text-xs font-semibold shadow"
                  style="background: linear-gradient(135deg,#7c3aed,#db2777);">
            Style Me! ✨
          </button>
        </div>
      </div>
    </div>`;
  chatBox.appendChild(bubble);
  chatBox.scrollTop = chatBox.scrollHeight;
}

/**
 * Opens the stylist modal and starts the conversation from step 1.
 */
async function openStylistModal(productId, productName, price) {
  _stylistState.sessionId   = (window.a2uiSessionId || 'default') + '_stylist_' + Date.now();
  _stylistState.cartProduct = { product_id: productId, product_name: productName, price: price };
  _stylistState.step        = 0;

  // Reset modal UI
  const modal = document.getElementById('stylist-modal');
  document.getElementById('stylist-chat-box').innerHTML    = '';
  document.getElementById('stylist-options').innerHTML     = '';
  document.getElementById('stylist-outfit-results').classList.add('hidden');
  document.getElementById('stylist-outfit-grid').innerHTML = '';
  document.getElementById('stylist-input-row').classList.add('hidden');
  document.getElementById('stylist-modal-subtitle').textContent = `Styling your look with ${productName}`;
  _updateStylistProgress(0);

  modal.classList.remove('hidden');
  modal.classList.add('flex');

  // Kick off the conversation
  try {
    const res = await fetch('/api/stylist-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action:       'start',
        session_id:   _stylistState.sessionId,
        cart_product: _stylistState.cartProduct,
      }),
    });
    const data = await res.json();
    _handleStylistResponse(data);
  } catch (err) {
    console.error('Stylist error:', err);
    _appendStylistMessage('Sorry, I ran into an issue. Please try again later.', 'bot');
  }
}

function closeStylistModal() {
  const modal = document.getElementById('stylist-modal');
  modal.classList.add('hidden');
  modal.classList.remove('flex');
}

/**
 * Sends the user's choice (option button or free text) to the backend.
 */
async function sendStylistMessage(text) {
  if (!text || !text.trim()) return;
  const input = document.getElementById('stylist-text-input');
  if (input) input.value = '';

  _appendStylistMessage(text, 'user');
  document.getElementById('stylist-options').innerHTML = '';
  document.getElementById('stylist-input-row').classList.add('hidden');

  // Typing indicator
  const typingId = _showStylistTyping();

  try {
    const res = await fetch('/api/stylist-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action:     'chat',
        session_id: _stylistState.sessionId,
        message:    text,
      }),
    });
    const data = await res.json();
    _removeStylistTyping(typingId);
    _handleStylistResponse(data);
  } catch (err) {
    _removeStylistTyping(typingId);
    _appendStylistMessage('Something went wrong. Please try again.', 'bot');
  }
}

/** Processes a response from /api/stylist-chat */
function _handleStylistResponse(data) {
  if (data.error) {
    _appendStylistMessage('Sorry, something went wrong: ' + data.error, 'bot');
    return;
  }

  _stylistState.step = data.step || _stylistState.step;
  _updateStylistProgress(data.step);

  // Update subtitle
  const label = STYLIST_STEP_LABELS[data.step] || '';
  if (label) {
    document.getElementById('stylist-modal-subtitle').textContent = `Step ${data.step}/4 — ${label}`;
  }

  _appendStylistMessage(data.message || '', 'bot');

  if (data.done) {
    _renderStylistOutfit(data.outfit_products || []);
  } else {
    if (data.options && data.options.length > 0) {
      const optBox = document.getElementById('stylist-options');
      optBox.innerHTML = '';
      data.options.forEach(opt => {
        const btn = document.createElement('button');
        btn.textContent = opt;
        btn.className = 'px-3 py-1.5 rounded-full border text-xs font-medium transition-colors';
        btn.style.cssText = 'border-color:#7c3aed; color:#7c3aed;';
        btn.onmouseover = () => { btn.style.background = '#7c3aed'; btn.style.color = '#fff'; };
        btn.onmouseout  = () => { btn.style.background = 'transparent'; btn.style.color = '#7c3aed'; };
        btn.onclick     = () => sendStylistMessage(opt);
        optBox.appendChild(btn);
      });
    }
  }
}

/** Renders the final outfit product grid */
function _renderStylistOutfit(products) {
  const resultsDiv = document.getElementById('stylist-outfit-results');
  const grid       = document.getElementById('stylist-outfit-grid');
  grid.innerHTML   = '';

  if (!products || products.length === 0) {
    grid.innerHTML = '<p class="col-span-2 text-sm text-gray-500 text-center py-4">No matching products found for your preferences.</p>';
  } else {
    products.forEach(p => {
      const imgSrc   = p.image_url || '/static/assets/placeholder-image.png';
      const price    = p.price ? `£${p.price.toFixed(2)}` : '';
      const origPr   = (p.has_promotion && p.original_price)
                       ? `<span class="line-through text-gray-400 text-xs mr-1">£${p.original_price.toFixed(2)}</span>` : '';
      const catBadge = p.category
        ? `<span class="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-600 capitalize">${p.category}</span>` : '';
      const safeName = (p.product_name || '').replace(/'/g, "\\'");

      grid.innerHTML += `
        <div class="border border-gray-200 rounded-2xl overflow-hidden flex flex-col shadow-sm hover:shadow-md transition-shadow">
          <img src="${imgSrc}" alt="${p.product_name}"
               class="w-full object-cover" style="height:120px;"
               onerror="this.src='/static/assets/placeholder-image.png'">
          <div class="p-2 flex flex-col gap-1 flex-1">
            ${catBadge}
            <p class="text-xs font-semibold text-gray-800 leading-tight"
               style="display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">
              ${p.product_name}
            </p>
            <p class="text-xs text-gray-500">${origPr}<span class="font-bold text-green-600">${price}</span></p>
            <button onclick="addToCart('${p.product_id}','${safeName}',null,false)"
                    class="mt-auto w-full py-1.5 rounded-lg text-white text-xs font-semibold"
                    style="background: linear-gradient(135deg,#7c3aed,#db2777);">
              Add to Cart
            </button>
          </div>
        </div>`;
    });
  }

  resultsDiv.classList.remove('hidden');
  document.getElementById('stylist-modal-subtitle').textContent = 'Your complete look is ready! 🎉';
  _updateStylistProgress(5);
}

/** Appends a message bubble inside the stylist chat box */
function _appendStylistMessage(text, sender) {
  const box = document.getElementById('stylist-chat-box');
  if (!box) return;
  const html = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>');
  const div  = document.createElement('div');
  if (sender === 'user') {
    div.className = 'flex justify-end';
    div.innerHTML = `
      <div class="px-4 py-2 rounded-2xl rounded-tr-sm text-sm text-white max-w-xs"
           style="background: linear-gradient(135deg,#7c3aed,#db2777);">${html}</div>`;
  } else {
    div.className = 'flex justify-start';
    div.innerHTML = `
      <div class="flex items-start space-x-2">
        <div class="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center"
             style="background: linear-gradient(135deg,#7c3aed,#db2777);">
          <i class="fas fa-magic text-white" style="font-size:10px;"></i>
        </div>
        <div class="px-4 py-2 rounded-2xl rounded-tl-sm bg-gray-100 text-sm text-gray-800 max-w-xs">${html}</div>
      </div>`;
  }
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function _showStylistTyping() {
  const id  = 'st-typing-' + Date.now();
  const box = document.getElementById('stylist-chat-box');
  if (!box) return id;
  const div = document.createElement('div');
  div.id        = id;
  div.className = 'flex justify-start';
  div.innerHTML = `
    <div class="flex items-start space-x-2">
      <div class="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center"
           style="background: linear-gradient(135deg,#7c3aed,#db2777);">
        <i class="fas fa-magic text-white" style="font-size:10px;"></i>
      </div>
      <div class="px-4 py-2 rounded-2xl bg-gray-100 text-sm text-gray-500">
        <i class="fas fa-spinner fa-spin mr-1"></i> Thinking…
      </div>
    </div>`;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
  return id;
}

function _removeStylistTyping(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function _updateStylistProgress(step) {
  const pct = Math.min(100, Math.round((step / 5) * 100));
  const bar = document.getElementById('stylist-progress-bar');
  if (bar) bar.style.width = pct + '%';
}