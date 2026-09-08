/**
 * A2UI Protocol Client Library
 * Handles WebSocket communication with A2UI Protocol Server
 * Provides real-time UI updates and bidirectional communication
 */

class A2UIClient {
    constructor(config = {}) {
        this.config = {
            serverUrl: config.serverUrl || 'ws://localhost:8020',
            reconnectInterval: config.reconnectInterval || 3000,
            maxReconnectAttempts: config.maxReconnectAttempts || 5,
            heartbeatInterval: config.heartbeatInterval || 30000,
            debug: config.debug || false,
            ...config
        };
        
        this.ws = null;
        this.sessionId = this.generateSessionId();
        this.reconnectAttempts = 0;
        this.isConnected = false;
        this.subscribedModules = new Set();
        this.messageHandlers = new Map();
        this.moduleHandlers = new Map();
        this.heartbeatTimer = null;
        
        // Event listeners
        this.onConnectCallbacks = [];
        this.onDisconnectCallbacks = [];
        this.onErrorCallbacks = [];
        
        this.log('A2UI Client initialized', { sessionId: this.sessionId });
    }
    
    /**
     * Get the session ID
     */
    getSessionId() {
        return this.sessionId;
    }
    
    /**
     * Generate unique session ID
     */
    generateSessionId() {
        return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    /**
     * Connect to A2UI server
     */
    connect() {
        if (this.ws && this.isConnected) {
            this.log('Already connected');
            return;
        }
        
        const wsUrl = `${this.config.serverUrl}/ws/${this.sessionId}`;
        this.log('Connecting to A2UI server...', { url: wsUrl });
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => this.handleOpen();
            this.ws.onmessage = (event) => this.handleMessage(event);
            this.ws.onerror = (error) => this.handleError(error);
            this.ws.onclose = () => this.handleClose();
            
        } catch (error) {
            this.log('Connection error', error, 'error');
            this.handleError(error);
        }
    }
    
    /**
     * Disconnect from server
     */
    disconnect() {
        this.log('Disconnecting...');
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
        }
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.isConnected = false;
    }
    
    /**
     * Subscribe to modules
     */
    subscribe(modules) {
        if (!Array.isArray(modules)) {
            modules = [modules];
        }
        
        modules.forEach(module => this.subscribedModules.add(module));
        
        if (this.isConnected) {
            this.send({
                type: 'subscribe',
                modules: Array.from(this.subscribedModules)
            });
        }
        
        this.log('Subscribed to modules', { modules });
    }
    
    /**
     * Register message handler for specific component
     */
    on(component, handler) {
        if (!this.messageHandlers.has(component)) {
            this.messageHandlers.set(component, []);
        }
        this.messageHandlers.get(component).push(handler);
        
        this.log('Handler registered', { component });
    }
    
    /**
     * Register module handler (convenience method)
     * Routes all messages from a module to a single handler
     */
    registerModule(moduleName, handler) {
        // Store module handler
        if (!this.moduleHandlers) {
            this.moduleHandlers = new Map();
        }
        this.moduleHandlers.set(moduleName, handler);
        
        // Subscribe to the module
        this.subscribe(moduleName);
        
        this.log('Module handler registered', { moduleName });
    }
    
    /**
     * Register connection callback
     */
    onConnect(callback) {
        this.onConnectCallbacks.push(callback);
    }
    
    /**
     * Register disconnection callback
     */
    onDisconnect(callback) {
        this.onDisconnectCallbacks.push(callback);
    }
    
    /**
     * Register error callback
     */
    onError(callback) {
        this.onErrorCallbacks.push(callback);
    }
    
    /**
     * Send message to server
     */
    send(data) {
        if (!this.isConnected) {
            this.log('Not connected, cannot send message', null, 'warn');
            return false;
        }
        
        try {
            this.ws.send(JSON.stringify(data));
            return true;
        } catch (error) {
            this.log('Error sending message', error, 'error');
            return false;
        }
    }
    
    /**
     * Send event to server
     */
    sendEvent(module, event, data) {
        return this.send({
            type: 'event',
            module,
            event,
            data
        });
    }
    
    /**
     * Handle WebSocket open
     */
    handleOpen() {
        this.log('✅ Connected to A2UI server');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        
        // Update connection status in UI
        this.updateConnectionStatus(true);
        
        // Subscribe to modules
        if (this.subscribedModules.size > 0) {
            this.send({
                type: 'subscribe',
                modules: Array.from(this.subscribedModules)
            });
        }
        
        // Start heartbeat
        this.startHeartbeat();
        
        // Call connect callbacks
        this.onConnectCallbacks.forEach(callback => {
            try {
                callback();
            } catch (error) {
                this.log('Error in connect callback', error, 'error');
            }
        });
    }
    
    /**
     * Handle incoming message
     */
    handleMessage(event) {
        try {
            const message = JSON.parse(event.data);
            this.log('📨 Message received', message);
            
            // Handle different message types
            switch (message.type) {
                case 'connection_established':
                    this.handleConnectionEstablished(message);
                    break;
                    
                case 'ui_update':
                    this.handleUIUpdate(message);
                    break;
                    
                case 'ui_command':
                    this.handleUICommand(message);
                    break;
                    
                case 'subscription_confirmed':
                    this.log('✅ Subscription confirmed', message.modules);
                    break;
                    
                case 'pong':
                    // Heartbeat response
                    break;
                    
                default:
                    this.log('Unknown message type', message.type, 'warn');
            }
            
        } catch (error) {
            this.log('Error handling message', error, 'error');
        }
    }
    
    /**
     * Handle UI update messages
     */
    handleUIUpdate(message) {
        const { module, action, component, data, metadata } = message;
        
        console.log('📨 handleUIUpdate called');
        console.log('   Module:', module);
        console.log('   Action:', action);
        console.log('   Component:', component);
        console.log('   Module Handlers available:', Array.from(this.moduleHandlers?.keys() || []));
        
        // Call module handlers first (if registered)
        if (this.moduleHandlers && this.moduleHandlers.has(module)) {
            try {
                console.log(`✅ Found module handler for: ${module}`);
                const moduleHandler = this.moduleHandlers.get(module);
                moduleHandler(action, component, data, message);
            } catch (error) {
                this.log('Error in module handler', error, 'error');
                console.error('Module handler error:', error);
            }
        } else {
            console.warn(`⚠️ No module handler found for: ${module}`);
        }
        
        // Call component-specific handlers
        if (this.messageHandlers.has(component)) {
            this.messageHandlers.get(component).forEach(handler => {
                try {
                    handler({ action, data, metadata, module });
                } catch (error) {
                    this.log('Error in message handler', error, 'error');
                }
            });
        }
        
        // Emit custom event
        const customEvent = new CustomEvent('a2ui-update', {
            detail: { module, action, component, data, metadata }
        });
        window.dispatchEvent(customEvent);
    }
    
    /**
     * Handle UI command messages
     */
    handleUICommand(message) {
        const { command, params, module } = message;
        
        this.log('🎯 UI Command', { command, params });
        
        // Execute command
        switch (command) {
            case 'show_toast':
                this.showToast(params.message, params.type, params.duration);
                break;
                
            case 'show_modal':
                this.showModal(params);
                break;
                
            case 'navigate':
                this.navigate(params.url);
                break;
                
            case 'scroll_to':
                this.scrollTo(params.element);
                break;
                
            case 'refresh':
                this.refresh(params.component);
                break;
                
            default:
                this.log('Unknown command', command, 'warn');
        }
        
        // Emit custom event
        const customEvent = new CustomEvent('a2ui-command', {
            detail: { command, params, module }
        });
        window.dispatchEvent(customEvent);
    }
    
    /**
     * Handle connection established
     */
    handleConnectionEstablished(message) {
        this.log('Connection established', message);
    }
    
    /**
     * Handle WebSocket error
     */
    handleError(error) {
        this.log('WebSocket error', error, 'error');
        
        this.onErrorCallbacks.forEach(callback => {
            try {
                callback(error);
            } catch (err) {
                this.log('Error in error callback', err, 'error');
            }
        });
    }
    
    /**
     * Handle WebSocket close
     */
    handleClose() {
        this.log('❌ Disconnected from A2UI server');
        this.isConnected = false;
        
        // Update connection status in UI
        this.updateConnectionStatus(false);
        
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
        }
        
        this.onDisconnectCallbacks.forEach(callback => {
            try {
                callback();
            } catch (error) {
                this.log('Error in disconnect callback', error, 'error');
            }
        });
        
        // Attempt reconnection
        this.attemptReconnect();
    }
    
    /**
     * Attempt to reconnect
     */
    attemptReconnect() {
        if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
            this.log('Max reconnection attempts reached', null, 'error');
            return;
        }
        
        this.reconnectAttempts++;
        this.log(`Reconnecting... (attempt ${this.reconnectAttempts}/${this.config.maxReconnectAttempts})`);
        
        setTimeout(() => {
            this.connect();
        }, this.config.reconnectInterval);
    }
    
    /**
     * Start heartbeat
     */
    startHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
        }
        
        this.heartbeatTimer = setInterval(() => {
            if (this.isConnected) {
                this.send({ type: 'ping' });
            }
        }, this.config.heartbeatInterval);
    }
    
    /**
     * Show toast notification
     */
    showToast(message, type = 'info', duration = 3000) {
        // Check if toast container exists
        let container = document.getElementById('a2ui-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'a2ui-toast-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
            `;
            document.body.appendChild(container);
        }
        
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `a2ui-toast a2ui-toast-${type}`;
        toast.style.cssText = `
            background: ${this.getToastColor(type)};
            color: white;
            padding: 12px 20px;
            margin-bottom: 10px;
            border-radius: 4px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            animation: slideIn 0.3s ease-out;
            min-width: 250px;
        `;
        toast.textContent = message;
        
        container.appendChild(toast);
        
        // Auto remove
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    }
    
    /**
     * Get toast color based on type
     */
    getToastColor(type) {
        const colors = {
            success: '#10b981',
            error: '#ef4444',
            warning: '#f59e0b',
            info: '#3b82f6'
        };
        return colors[type] || colors.info;
    }
    
    /**
     * Show modal
     */
    showModal(params) {
        // Implement modal logic or emit event for app to handle
        const event = new CustomEvent('a2ui-show-modal', { detail: params });
        window.dispatchEvent(event);
    }
    
    /**
     * Navigate to URL
     */
    navigate(url) {
        window.location.href = url;
    }
    
    /**
     * Scroll to element
     */
    scrollTo(elementId) {
        const element = document.getElementById(elementId);
        if (element) {
            element.scrollIntoView({ behavior: 'smooth' });
        }
    }
    
    /**
     * Refresh component
     */
    refresh(component) {
        const event = new CustomEvent('a2ui-refresh', { detail: { component } });
        window.dispatchEvent(event);
    }
    
    /**
     * Update connection status indicator in UI
     */
    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('a2ui-connection-status');
        if (statusElement) {
            if (connected) {
                statusElement.textContent = 'Connected';
                statusElement.className = 'px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800';
            } else {
                statusElement.textContent = 'Disconnected';
                statusElement.className = 'px-3 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800';
            }
            this.log('Connection status updated', { connected });
        }
    }
    
    /**
     * Logging utility
     */
    log(message, data = null, level = 'info') {
        if (!this.config.debug && level === 'info') return;
        
        const prefix = '[A2UI]';
        const styles = {
            info: 'color: #3b82f6',
            warn: 'color: #f59e0b',
            error: 'color: #ef4444'
        };
        
        if (data) {
            console[level](`%c${prefix} ${message}`, styles[level], data);
        } else {
            console[level](`%c${prefix} ${message}`, styles[level]);
        }
    }
}

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

/**
 * Cross-Sell A2UI Module Handler
 * Handles real-time cross-sell product display via A2UI
 */
class CrossSellA2UIHandler {
    constructor() {
        this.containerSelector = '#crosssell-a2ui-container';
        this.loadingSelector = '#crosssell-a2ui-loading';
    }
    
    /**
     * Handle cross-sell module updates
     */
    handle(action, component, data, fullMessage) {
        console.log('🛍️ Cross-Sell A2UI Update:', { action, component, data });
        console.log('📋 Full A2UI JSON:', JSON.stringify(fullMessage, null, 2));
        
        // Log container status
        const container = document.querySelector(this.containerSelector);
        const section = document.getElementById('crosssell-a2ui-section');
        console.log('📦 Container element:', container);
        console.log('📦 Section element:', section);
        console.log('📦 Section hidden?:', section?.classList.contains('hidden'));
        
        switch (component) {
            case 'crosssell_loading':
                this.handleLoadingState(data);
                break;
                
            case 'crosssell_carousel':
                this.handleCrossSellProducts(data);
                break;
                
            case 'crosssell_error':
                this.handleError(data);
                break;
                
            default:
                console.warn(`⚠️ Unknown cross-sell component: ${component}`);
        }
    }
    
    /**
     * Handle loading state
     */
    handleLoadingState(data) {
        const { is_loading, message } = data;
        const loadingElement = document.querySelector(this.loadingSelector);
        
        if (loadingElement) {
            if (is_loading) {
                loadingElement.classList.remove('hidden');
                loadingElement.innerHTML = `
                    <div class="flex items-center justify-center gap-3 p-4">
                        <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                        <span class="text-gray-600">${message || 'Loading related products...'}</span>
                    </div>
                `;
            } else {
                loadingElement.classList.add('hidden');
            }
        }
    }
    
    /**
     * Handle cross-sell products display
     */
    handleCrossSellProducts(data) {
        const { products, product_id, total_count } = data;
        const container = document.querySelector(this.containerSelector);
        
        console.log(`📦 Displaying ${products.length} cross-sell products for ${product_id} via A2UI`);
        console.log('📊 Cross-Sell Products Data:', products);
        
        if (!container) {
            console.error('❌ Cross-sell container not found');
            return;
        }
        
        // Hide loading
        this.handleLoadingState({ is_loading: false });
        
        // Show cross-sell section
        const section = document.getElementById('crosssell-a2ui-section');
        if (section) {
            section.classList.remove('hidden');
        }
        
        if (products && products.length > 0) {
            // Build carousel HTML with scrollable layout
            const html = `
                <div class="relative bg-gradient-to-br from-white/80 to-white/60 rounded-2xl shadow-lg p-6 animate__animated animate__fadeInUp">
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center space-x-2">
                            <span class="text-sm text-blue-600 font-semibold bg-blue-50 px-3 py-1 rounded-full">
                                <i class="fas fa-robot mr-1"></i> Powered by A2UI
                            </span>
                            <span class="text-sm text-gray-500">${total_count} products</span>
                        </div>
                        <div class="flex space-x-2">
                            <button onclick="scrollCrossSellCarousel(-1)" 
                                    class="w-8 h-8 bg-white/80 hover:bg-white rounded-full flex items-center justify-center shadow-md transition-all hover:scale-110">
                                <i class="fas fa-chevron-left text-gray-600"></i>
                            </button>
                            <button onclick="scrollCrossSellCarousel(1)" 
                                    class="w-8 h-8 bg-white/80 hover:bg-white rounded-full flex items-center justify-center shadow-md transition-all hover:scale-110">
                                <i class="fas fa-chevron-right text-gray-600"></i>
                            </button>
                        </div>
                    </div>
                    
                    <!-- Carousel Container -->
                    <div class="relative overflow-hidden">
                        <div id="crosssell-carousel-track" class="flex space-x-4 overflow-x-auto scrollbar-hide scroll-smooth">
                            ${products.map(product => this.createCarouselCard(product)).join('')}
                        </div>
                    </div>
                </div>
            `;
            
            container.innerHTML = html;
            
            // Add click handlers
            this.attachEventHandlers(container);
            
        } else {
            console.log('ℹ️ No cross-sell products to display');
            container.innerHTML = '';
            if (section) {
                section.classList.add('hidden');
            }
        }
    }
    
    /**
     * Create carousel product card HTML
     */
    createCarouselCard(product) {
        const {
            product_id,
            PRODUCT_ID,
            product_name,
            PRODUCT_NAME,
            summary,
            SUMMARY,
            price,
            PRICE,
            original_price,
            discounted_price,
            discount_percent,
            has_promotion,
            promo_title,
            image_url,
            IMAGE_URL
        } = product;
        
        // Handle both lowercase and uppercase field names
        const id = product_id || PRODUCT_ID || '';
        const name = product_name || PRODUCT_NAME || 'Product';
        const desc = summary || SUMMARY || '';
        const img = image_url || IMAGE_URL || '/static/assets/placeholder.jpg';
        
        const displayPrice = discounted_price || price || PRICE || 0;
        const origPrice = original_price || price || PRICE || 0;
        const savings = origPrice - displayPrice;
        const hasDiscount = has_promotion && savings > 0;
        
        return `
            <div class="flex-shrink-0 w-72 bg-white rounded-xl shadow-md hover:shadow-2xl transition-all duration-300 overflow-hidden cursor-pointer crosssell-product-card transform hover:-translate-y-2" 
                 data-product-id="${id}">
                <div class="relative">
                    ${hasDiscount ? `
                        <div class="absolute top-3 right-3 z-10 flex flex-col gap-1">
                            <div class="bg-red-500 text-white px-3 py-1.5 rounded-full text-xs font-bold shadow-lg animate-pulse">
                                -${discount_percent}% OFF
                            </div>
                            <div class="bg-green-500 text-white px-3 py-1 rounded-full text-xs font-bold shadow-lg">
                                SALE
                            </div>
                        </div>
                    ` : ''}
                    <img src="${img}" 
                         alt="${name}"
                         class="w-full h-56 object-cover"
                         onerror="this.src='/static/assets/placeholder.jpg'">
                </div>
                <div class="p-4">
                    <h4 class="font-bold text-gray-800 mb-2 line-clamp-2 text-lg">
                        ${name}
                    </h4>
                    ${desc ? `
                        <p class="text-sm text-gray-600 mb-3 line-clamp-2">
                            ${desc}
                        </p>
                    ` : ''}
                    <div class="mt-4">
                        ${hasDiscount ? `
                            <div class="flex items-center justify-between mb-2">
                                <div>
                                    <div class="flex items-center gap-2">
                                        <span class="text-2xl font-bold text-red-600">
                                            £${displayPrice.toFixed(2)}
                                        </span>
                                        <span class="text-sm text-gray-400 line-through">
                                            £${origPrice.toFixed(2)}
                                        </span>
                                    </div>
                                    <div class="text-sm text-green-600 font-semibold mt-1">
                                        <i class="fas fa-tag mr-1"></i> Save £${savings.toFixed(2)}
                                    </div>
                                </div>
                            </div>
                        ` : `
                            <div class="text-2xl font-bold text-gray-800 mb-2">
                                £${displayPrice.toFixed(2)}
                            </div>
                        `}
                        <button class="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white px-4 py-2.5 rounded-lg font-medium transition-all duration-300 transform hover:scale-105 shadow-md">
                            <i class="fas fa-eye mr-2"></i> View Details
                        </button>
                    </div>
                </div>
            </div>
        `;
    }
    
    /**
     * Attach event handlers to product cards
     */
    attachEventHandlers(container) {
        const cards = container.querySelectorAll('.crosssell-product-card');
        cards.forEach(card => {
            card.addEventListener('click', (e) => {
                const productId = card.dataset.productId;
                console.log(`🔍 Cross-sell product clicked: ${productId}`);
                // Trigger product details view
                if (window.showProductDetails) {
                    window.showProductDetails(productId);
                } else if (window.loadProductDetails) {
                    window.loadProductDetails(productId);
                }
            });
        });
    }
    
    /**
     * Handle errors
     */
    handleError(data) {
        const { error_message } = data;
        const container = document.querySelector(this.containerSelector);
        
        console.error('❌ Cross-sell error:', error_message);
        
        if (container) {
            container.innerHTML = `
                <div class="p-4 bg-red-50 border border-red-200 rounded-lg">
                    <p class="text-red-600">
                        <i class="fas fa-exclamation-triangle mr-2"></i>
                        ${error_message}
                    </p>
                </div>
            `;
            container.classList.remove('hidden');
        }
        
        this.handleLoadingState({ is_loading: false });
    }
}

/**
 * Scroll cross-sell carousel
 */
function scrollCrossSellCarousel(direction) {
    const track = document.getElementById('crosssell-carousel-track');
    if (track) {
        const scrollAmount = 300; // Width of one card + gap
        track.scrollBy({
            left: direction * scrollAmount,
            behavior: 'smooth'
        });
    }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { A2UIClient, CrossSellA2UIHandler };
}
