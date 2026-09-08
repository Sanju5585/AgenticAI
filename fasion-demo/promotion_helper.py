# promotion_helper.py
# Helper functions for managing product promotions

from hdbcli import dbapi
from datetime import datetime
from typing import Optional, Dict

def hana_connect():
    """Establish connection to SAP HANA"""
    conn = dbapi.connect(
        address='794d7a51-4a96-4b97-a476-dacb3a0440b4.hna2.prod-eu10.hanacloud.ondemand.com',
        port='443',
        user='00F588CD78904954BA0FA8C9585A169F_8C04J77WXE7NPHALBEVGEC4AA_DT',
        password='Ae7Z34V2HG_8_j8r1kb_dWJsCGEnmE_nN0Z0cMULba.EdRcYbilznUf.bsX-ZJJ9q.9_13It90i_q3n8jSzE8zF_gfHbwEuE9LJos0bENwD2Q6YJjo_TlBICY23muSi.',
        encrypt=True,
        autocommit=True,
        sslValidateCertificate=False,
    )
    return conn

def get_active_promotion(product_id: str) -> Optional[Dict]:
    """
    Get active promotion for a product if it exists
    
    Args:
        product_id: Product identifier
        
    Returns:
        Dictionary with promotion details or None if no active promotion
    """
    try:
        conn = hana_connect()
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        query = f"""
            SELECT 
                PROMO_ID,
                PROMO_TITLE,
                PROMO_DESCRIPTION,
                PROMO_DISCOUNT_PERCENT,
                PROMO_START_DATE,
                PROMO_END_DATE
            FROM SAP_PROMOTION_COMMERCE_2211_V2
            WHERE TRIM(PROMO_PRODUCT_ID) = '{product_id}'
                AND PROMO_START_DATE <= '{today}'
                AND PROMO_END_DATE >= '{today}'
            ORDER BY PROMO_DISCOUNT_PERCENT DESC
            LIMIT 1
        """
        
        cursor.execute(query)
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if result:
            discount_percent = float(result[3]) if result[3] is not None else 0.0
            promo_data = {
                'promo_id': result[0],
                'promo_title': result[1],
                'promo_description': result[2],
                'discount_percent': discount_percent,
                'start_date': result[4],
                'end_date': result[5],
                'has_promotion': True
            }
            print(f"✅ Found promotion for {product_id}: {result[1]} - {discount_percent}% off")
            return promo_data
        
        print(f"ℹ️  No active promotion found for product {product_id}")
        return None
        
    except Exception as e:
        print(f"Error getting promotion for product {product_id}: {str(e)}")
        return None

def calculate_discounted_price(original_price: float, discount_percent: float) -> float:
    """
    Calculate discounted price
    
    Args:
        original_price: Original product price
        discount_percent: Discount percentage (e.g., 25 for 25%)
        
    Returns:
        Discounted price rounded to 2 decimals
    """
    try:
        # Ensure we have valid numbers
        original_price = float(original_price) if original_price is not None else 0.0
        discount_percent = float(discount_percent) if discount_percent is not None else 0.0
        
        # Validate discount percentage
        if discount_percent <= 0 or discount_percent > 100:
            print(f"⚠️ Invalid discount percent: {discount_percent}, returning original price: £{original_price}")
            return original_price
        
        # Calculate discount
        discount_amount = original_price * (discount_percent / 100)
        discounted_price = original_price - discount_amount
        
        result = round(discounted_price, 2)
        print(f"💰 Discount calc: £{original_price} - {discount_percent}% = £{result}")
        return result
    except Exception as e:
        print(f"❌ Error in calculate_discounted_price: {e}")
        return float(original_price) if original_price is not None else 0.0

def get_product_with_promotion(product_id: str) -> Optional[Dict]:
    """
    Get complete product details including promotion if available
    
    Args:
        product_id: Product identifier
        
    Returns:
        Dictionary with product and promotion details
    """
    try:
        conn = hana_connect()
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Query with LEFT JOIN to get promotion if exists
        query = f"""
            SELECT 
                p.PRODUCT_ID,
                p.PRODUCT_NAME,
                p.SUMMARY,
                p.PRICE,
                p.IMAGE_URL,
                p.CATEGORY_IDs,
                promo.PROMO_ID,
                promo.PROMO_TITLE,
                promo.PROMO_DESCRIPTION,
                promo.PROMO_DISCOUNT_PERCENT,
                promo.PROMO_END_DATE
            FROM SAP_PRODUCTS_COMMERCE_2211_V2 p
            LEFT JOIN SAP_PROMOTION_COMMERCE_2211_V2 promo 
                ON TRIM(p.PRODUCT_ID) = TRIM(promo.PROMO_PRODUCT_ID)
                AND promo.PROMO_START_DATE <= '{today}'
                AND promo.PROMO_END_DATE >= '{today}'
            WHERE TRIM(p.PRODUCT_ID) = '{product_id}'
        """
        
        cursor.execute(query)
        result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not result:
            return None
        
        original_price = float(result[3]) if result[3] else 0.0
        has_promotion = result[6] is not None
        
        product_data = {
            'product_id': result[0],
            'product_name': result[1],
            'summary': result[2],
            'original_price': original_price,
            'image_url': result[4],
            'category_ids': result[5],
            'has_promotion': has_promotion
        }
        
        if has_promotion:
            discount_percent = float(result[9])
            product_data.update({
                'promo_id': result[6],
                'promo_title': result[7],
                'promo_description': result[8],
                'discount_percent': discount_percent,
                'promo_end_date': result[10],
                'discounted_price': calculate_discounted_price(original_price, discount_percent),
                'savings': round(original_price - calculate_discounted_price(original_price, discount_percent), 2)
            })
            # Final price is discounted price
            product_data['price'] = product_data['discounted_price']
        else:
            # No promotion, price is original price
            product_data['price'] = original_price
            product_data['discount_percent'] = 0
            product_data['discounted_price'] = original_price
        
        return product_data
        
    except Exception as e:
        print(f"Error getting product with promotion {product_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def get_promotion_sql_join() -> str:
    """
    Returns SQL JOIN clause to include promotion data in product queries
    
    Returns:
        SQL JOIN string
    """
    today = datetime.now().strftime('%Y-%m-%d')
    
    return f"""
        LEFT JOIN SAP_PROMOTION_COMMERCE_2211_V2 promo 
            ON TRIM(PRODUCT_ID) = TRIM(promo.PROMO_PRODUCT_ID)
            AND promo.PROMO_START_DATE <= '{today}'
            AND promo.PROMO_END_DATE >= '{today}'
    """

def get_promotion_sql_columns() -> str:
    """
    Returns SQL column selection for promotion data
    
    Returns:
        SQL column string
    """
    return """
        promo.PROMO_ID,
        promo.PROMO_TITLE,
        promo.PROMO_DESCRIPTION,
        promo.PROMO_DISCOUNT_PERCENT,
        promo.PROMO_END_DATE,
        CASE 
            WHEN promo.PROMO_DISCOUNT_PERCENT IS NOT NULL 
            THEN PRICE * (1 - promo.PROMO_DISCOUNT_PERCENT / 100.0)
            ELSE PRICE
        END AS FINAL_PRICE
    """

def format_product_with_promotion(row_data: tuple, cursor_description: list) -> Dict:
    """
    Format database row to include promotion information
    
    Args:
        row_data: Database row tuple
        cursor_description: Cursor column descriptions
        
    Returns:
        Formatted product dictionary
    """
    columns = [col[0] for col in cursor_description]
    product = dict(zip(columns, row_data))
    
    # Check if promotion exists
    has_promotion = product.get('PROMO_ID') is not None and product.get('PROMO_DISCOUNT_PERCENT') is not None
    
    product['has_promotion'] = has_promotion
    
    if has_promotion:
        original_price = float(product.get('PRICE', 0))
        discount_percent = float(product.get('PROMO_DISCOUNT_PERCENT', 0))
        
        product['original_price'] = original_price
        product['discount_percent'] = discount_percent
        product['discounted_price'] = calculate_discounted_price(original_price, discount_percent)
        product['savings'] = round(original_price - product['discounted_price'], 2)
        product['price'] = product['discounted_price']  # Use discounted price as main price
    else:
        product['original_price'] = float(product.get('PRICE', 0))
        product['discount_percent'] = 0
        product['discounted_price'] = product['original_price']
        product['price'] = product['original_price']
    
    return product

def get_all_active_promotions() -> list:
    """
    Get all active promotions
    
    Returns:
        List of active promotions
    """
    try:
        conn = hana_connect()
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        query = f"""
            SELECT 
                PROMO_ID,
                PROMO_PRODUCT_ID,
                PROMO_PRODUCT_NAME,
                PROMO_TITLE,
                PROMO_DESCRIPTION,
                PROMO_DISCOUNT_PERCENT,
                PROMO_START_DATE,
                PROMO_END_DATE
            FROM SAP_PROMOTION_COMMERCE_2211_V2
            WHERE PROMO_START_DATE <= '{today}'
                AND PROMO_END_DATE >= '{today}'
            ORDER BY PROMO_DISCOUNT_PERCENT DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        promotions = []
        for row in rows:
            promotions.append({
                'promo_id': row[0],
                'product_id': row[1],
                'product_name': row[2],
                'promo_title': row[3],
                'promo_description': row[4],
                'discount_percent': float(row[5]),
                'start_date': row[6],
                'end_date': row[7]
            })
        
        cursor.close()
        conn.close()
        
        return promotions
        
    except Exception as e:
        print(f"Error getting all active promotions: {str(e)}")
        return []
