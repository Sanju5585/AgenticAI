// function submitQuery() {
//     const queryValue = document.getElementById("query").value.trim();
//     const responseDiv = document.getElementById("response");
//     const loadingDiv = document.getElementById("loading");

//     if (!queryValue) {
//         alert("Please enter a query");
//         return;
//     }

//     // Show the loading spinner with text
//     loadingDiv.style.display = "block";
//     responseDiv.innerHTML = "";

//     fetch("/api/query", {
//         method: "POST",
//         headers: {
//             "Content-Type": "application/json"
//         },
//         body: JSON.stringify({ query: queryValue })
//     })
//     .then(response => response.json())
//     .then(data => {
//         // Render the response with header and content in a user-friendly way
//         document.getElementById("response").innerHTML = `<h3>${data.header}</h3><p>${data.content}</p>`;
//     })
//     .catch(error => {
//         console.error("Error:", error);
//         document.getElementById("response").innerHTML = "<p>Error processing your query. Please try again.</p>";
//     })
//     .finally(() => {
//         // Hide the loading spinner
//         loadingDiv.style.display = "none";
//     });
// }

// async function submitProductQuery() {
//     const productQueryValue = document.getElementById("product_query").value.trim();
//     const productResponseDiv = document.getElementById("product-response");
//     if (!productQueryValue) {
//         alert("Please enter a product query");
//         return;
//     }
//     productResponseDiv.innerHTML = "Loading...";
//     try {
//         const response = await fetch("/api/product_semantic", {
//             method: "POST",
//             headers: {
//                 "Content-Type": "application/json",
//             },
//             body: JSON.stringify({ query: productQueryValue }),
//         });
//         const data = await response.json();
//         productResponseDiv.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
//     } catch (error) {
//         console.error("Error:", error);
//         productResponseDiv.innerHTML = "<p>Error processing your product query. Please try again.</p>";
//     }
// }