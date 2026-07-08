/**
 * Enhanced main.js with A2UI Protocol Integration
 * Provides real-time UI updates for product search
 */

// Initialize A2UI Client
let a2uiClient = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Initializing A2UI Protocol...');
    
    // Create A2UI client
    a2uiClient = new A2UIClient({
        serverUrl: 'ws://localhost:8020',
        debug: true,
        reconnectInterval: 3000,
        maxReconnectAttempts: 5
    });
    
    // Setup event handlers
    setupA2UIHandlers();
    
    // Connect to server
    a2uiClient.connect();
    
    // Subscribe to product_search module
    a2uiClient.subscribe(['product_search', 'cart', 'checkout']);
    
    console.log('✅ A2UI Protocol initialized');
});

/**
 * Setup A2UI event handlers
 */
function setupA2UIHandlers() {
    // Handle product list updates
    a2uiClient.on('product_list', ({ action, data, metadata }) => {
        console.log('📦 Product list update', { action, data });
        
        if (action === 'replace') {
            displayProducts(data.products, data.query);
        } else if (action === 'append') {
            appendProducts(data.products);
        }
    });
    
    // Handle loading state updates
    a2uiClient.on('loading_state', ({ data }) => {
        console.log('⏳ Loading state update', data);
        
        const loadingDiv = document.getElementById('loading');
        if (loadingDiv) {
            if (data.is_loading) {
                loadingDiv.style.display = 'block';
                if (data.message) {
                    loadingDiv.innerHTML = `<div class="spinner"></div><p>${data.message}</p>`;
                }
            } else {
                loadingDiv.style.display = 'none';
            }
        }
    });
    
    // Handle error state updates
    a2uiClient.on('error_state', ({ data }) => {
        console.log('❌ Error state update', data);
        
        if (data.has_error) {
            showError(data.error_message, data.error_type);
        }
    });
    
    // Handle product details updates
    a2uiClient.on('product_details', ({ data }) => {
        console.log('🔍 Product details update', data);
        if (data.product) {
            displayProductDetails(data.product);
        }
    });
    
    // Connection status handlers
    a2uiClient.onConnect(() => {
        console.log('✅ Connected to A2UI server');
        showConnectionStatus('connected');
    });
    
    a2uiClient.onDisconnect(() => {
        console.log('❌ Disconnected from A2UI server');
        showConnectionStatus('disconnected');
    });
    
    a2uiClient.onError((error) => {
        console.error('🔴 A2UI error:', error);
        showConnectionStatus('error');
    });
}

/**
 * Submit search query with A2UI integration
 */
function submitQuery() {
    const queryValue = document.getElementById("query").value.trim();
    const responseDiv = document.getElementById("response");

    if (!queryValue) {
        alert("Please enter a query");
        return;
    }

    // Clear previous results
    responseDiv.innerHTML = "";
    
    // Send event to A2UI (optional - for analytics)
    if (a2uiClient && a2uiClient.isConnected) {
        a2uiClient.sendEvent('product_search', 'search_initiated', {
            query: queryValue,
            timestamp: new Date().toISOString()
        });
    }

    // Make API call (backend will send updates via A2UI)
    fetch("/api/query", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ 
            query: queryValue,
            session_id: a2uiClient ? a2uiClient.sessionId : null
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log("Response data:", data);
        
        // If A2UI is not connected, fall back to direct display
        if (!a2uiClient || !a2uiClient.isConnected) {
            handleStructuredResponse(data);
        }
        // Otherwise, A2UI handlers will update the UI
    })
    .catch(error => {
        console.error("Error:", error);
        showError("Error processing your query. Please try again.");
    });
}

/**
 * Display products in the UI
 */
function displayProducts(products, query = '') {
    const responseDiv = document.getElementById("response");
    
    if (!products || products.length === 0) {
        responseDiv.innerHTML = `
            <div class="no-results">
                <p>No products found${query ? ` for "${query}"` : ''}.</p>
                <p>Try a different search term.</p>
            </div>
        `;
        return;
    }
    
    let html = '';
    
    // Add search info
    if (query) {
        html += `
            <div class="search-info">
                <p>Found <strong>${products.length}</strong> products for "<strong>${query}</strong>"</p>
            </div>
        `;
    }
    
    // Create product grid
    html += '<div class="products-container" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-top: 20px;">';
    
    products.forEach(product => {
        html += createProductCard(product);
    });
    
    html += '</div>';
    
    responseDiv.innerHTML = html;
}

/**
 * Append products to existing list
 */
function appendProducts(products) {
    const container = document.querySelector('.products-container');
    if (!container) {
        displayProducts(products);
        return;
    }
    
    products.forEach(product => {
        const cardHtml = createProductCard(product);
        container.insertAdjacentHTML('beforeend', cardHtml);
    });
}

/**
 * Create product card HTML
 */
function createProductCard(product) {
    const imageUrl = product.image_url || '/static/assets/placeholder-image.png';
    const price = product.price ? `$${product.price.toFixed(2)}` : 'Price not available';
    const encodedProductName = encodeURIComponent(product.product_name || '');
    
    return `
        <div class="product-card" style="
            border: 1px solid #ddd; 
            border-radius: 8px; 
            padding: 16px; 
            background: white; 
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        " onmouseover="this.style.transform='translateY(-4px)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.15)';" 
           onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.1)';">
            
            <div class="product-image" style="text-align: center; margin-bottom: 12px;">
                <img src="${imageUrl}" alt="${product.product_name || 'Product'}" 
                     style="max-width: 100%; height: 200px; object-fit: cover; border-radius: 4px;" 
                     onerror="this.src='/static/assets/placeholder-image.png'">
            </div>
            
            <div class="product-info">
                <h3 style="margin: 0 0 8px 0; font-size: 18px; color: #333;">
                    ${product.product_name || 'Unknown Product'}
                </h3>
                
                ${product.summary ? `
                    <p style="color: #666; font-size: 14px; margin-bottom: 12px; line-height: 1.4;">
                        ${product.summary.substring(0, 100)}${product.summary.length > 100 ? '...' : ''}
                    </p>
                ` : ''}
                
                <div class="product-price" style="font-size: 20px; font-weight: bold; color: #2563eb; margin-bottom: 12px;">
                    ${price}
                </div>
                
                ${product.category_name ? `
                    <div class="product-category" style="font-size: 12px; color: #888; margin-bottom: 12px;">
                        Category: ${product.category_name}
                    </div>
                ` : ''}
                
                <div class="product-actions" style="display: flex; gap: 8px;">
                    <button onclick="viewProductDetails('${product.product_id}')" 
                            style="flex: 1; padding: 8px 16px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px;"
                            onmouseover="this.style.background='#2563eb'"
                            onmouseout="this.style.background='#3b82f6'">
                        View Details
                    </button>
                    
                    <button onclick="addToCart('${product.product_id}', '${encodedProductName}')" 
                            style="flex: 1; padding: 8px 16px; background: #00529B; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px;"
                            onmouseover="this.style.background='#003F7A'"
                            onmouseout="this.style.background='#00529B'">
                        Add to Cart
                    </button>
                </div>
            </div>
        </div>
    `;
}

/**
 * View product details
 */
function viewProductDetails(productId) {
    console.log('Viewing product:', productId);
    
    // Send event to A2UI
    if (a2uiClient && a2uiClient.isConnected) {
        a2uiClient.sendEvent('product_search', 'product_detail_view', {
            product_id: productId
        });
    }
    
    // Fetch product details
    fetch(`/api/product/${productId}`)
        .then(response => response.json())
        .then(data => {
            if (a2uiClient && a2uiClient.isConnected) {
                // Details will be updated via A2UI
                console.log('Product details received via API');
            } else {
                displayProductDetails(data);
            }
        })
        .catch(error => {
            console.error('Error fetching product details:', error);
            showError('Failed to load product details');
        });
}

/**
 * Display product details
 */
function displayProductDetails(product) {
    // Implement product details view
    console.log('Displaying product details:', product);
    // You can implement a modal or redirect to product page
}

/**
 * Add product to cart
 */
function addToCart(productId, productName) {
    console.log('Adding to cart:', productId);
    
    // Send event to A2UI
    if (a2uiClient && a2uiClient.isConnected) {
        a2uiClient.sendEvent('cart', 'add_to_cart', {
            product_id: productId,
            product_name: decodeURIComponent(productName),
            quantity: 1
        });
    }
    
    // Show success message
    if (a2uiClient) {
        a2uiClient.showToast(`Added ${decodeURIComponent(productName)} to cart`, 'success');
    } else {
        alert(`Added ${decodeURIComponent(productName)} to cart`);
    }
}

/**
 * Show error message
 */
function showError(message, type = 'error') {
    const responseDiv = document.getElementById("response");
    responseDiv.innerHTML = `
        <div class="error-message" style="
            padding: 16px; 
            background: #fee2e2; 
            border: 1px solid #ef4444; 
            border-radius: 8px; 
            color: #991b1b;
            margin: 20px 0;
        ">
            <strong>Error:</strong> ${message}
        </div>
    `;
}

/**
 * Show connection status
 */
function showConnectionStatus(status) {
    let statusIndicator = document.getElementById('a2ui-status');
    
    if (!statusIndicator) {
        statusIndicator = document.createElement('div');
        statusIndicator.id = 'a2ui-status';
        statusIndicator.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 20px;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 12px;
            z-index: 9999;
            transition: all 0.3s;
        `;
        document.body.appendChild(statusIndicator);
    }
    
    const statusConfig = {
        connected: {
            text: '🟢 A2UI Connected',
            background: '#10b981',
            color: 'white'
        },
        disconnected: {
            text: '🔴 A2UI Disconnected',
            background: '#ef4444',
            color: 'white'
        },
        error: {
            text: '⚠️ A2UI Error',
            background: '#f59e0b',
            color: 'white'
        }
    };
    
    const config = statusConfig[status] || statusConfig.disconnected;
    statusIndicator.textContent = config.text;
    statusIndicator.style.background = config.background;
    statusIndicator.style.color = config.color;
    
    // Auto-hide when connected
    if (status === 'connected') {
        setTimeout(() => {
            statusIndicator.style.opacity = '0.3';
        }, 3000);
    } else {
        statusIndicator.style.opacity = '1';
    }
}

/**
 * Handle structured response (backward compatibility)
 */
function handleStructuredResponse(data) {
    const responseDiv = document.getElementById("response");
    
    if (data.response_type === 'products_list' || data.response_type === 'product') {
        let html = '';
        
        if (data.ai_response) {
            html += `<div class="ai-response" style="margin-bottom: 20px; padding: 16px; background: #f3f4f6; border-radius: 8px;">${data.ai_response}</div>`;
        }
        
        if (data.products_data && data.products_data.length > 0) {
            displayProducts(data.products_data, data.query || '');
        }
    } else if (data.response_type === 'order_history' || data.response_type === 'order') {
        responseDiv.innerHTML = data.ai_response || "Order information processed.";
    } else {
        responseDiv.innerHTML = data.ai_response || `<p>${JSON.stringify(data)}</p>`;
    }
}

// Make functions globally available
window.submitQuery = submitQuery;
window.viewProductDetails = viewProductDetails;
window.addToCart = addToCart;
window.a2uiClient = a2uiClient;

console.log('✅ Enhanced main.js with A2UI loaded');
