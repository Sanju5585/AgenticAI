from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import paypalrestsdk
import uuid
import os
from dotenv import load_dotenv
import traceback
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """Handle startup events"""
    import asyncio
    logger.info("=" * 60)
    logger.info("PayPal MCP Server Starting...")
    logger.info(f"Mode: {PAYPAL_MODE}")
    logger.info("Initializing PayPal SDK...")
    
    # Brief delay to ensure all components are initialized
    await asyncio.sleep(0.5)
    
    logger.info("✅ PayPal MCP Server Ready!")
    logger.info("=" * 60)

@app.on_event("shutdown")
async def shutdown_event():
    """Handle shutdown events"""
    logger.info("PayPal MCP Server Shutting Down...")
    logger.info("Cleanup completed")

# Get PayPal credentials from environment
PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID')
PAYPAL_CLIENT_SECRET = os.getenv('PAYPAL_CLIENT_SECRET')
PAYPAL_MODE = os.getenv('PAYPAL_MODE', 'sandbox')  # Default to sandbox

# Validate credentials
if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
    error_msg = "PayPal credentials not found in environment variables. Please check your .env file."
    logger.error(error_msg)
    raise ValueError(error_msg)

logger.info("PayPal MCP Server Configuration:")
logger.info(f"   Mode: {PAYPAL_MODE}")
logger.info(f"   Client ID: {PAYPAL_CLIENT_ID[:10]}...{PAYPAL_CLIENT_ID[-4:] if len(PAYPAL_CLIENT_ID) > 14 else PAYPAL_CLIENT_ID}")
logger.info(f"   Client Secret: {'*' * min(len(PAYPAL_CLIENT_SECRET), 20)}")

# Configure PayPal SDK with credentials from .env
paypalrestsdk.configure({
    "mode": PAYPAL_MODE,  # sandbox or live
    "client_id": PAYPAL_CLIENT_ID,
    "client_secret": PAYPAL_CLIENT_SECRET
})

# Request model
class PaymentRequest(BaseModel):
    amount: str
    currency: str
    description: str
    return_url: str
    cancel_url: str

@app.get("/")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "PayPal MCP Server",
        "mode": PAYPAL_MODE,
        "endpoints": {
            "payment": "/mcp/tools/invoke/paypal_payment",
            "health": "/"
        }
    }

@app.get("/health")
def detailed_health_check():
    """Detailed health check with PayPal configuration status"""
    config_status = {
        "paypal_configured": bool(PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET),
        "mode": PAYPAL_MODE,
        "client_id_set": bool(PAYPAL_CLIENT_ID),
        "client_secret_set": bool(PAYPAL_CLIENT_SECRET)
    }
    
    return {
        "status": "healthy",
        "service": "PayPal MCP Server",
        "timestamp": uuid.uuid4().hex,
        "configuration": config_status
    }

@app.post("/mcp/tools/invoke/paypal_payment")
def create_paypal_payment(req: PaymentRequest):
    """
    Create a PayPal payment with comprehensive error handling.
    """
    try:
        logger.info("Creating PayPal payment:")
        logger.info(f"   Amount: {req.amount} {req.currency}")
        logger.info(f"   Description: {req.description}")
        logger.info(f"   Return URL: {req.return_url}")
        logger.info(f"   Cancel URL: {req.cancel_url}")
        
        # Validate input
        try:
            amount_float = float(req.amount)
            if amount_float <= 0:
                raise ValueError("Amount must be greater than 0")
        except ValueError as e:
            logger.error(f"Invalid amount: {req.amount}")
            return {
                "status": "error",
                "details": f"Invalid amount: {str(e)}"
            }
        
        # Create payment object
        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {"payment_method": "paypal"},
            "transactions": [{
                "amount": {
                    "total": req.amount,
                    "currency": req.currency
                },
                "description": req.description
            }],
            "redirect_urls": {
                "return_url": req.return_url,
                "cancel_url": req.cancel_url
            }
        })

        # Attempt to create the payment
        if payment.create():
            logger.info(f"PayPal payment created successfully:")
            logger.info(f"   Payment ID: {payment.id}")
            
            # Find the approval URL
            approval_url = None
            for link in payment.links:
                if link.rel == "approval_url":
                    approval_url = link.href
                    break
            
            if not approval_url:
                logger.error("No approval URL found in PayPal response")
                return {
                    "status": "error",
                    "details": "No approval URL found in PayPal response"
                }
            
            logger.info(f"   Approval URL: {approval_url}")
            
            return {
                "status": "success",
                "payment_id": payment.id,
                "approval_url": approval_url
            }
        else:
            error_detail = getattr(payment, 'error', 'Unknown error')
            logger.error(f"PayPal payment creation failed:")
            logger.error(f"   Error: {error_detail}")
            return {
                "status": "error",
                "details": error_detail
            }
            
    except paypalrestsdk.exceptions.ConnectionError as e:
        logger.error(f"PayPal connection error: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "details": f"PayPal connection error: {str(e)}"
        }
    except Exception as e:
        logger.error(f"Unexpected exception in PayPal payment creation: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "details": f"Server error: {str(e)}"
        }