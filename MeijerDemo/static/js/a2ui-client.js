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
        
        // Call registered handlers
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

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = A2UIClient;
}
