function submitQuery() {
    const queryValue = document.getElementById("query").value.trim();
    const responseDiv = document.getElementById("response");
    const loadingDiv = document.getElementById("loading");

    if (!queryValue) {
        alert("Please enter a query");
        return;
    }

    // Show the loading spinner with text
    loadingDiv.style.display = "block";
    responseDiv.innerHTML = "";

    fetch("/api/query", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ query: queryValue })
    })
    .then(response => response.json())
    .then(data => {
        console.log("Response data:", data); // Debug log
        
        // Handle structured responses (products, orders, etc.)
        if (data.response_type) {
            handleStructuredResponse(data);
        } 
        // Handle simple text responses
        else if (data.response) {
            document.getElementById("response").innerHTML = `<div>${data.response}</div>`;
        } 
        // Fallback for old format
        else {
            document.getElementById("response").innerHTML = `<p>${JSON.stringify(data)}</p>`;
        }
    })
    .catch(error => {
        console.error("Error:", error);
        document.getElementById("response").innerHTML = "<p>Error processing your query. Please try again.</p>";
    })
    .finally(() => {
        // Hide the loading spinner
        loadingDiv.style.display = "none";
    });
}

function handleStructuredResponse(data) {
    const responseDiv = document.getElementById("response");
    
    // Handle product responses
    if (data.response_type === 'products_list' || data.response_type === 'product') {
        let html = '';
        
        // Add AI response text if available
        if (data.ai_response) {
            html += `<div class="ai-response" style="margin-bottom: 20px;">${data.ai_response}</div>`;
        }
        
        // Create product cards
        if (data.products_data && data.products_data.length > 0) {
            html += '<div class="products-container" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-top: 20px;">';
            
            data.products_data.forEach(product => {
                html += createProductCard(product);
            });
            
            html += '</div>';
        }
        
        responseDiv.innerHTML = html;
    }
    // Handle order responses
    else if (data.response_type === 'order_history' || data.response_type === 'order') {
        responseDiv.innerHTML = data.ai_response || "Order information processed.";
    }
    // Handle other structured responses
    else {
        responseDiv.innerHTML = data.ai_response || `<p>${JSON.stringify(data)}</p>`;
    }
}

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
            transition: transform 0.2s;
        " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
            <div class="product-image" style="text-align: center; margin-bottom: 12px;">
                <img src="${imageUrl}" alt="${product.product_name || 'Product'}" 
                     style="max-width: 100%; height: 200px; object-fit: cover; border-radius: 4px;" 
                     onerror="this.src='/static/assets/placeholder-image.png'">
            </div>
            <div class="product-info">
                <h3 style="margin: 0 0 8px 0; font-size: 1.2em; color: #333;">
                    <a href="/product/${product.product_id}/${encodedProductName}" 
                       style="text-decoration: none; color: #007bff;"
                       onmouseover="this.style.textDecoration='underline'" 
                       onmouseout="this.style.textDecoration='none'">
                        ${product.product_name || 'Unknown Product'}
                    </a>
                </h3>
                <p style="margin: 0 0 8px 0; color: #666; font-size: 0.9em;">
                    ${product.summary || 'No description available'}
                </p>
                <div class="product-price" style="font-size: 1.1em; font-weight: bold; color: #28a745; margin: 8px 0;">
                    ${price}
                </div>
                <button class="add-to-cart-btn" 
                        onclick="addToCart('${product.product_id}', '${product.product_name}')"
                        style="
                            background: linear-gradient(135deg, #007bff, #0056b3); 
                            color: white; 
                            border: none; 
                            padding: 10px 20px; 
                            border-radius: 5px; 
                            cursor: pointer; 
                            width: 100%;
                            font-weight: bold;
                            transition: background 0.3s;
                        "
                        onmouseover="this.style.background='linear-gradient(135deg, #0056b3, #004085)'" 
                        onmouseout="this.style.background='linear-gradient(135deg, #007bff, #0056b3)'">
                    Add to Cart
                </button>
            </div>
        </div>
    `;
}

async function addToCart(productId, productName) {
    try {
        // Get or create customer ID (email)
        let customerEmail = localStorage.getItem('customer_email');
        if (!customerEmail) {
            customerEmail = prompt("Please enter your email to add items to cart:");
            if (!customerEmail) {
                alert("Email is required to add items to cart.");
                return;
            }
            localStorage.setItem('customer_email', customerEmail);
        }

        // Show loading state
        const response = await fetch("/api/add-to-cart", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                product_id: productId,
                quantity: 1,
                customer_id: customerEmail
            })
        });

        const data = await response.json();
        
        if (data.success) {
            // Show success message
            alert(data.message.replace(/<[^>]*>/g, '')); // Remove HTML tags for alert
            
            // Optional: Update cart UI or badge if you have one
            console.log("Product added to cart:", data.product_details);
        } else {
            alert(data.error || "Failed to add product to cart");
        }
    } catch (error) {
        console.error("Error adding to cart:", error);
        alert("Error adding product to cart. Please try again.");
    }
}


async function submitProductQuery() {
    const productQueryValue = document.getElementById("product_query").value.trim();
    const productResponseDiv = document.getElementById("product-response");
    if (!productQueryValue) {
        alert("Please enter a product query");
        return;
    }
    productResponseDiv.innerHTML = "Loading...";
    try {
        const response = await fetch("/api/product_semantic", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ query: productQueryValue }),
        });
        const data = await response.json();
        productResponseDiv.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
    } catch (error) {
        console.error("Error:", error);
        productResponseDiv.innerHTML = "<p>Error processing your product query. Please try again.</p>";
    }
}