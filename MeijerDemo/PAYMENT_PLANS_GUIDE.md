# Payment Plans Implementation Guide

## Overview
This implementation adds payment plan functionality to mobile phones and watches, displaying storage/variant options with monthly payment plans on the product detail page.

## Features

### 1. Database Structure
- **Table Name**: `SAP_PRODUCT_PAYMENT_PLANS_V2`
- **Columns**:
  - `PLAN_ID`: Unique identifier for the plan
  - `PRODUCT_ID`: Links to the product (mobile or watch)
  - `VARIANT_NAME`: Storage option (256GB, 512GB, 1TB, etc.) or connectivity type (GPS, GPS + Cellular, LTE, etc.)
  - `MONTHLY_PAYMENT`: Monthly payment amount for 24 months
  - `DURATION_MONTHS`: Payment duration (typically 24 months)
  - `DUE_TODAY`: Amount due today (usually $0.00, or upfront payment)
  - `FULL_PRICE`: Full retail price of the variant
  - `STOCK_STATUS`: 'In stock' or 'Out of stock'
  - `VARIANT_ORDER`: Display order (1, 2, 3, etc.)

### 2. Product Eligibility
Payment plans are **only available** for:
- **Mobile phones**: Product IDs starting with `2` (e.g., 200001, 200050, 200055)
- **Watches**: Product IDs starting with `4` (e.g., 400001, 400011, 400014)

### 3. Payment Plan Display
The product detail page shows:
- Toggle between "Pay monthly" and "Pay in full" view
- Storage/variant options with pricing
- Stock availability status
- Full price with tax information
- Due today amount

## Usage

### Adding Payment Plans

#### Method 1: Using the Load Script
Run the payment plans loader:
```bash
python load_payment_plans.py
```

This will create the table and load sample plans for popular products.

#### Method 2: Manual Database Insert
```sql
INSERT INTO SAP_PRODUCT_PAYMENT_PLANS_V2 
(PLAN_ID, PRODUCT_ID, VARIANT_NAME, MONTHLY_PAYMENT, DURATION_MONTHS, DUE_TODAY, FULL_PRICE, STOCK_STATUS, VARIANT_ORDER)
VALUES 
('PLAN_200050_256', '200050', '256GB', 37.50, 24, 0.00, 899.99, 'In stock', 2);
```

### Accessing Product Details with Plans

#### Via Web Interface
Navigate to: `http://localhost:5000/product/{PRODUCT_ID}`

Example:
- `http://localhost:5000/product/200050` - Samsung Galaxy S25
- `http://localhost:5000/product/400001` - Apple Watch Series 11

#### Via API/Agent
```python
from agent import get_product_details

# Get product details with payment plans
result = get_product_details("product 200050")

# Access the data
product = result['results'][0]
print(f"Product: {product['PRODUCT_NAME']}")
print(f"Plans available: {len(product.get('PAYMENT_PLANS', []))}")

for plan in product.get('PAYMENT_PLANS', []):
    print(f"  {plan['VARIANT_NAME']}: ${plan['MONTHLY_PAYMENT']}/month")
```

## Example Products with Plans

### Mobile Phones
- **200022**: Apple iPhone 15 (4 storage variants)
- **200029**: Apple iPhone 15 Pro (4 storage variants)
- **200036**: Apple iPhone 17 Pro Max (3 storage variants)
- **200050**: Samsung Galaxy S25 (3 storage variants)
- **200055**: Samsung Galaxy S25 Ultra (3 storage variants)
- **200058**: Google Pixel 9a (2 storage variants)

### Watches
- **400001**: Apple Watch Series 11 42mm (GPS, GPS + Cellular)
- **400002**: Apple Watch Series 11 46mm (GPS, GPS + Cellular)
- **400007**: Apple Watch Ultra 3 (Titanium)
- **400011**: Samsung Galaxy Watch8 40mm (Bluetooth, LTE)
- **400012**: Samsung Galaxy Watch8 44mm (Bluetooth, LTE)
- **400014**: Samsung Galaxy Watch Ultra 47mm (LTE)

## Testing

Run the test script to verify the implementation:
```bash
python test_payment_plans.py
```

This will verify:
- Payment plans table exists and has data
- Plans are correctly linked to products
- `get_product_details` function includes payment plans
- Plans are only shown for eligible products

## UI Components

### Payment Plan Card Format
Each variant displays:
```
┌─────────────────────────────────────────┐
│ 256GB                 $37.50/month      │
│                       for 24 months     │
│                       Due today: $0.00  │
│                       Full price: $899.99 + tax │
│                       In stock          │
└─────────────────────────────────────────┘
```

### Toggle Buttons
- **Pay monthly**: Shows monthly payment amount
- **Pay in full**: Shows full retail price

## Adding Plans for New Products

### Step 1: Identify Product Type
Ensure the product ID starts with:
- `2` for mobiles
- `4` for watches

### Step 2: Define Variants
Determine storage or connectivity options:
- **Mobiles**: 128GB, 256GB, 512GB, 1TB, 2TB
- **Watches**: GPS, GPS + Cellular, Bluetooth, LTE

### Step 3: Calculate Pricing
- **Monthly Payment** = Full Price / 24 months
- **Due Today** = Usually $0.00 (or any upfront payment)
- **Full Price** = Retail price for that variant

### Step 4: Insert Data
```python
# Example: Adding plans for a new iPhone model (Product ID: 200099)
plans = [
    ('PLAN_200099_128', '200099', '128GB', 41.67, 24, 0.00, 999.99, 'In stock', 1),
    ('PLAN_200099_256', '200099', '256GB', 45.83, 24, 0.00, 1099.99, 'In stock', 2),
    ('PLAN_200099_512', '200099', '512GB', 54.17, 24, 0.00, 1299.99, 'In stock', 3),
]

# Insert into database
conn = hana_connect()
cursor = conn.cursor()
for plan in plans:
    cursor.execute("""
        INSERT INTO SAP_PRODUCT_PAYMENT_PLANS_V2 
        (PLAN_ID, PRODUCT_ID, VARIANT_NAME, MONTHLY_PAYMENT, DURATION_MONTHS, 
         DUE_TODAY, FULL_PRICE, STOCK_STATUS, VARIANT_ORDER)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, plan)
conn.commit()
```

## Customization

### Changing Payment Duration
Currently set to 24 months. To change:
1. Update `DURATION_MONTHS` in the database
2. Recalculate `MONTHLY_PAYMENT` = Full Price / New Duration

### Adding Stock Management
Update stock status based on inventory:
```sql
UPDATE SAP_PRODUCT_PAYMENT_PLANS_V2 
SET STOCK_STATUS = 'Out of stock' 
WHERE PLAN_ID = 'PLAN_200022_256';
```

### Custom Variant Names
For special editions or colors:
```sql
INSERT INTO SAP_PRODUCT_PAYMENT_PLANS_V2 
VALUES ('PLAN_200099_256_GOLD', '200099', '256GB Gold Edition', 49.99, 24, 0.00, 1199.99, 'In stock', 4);
```

## Troubleshooting

### Plans Not Showing
1. Check product ID starts with `2` or `4`
2. Verify plans exist in database:
   ```sql
   SELECT * FROM SAP_PRODUCT_PAYMENT_PLANS_V2 WHERE PRODUCT_ID = 'YOUR_PRODUCT_ID';
   ```
3. Check console logs for errors

### Incorrect Pricing Display
1. Ensure `MONTHLY_PAYMENT` and `FULL_PRICE` are properly formatted decimals
2. Verify template is rendering prices with 2 decimal places
3. Check JavaScript toggle functionality

### Stock Status Not Updating
The stock status is stored in the database. Update it regularly:
```sql
UPDATE SAP_PRODUCT_PAYMENT_PLANS_V2 
SET STOCK_STATUS = 'In stock' 
WHERE PRODUCT_ID = '200050';
```

## Technical Architecture

### Backend Flow
1. User requests product detail page: `/product/{PRODUCT_ID}`
2. `app.py` route handler fetches product from database
3. If product ID starts with `2` or `4`, fetch payment plans
4. Template renders product info and payment plans

### Frontend Components
- **product_detail.html**: Main template with payment plan UI
- **JavaScript Toggle**: Switches between monthly/full payment views
- **Responsive Design**: Works on mobile and desktop

### Database Integration
- Joins `SAP_ELECTRONICS_PRODUCTS_2211_V2` with `SAP_PRODUCT_PAYMENT_PLANS_V2`
- Ordered by `VARIANT_ORDER` for consistent display

## Future Enhancements

Potential improvements:
1. **CSV Import**: Bulk load plans from CSV file
2. **Admin Interface**: Manage plans via web UI
3. **Dynamic Pricing**: Calculate based on current inventory
4. **Multiple Payment Durations**: 12, 24, 36 months options
5. **Interest Calculations**: Add APR/interest if applicable
6. **Color Variants**: Add color options with different pricing
7. **Search Integration**: Filter products by payment plan availability

## API Reference

### get_product_details(query: str) -> dict
Enhanced to include payment plans for mobile and watch products.

**Input**: Query string with product ID
**Output**: Dictionary with product details and optional payment plans

```python
{
    "results": [{
        "PRODUCT_ID": "200050",
        "PRODUCT_NAME": "Samsung Galaxy S25",
        "SUMMARY": "...",
        "PRICE": 799.99,
        "PAYMENT_PLANS": [
            {
                "PLAN_ID": "PLAN_200050_128",
                "VARIANT_NAME": "128GB",
                "MONTHLY_PAYMENT": 33.33,
                "DURATION_MONTHS": 24,
                "DUE_TODAY": 0.00,
                "FULL_PRICE": 799.99,
                "STOCK_STATUS": "In stock"
            }
        ]
    }]
}
```

## Conclusion

The payment plans feature is now fully integrated into the product catalog system. It provides a professional, user-friendly way to display financing options for mobile phones and watches, similar to major e-commerce platforms.
