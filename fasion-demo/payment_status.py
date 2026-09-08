"""
Payment Status Manager
Handles writing and reading payment status to/from temporary files
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path

# Directory for payment status files
PAYMENT_STATUS_DIR = Path("temp_payment_status")
PAYMENT_STATUS_DIR.mkdir(exist_ok=True)

def create_payment_status_file(session_id: str, payment_data: dict) -> str:
    """
    Create a payment status file for tracking
    Returns the file path
    """
    filename = f"payment_{session_id}_{int(time.time())}.json"
    filepath = PAYMENT_STATUS_DIR / filename
    
    status_data = {
        "session_id": session_id,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "payment_data": payment_data,
        "result": None
    }
    
    with open(filepath, 'w') as f:
        json.dump(status_data, f, indent=2)
    
    return str(filepath)

def update_payment_status(session_id: str, status: str, result_data: dict = None):
    """
    Update payment status file
    status: 'success', 'cancelled', 'error'
    """
    # Find the most recent payment file for this session
    payment_files = list(PAYMENT_STATUS_DIR.glob(f"payment_{session_id}_*.json"))
    
    if not payment_files:
        print(f"No payment file found for session: {session_id}")
        return False
    
    # Get the most recent file
    latest_file = max(payment_files, key=os.path.getctime)
    
    # Read current data
    with open(latest_file, 'r') as f:
        data = json.load(f)
    
    # Update status
    data['status'] = status
    data['updated_at'] = datetime.now().isoformat()
    
    if result_data:
        data['result'] = result_data
    
    # Write back
    with open(latest_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Payment status updated: {session_id} -> {status}")
    return True

def check_payment_status(session_id: str) -> dict:
    """
    Check the current payment status
    Returns: {'status': 'pending'|'success'|'cancelled'|'error', 'result': dict}
    """
    # Find the most recent payment file for this session
    payment_files = list(PAYMENT_STATUS_DIR.glob(f"payment_{session_id}_*.json"))
    
    if not payment_files:
        return {'status': 'not_found', 'result': None}
    
    # Get the most recent file
    latest_file = max(payment_files, key=os.path.getctime)
    
    # Read status
    with open(latest_file, 'r') as f:
        data = json.load(f)
    
    return {
        'status': data.get('status', 'pending'),
        'result': data.get('result'),
        'payment_data': data.get('payment_data'),
        'created_at': data.get('created_at'),
        'updated_at': data.get('updated_at', None)
    }

def cleanup_old_payment_files(hours: int = 24):
    """
    Clean up old payment status files older than specified hours
    """
    current_time = time.time()
    cutoff_time = current_time - (hours * 3600)
    
    for filepath in PAYMENT_STATUS_DIR.glob("payment_*.json"):
        if os.path.getctime(filepath) < cutoff_time:
            try:
                os.remove(filepath)
                print(f"🗑️ Cleaned up old payment file: {filepath}")
            except Exception as e:
                print(f"Error cleaning up {filepath}: {e}")

def get_session_payment_file(session_id: str) -> str:
    """
    Get the filepath for a session's payment status
    """
    payment_files = list(PAYMENT_STATUS_DIR.glob(f"payment_{session_id}_*.json"))
    
    if not payment_files:
        return None
    
    # Return the most recent file
    return str(max(payment_files, key=os.path.getctime))
