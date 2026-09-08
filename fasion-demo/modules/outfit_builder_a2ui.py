"""
Outfit Builder / "Complete the Look" A2UI Module
Triggered when a user adds a product to the cart.
Finds complementary products from OUTFIT_COMPLETE_LOOK table,
fetches their details from SAP_PRODUCTS_COMMERCE_2211_V2,
and pushes the result to the frontend via the A2UI WebSocket server.
"""

import asyncio
import httpx
import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

A2UI_SERVER_URL = "http://localhost:8020"
A2UI_MODULE = "outfit_builder"

# ---------------------------------------------------------------------------
# Category detection: given a product name, return its category key
# ---------------------------------------------------------------------------
CATEGORY_PATTERNS = {
    "jacket":     r"(?i)jacket|coat|blazer|hoodie|cardigan",
    "tshirt":     r"(?i)t.shirt|tshirt|\btee\b",
    "dress":      r"(?i)dress|skirt|gown|jumpsuit",
    "pants":      r"(?i)pant|trouser|\bshort\b(?!board)",
    "shoe":       r"(?i)shoe|sneaker|sandal|\bboot\b",
    "cap":        r"(?i)\bcap\b|beanie|\bhat\b",
    "sunglasses": r"(?i)sunglass|shades|goggle",
    "bag":        r"(?i)\bbag\b|backpack|purse",
    "glove":      r"(?i)glove",
}


def detect_category(product_name: str) -> Optional[str]:
    """Return the category key for a product name, or None."""
    for cat, pattern in CATEGORY_PATTERNS.items():
        if re.search(pattern, product_name or ""):
            return cat
    return None


def detect_category_by_id(product_id: str, cursor) -> Optional[str]:
    """Look up category by querying the product table directly."""
    try:
        cursor.execute(
            "SELECT PRODUCT_NAME FROM SAP_PRODUCTS_COMMERCE_2211_V2 WHERE TRIM(PRODUCT_ID) = ?",
            (str(product_id).strip(),)
        )
        row = cursor.fetchone()
        if row:
            return detect_category(row[0])
    except Exception as e:
        logger.warning(f"Category lookup failed for {product_id}: {e}")
    return None


# ---------------------------------------------------------------------------
# Core DB logic
# ---------------------------------------------------------------------------

def get_outfit_looks(product_id: str, product_name: str, cursor) -> List[Dict[str, Any]]:
    """
    Given a cart product, fetch complement sections from OUTFIT_COMPLETE_LOOK
    and enrich each section with real product rows from SAP_PRODUCTS_COMMERCE_2211_V2.

    Returns a list of sections, e.g.:
      [
        { "complement_label": "Add Trousers / Pants",
          "complement_category": "pants",
          "priority": 1,
          "products": [ { product row dict }, ... ] },
        ...
      ]
    """
    today = datetime.now().strftime("%Y-%m-%d")

    # 1. Detect category for the cart product
    category = detect_category(product_name) or detect_category_by_id(product_id, cursor)
    if not category:
        logger.info(f"No category detected for product {product_id} ({product_name})")
        return []

    logger.info(f"Detected category '{category}' for product {product_id}")

    # 2. Get all outfit rules for this category
    cursor.execute(
        """
        SELECT COMPLEMENT_CATEGORY, COMPLEMENT_PRODUCT_IDS, COMPLEMENT_LABEL, PRIORITY
        FROM OUTFIT_COMPLETE_LOOK
        WHERE LOWER(SOURCE_CATEGORY) = ?
        ORDER BY PRIORITY ASC
        """,
        (category.lower(),)
    )
    rules = cursor.fetchall()

    if not rules:
        logger.info(f"No outfit rules found for category '{category}'")
        return []

    # 3. For each rule, fetch up to 4 actual product rows
    sections = []
    for comp_cat, comp_ids_str, comp_label, priority in rules:
        raw_ids = [i.strip() for i in (comp_ids_str or "").split(",") if i.strip()]
        if not raw_ids:
            continue

        # Fetch product details + any active promotion
        placeholders = ",".join(["?" for _ in raw_ids])
        cursor.execute(
            f"""
            SELECT TOP 4
                p.PRODUCT_ID, p.PRODUCT_NAME, p.SUMMARY, p.PRICE, p.IMAGE_URL,
                promo.PROMO_TITLE, promo.PROMO_DISCOUNT_PERCENT,
                CASE
                    WHEN promo.PROMO_DISCOUNT_PERCENT IS NOT NULL
                    THEN p.PRICE * (1 - promo.PROMO_DISCOUNT_PERCENT / 100.0)
                    ELSE p.PRICE
                END AS FINAL_PRICE
            FROM SAP_PRODUCTS_COMMERCE_2211_V2 p
            LEFT JOIN SAP_PROMOTION_COMMERCE_2211_V2 promo
                ON TRIM(p.PRODUCT_ID) = TRIM(promo.PROMO_PRODUCT_ID)
                AND promo.PROMO_START_DATE <= '{today}'
                AND promo.PROMO_END_DATE   >= '{today}'
            WHERE TRIM(p.PRODUCT_ID) IN ({placeholders})
            AND p.PRICE > 0
            ORDER BY FINAL_PRICE ASC
            """,
            raw_ids
        )
        prod_rows = cursor.fetchall()

        if not prod_rows:
            continue

        products = []
        for row in prod_rows:
            pid, pname, summary, price, img, promo_title, disc_pct, final_price = row
            products.append({
                "product_id":   str(pid).strip()   if pid   else "",
                "product_name": str(pname).strip() if pname else "",
                "summary":      str(summary).strip()[:120] if summary else "",
                "price":        float(price)        if price       else 0.0,
                "final_price":  float(final_price)  if final_price else (float(price) if price else 0.0),
                "image_url":    str(img).strip()    if img         else "",
                "promo_title":  str(promo_title).strip() if promo_title else "",
                "discount_pct": float(disc_pct)     if disc_pct    else 0.0,
            })

        sections.append({
            "complement_label":    str(comp_label).strip(),
            "complement_category": str(comp_cat).strip(),
            "priority":            int(priority),
            "products":            products,
        })

    return sections


# ---------------------------------------------------------------------------
# A2UI push
# ---------------------------------------------------------------------------

class OutfitBuilderA2UI:
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id

    async def _push(self, action: str, component: str, data: Dict[str, Any]):
        """POST a UI update to the A2UI server."""
        try:
            endpoint = f"{A2UI_SERVER_URL}/api/ui/update"
            if self.session_id:
                endpoint = f"{A2UI_SERVER_URL}/api/ui/update/{self.session_id}"

            payload = {
                "module":    A2UI_MODULE,
                "action":    action,
                "component": component,
                "data":      data,
                "metadata":  {"session_id": self.session_id},
            }
            async with httpx.AsyncClient() as client:
                resp = await client.post(endpoint, json=payload, timeout=5.0)
                if resp.status_code == 200:
                    logger.info(f"✅ Outfit A2UI update sent: {component}")
                else:
                    logger.warning(f"⚠️ Outfit A2UI update failed: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"❌ Outfit A2UI push error: {e}")

    async def push_outfit(self, product_id: str, product_name: str, sections: List[Dict]):
        """Send the complete outfit sections to the frontend."""
        await self._push(
            action="replace",
            component="outfit_complete_look",
            data={
                "cart_product_id":   product_id,
                "cart_product_name": product_name,
                "sections":          sections,
                "total_sections":    len(sections),
                "timestamp":         datetime.utcnow().isoformat(),
            },
        )

    async def push_loading(self, is_loading: bool, message: str = ""):
        await self._push(
            action="update",
            component="outfit_loading",
            data={"is_loading": is_loading, "message": message},
        )

    async def push_empty(self, product_id: str, product_name: str):
        await self._push(
            action="replace",
            component="outfit_complete_look",
            data={
                "cart_product_id":   product_id,
                "cart_product_name": product_name,
                "sections":          [],
                "total_sections":    0,
                "timestamp":         datetime.utcnow().isoformat(),
            },
        )

    async def load_and_push(self, product_id: str, product_name: str):
        """Full pipeline: query DB → push to frontend via A2UI."""
        try:
            await self.push_loading(True, f"Building your outfit for {product_name}…")

            from agent import hana_connect
            conn = hana_connect()
            cursor = conn.cursor()

            sections = get_outfit_looks(product_id, product_name, cursor)

            cursor.close()
            conn.close()

            if sections:
                logger.info(f"✅ Outfit: {len(sections)} sections for product {product_id}")
                await self.push_outfit(product_id, product_name, sections)
            else:
                logger.info(f"ℹ️ No outfit sections for product {product_id}")
                await self.push_empty(product_id, product_name)

            await self.push_loading(False)
            return {"success": True, "sections": len(sections), "data": sections}

        except Exception as e:
            logger.error(f"❌ Outfit load_and_push error: {e}")
            import traceback
            traceback.print_exc()
            await self.push_loading(False)
            return {"success": False, "error": str(e)}


def load_outfit_sync(product_id: str, product_name: str, session_id: Optional[str] = None) -> dict:
    """Synchronous wrapper usable from Flask views."""
    builder = OutfitBuilderA2UI(session_id=session_id)
    return asyncio.run(builder.load_and_push(product_id, product_name))
