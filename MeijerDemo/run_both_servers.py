#!/usr/bin/env python3
"""
Multi-Server Launcher
Runs Flask App, PayPal MCP Server, and A2UI Protocol Server concurrently.
"""

import threading
import time
import sys
import os
import signal
from concurrent.futures import ThreadPoolExecutor
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# PayPal MCP Server Configuration
PAYPAL_MCP_PORT = int(os.getenv("PAYPAL_MCP_PORT", "8010"))
PAYPAL_MCP_BIND_HOST = "0.0.0.0"
PAYPAL_MCP_SERVER_URL = f"http://0.0.0.0:{PAYPAL_MCP_PORT}"

# A2UI Protocol Server Configuration
A2UI_PORT = int(os.getenv("A2UI_PORT", "8020"))
A2UI_BIND_HOST = "0.0.0.0"
A2UI_SERVER_URL = f"http://0.0.0.0:{A2UI_PORT}"


def get_local_ip():
    """Return the machine's LAN IP address for remote access display."""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "<your-ip>"

def run_flask_app():
    """Run the Flask application"""
    try:
        print("🌐 Starting Flask App (app.py)...")
        print("   URL: http://0.0.0.0:5000 (accessible from remote machines)")
        print("   Environment: Development")
        
        # Import and run the Flask app
        from app import app
        app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False, threaded=True)
        
    except KeyboardInterrupt:
        print("🌐 Flask App: Shutdown requested")
    except Exception as e:
        print(f"❌ Flask App Error: {e}")
        import traceback
        traceback.print_exc()
        # Don't exit the whole process, just log the error
        raise

def run_paypal_mcp_server():
    """Run the PayPal MCP Server using uvicorn"""
    try:
        ip = get_local_ip()
        print("💳 Starting PayPal MCP Server (Paypal_MCP_Server.py)...")
        print(f"   Binding: http://0.0.0.0:{PAYPAL_MCP_PORT}  (remote: http://{ip}:{PAYPAL_MCP_PORT})")
        print("   Environment: Development")
        
        # Brief delay to ensure clean startup
        time.sleep(0.5)
        
        # Run uvicorn server with proper error handling
        uvicorn.run(
            "Paypal_MCP_Server:app",
            host=PAYPAL_MCP_BIND_HOST,
            port=PAYPAL_MCP_PORT,
            reload=False,  # Disable reload to avoid conflicts
            log_level="info",
            access_log=True,
            use_colors=True,
            timeout_keep_alive=30  # Add keep-alive timeout
        )
        
    except KeyboardInterrupt:
        print("💳 PayPal MCP Server: Shutdown requested")
    except Exception as e:
        print(f"❌ PayPal MCP Server Error: {e}")
        import traceback
        traceback.print_exc()
        # Don't exit the whole process, just log the error
        raise

def run_a2ui_server():
    """Run the A2UI Protocol Server using uvicorn"""
    try:
        ip = get_local_ip()
        print("🚀 Starting A2UI Protocol Server (a2ui_protocol_server.py)...")
        print(f"   Binding: http://0.0.0.0:{A2UI_PORT}  (remote: http://{ip}:{A2UI_PORT})")
        print(f"   WebSocket: ws://0.0.0.0:{A2UI_PORT}/ws/{{session_id}}  (remote: ws://{ip}:{A2UI_PORT}/ws/{{session_id}})")
        print("   Environment: Development")
        
        # Brief delay to ensure clean startup
        time.sleep(0.5)
        
        # Run uvicorn server with proper error handling
        uvicorn.run(
            "a2ui_protocol_server:app",
            host=A2UI_BIND_HOST,
            port=A2UI_PORT,
            reload=False,  # Disable reload to avoid conflicts
            log_level="info",
            access_log=True,
            use_colors=True,
            timeout_keep_alive=60  # Longer timeout for WebSocket connections
        )
        
    except KeyboardInterrupt:
        print("🚀 A2UI Protocol Server: Shutdown requested")
    except Exception as e:
        print(f"❌ A2UI Protocol Server Error: {e}")
        import traceback
        traceback.print_exc()
        # Don't exit the whole process, just log the error
        raise

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\n🛑 Shutdown signal received. Stopping all servers...")
    print("   Flask App: Stopping...")
    print("   PayPal MCP Server: Stopping...")
    print("   A2UI Protocol Server: Stopping...")
    os._exit(0)

def check_prerequisites():
    """Check if all required environment variables are set"""
    print("🔍 Checking prerequisites...")
    
    required_vars = ['PAYPAL_CLIENT_ID', 'PAYPAL_CLIENT_SECRET']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("   Please check your .env file and ensure these variables are set.")
        return False
    
    print("✅ All prerequisites met!")
    return True

def main():
    """Main function to run all servers concurrently"""
    print("=" * 70)
    print("🚀 MULTI-SERVER LAUNCHER")
    print("   Flask App + PayPal MCP Server + A2UI Protocol Server")
    print("=" * 70)
    
    # Check prerequisites
    if not check_prerequisites():
        sys.exit(1)
    
    # Set up signal handling for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create threads for all servers
    flask_thread = threading.Thread(
        target=run_flask_app,
        name="FlaskApp",
        daemon=True
    )
    
    paypal_thread = threading.Thread(
        target=run_paypal_mcp_server,
        name="PayPalMCPServer",
        daemon=True
    )
    
    a2ui_thread = threading.Thread(
        target=run_a2ui_server,
        name="A2UIProtocolServer",
        daemon=True
    )
    
    try:
        print("\n🔄 Starting servers in sequence...")
        
        # Start A2UI Protocol Server first
        print("1️⃣ Starting A2UI Protocol Server...")
        a2ui_thread.start()
        time.sleep(2)
        
        # Start PayPal MCP Server second
        print("2️⃣ Starting PayPal MCP Server...")
        paypal_thread.start()
        
        # Wait for the MCP server to initialize with retry logic
        print("   ⏳ Waiting for PayPal MCP Server to initialize...")
        import requests
        
        max_retries = 10
        retry_delay = 1
        server_ready = False
        
        for attempt in range(max_retries):
            time.sleep(retry_delay)
            try:
                response = requests.get(f"http://127.0.0.1:{PAYPAL_MCP_PORT}/health", timeout=3)
                if response.status_code == 200:
                    print(f"   ✅ PayPal MCP Server is healthy (ready in {(attempt + 1) * retry_delay}s)")
                    server_ready = True
                    break
                else:
                    print(f"   ⏳ Attempt {attempt + 1}/{max_retries}: Server returned status {response.status_code}")
            except requests.exceptions.RequestException:
                if attempt < max_retries - 1:
                    print(f"   ⏳ Attempt {attempt + 1}/{max_retries}: Waiting for server to start...")
                else:
                    print(f"   ⚠️ Could not verify PayPal MCP Server health after {max_retries} attempts")
                    print("   ⚠️ Server may still be starting. Continuing anyway...")
        
        if not server_ready:
            print(f"   ℹ️ Note: You can verify server status later at http://127.0.0.1:{PAYPAL_MCP_PORT}/health")
        
        # Start Flask app last
        print("3️⃣ Starting Flask App...")
        flask_thread.start()
        time.sleep(2)
        
        print("\n✅ All servers started successfully!")
        print("\n📋 SERVER STATUS:")
        ip = get_local_ip()
        flask_port = 5000
        print("   🌐 Flask App:              http://0.0.0.0:5000")
        print(f"   🌐 Flask App (remote):     http://{ip}:{flask_port}")
        print(f"   🎯 A2UI Demo:              http://{ip}:{flask_port}/a2ui_demo")
        print(f"   💳 PayPal MCP Server:      http://0.0.0.0:{PAYPAL_MCP_PORT}")
        print(f"   💳 PayPal MCP (remote):    http://{ip}:{PAYPAL_MCP_PORT}")
        print(f"   🚀 A2UI Protocol Server:   http://0.0.0.0:{A2UI_PORT}")
        print(f"   🚀 A2UI Server (remote):   http://{ip}:{A2UI_PORT}")
        print(f"   🔌 A2UI WebSocket:         ws://0.0.0.0:{A2UI_PORT}/ws/{{session_id}}")
        print(f"   🔌 A2UI WebSocket (remote):ws://{ip}:{A2UI_PORT}/ws/{{session_id}}")
        print(f"   📖 PayPal Health Check:    http://{ip}:{PAYPAL_MCP_PORT}/health")
        print(f"   📖 A2UI Health Check:      http://{ip}:{A2UI_PORT}/")
        print("\n💡 USAGE:")
        print(f"   • Open http://{ip}:{flask_port} from any machine on the network")
        print(f"   • A2UI demo at http://{ip}:{flask_port}/a2ui_demo")
        print("   • PayPal MCP Server handles payment processing")
        print("   • A2UI Protocol Server enables real-time UI updates via WebSocket")
        print("   • Press Ctrl+C to stop all servers")
        
        # Keep the main thread alive and monitor thread health
        check_interval = 5  # Check every 5 seconds
        last_check = time.time()
        
        while True:
            current_time = time.time()
            
            # Periodically check thread status
            if current_time - last_check >= check_interval:
                if not flask_thread.is_alive():
                    print("\n❌ Flask App thread died unexpectedly")
                    print("   Attempting to diagnose issue...")
                    break
                if not paypal_thread.is_alive():
                    print("\n❌ PayPal MCP Server thread died unexpectedly")
                    print("   Attempting to diagnose issue...")
                    # Try to restart the PayPal server
                    print("   🔄 Attempting to restart PayPal MCP Server...")
                    paypal_thread = threading.Thread(
                        target=run_paypal_mcp_server,
                        name="PayPalMCPServer-Restart",
                        daemon=True
                    )
                    paypal_thread.start()
                    time.sleep(3)
                    print("   ✅ PayPal MCP Server restarted")
                if not a2ui_thread.is_alive():
                    print("\n❌ A2UI Protocol Server thread died unexpectedly")
                    print("   Attempting to diagnose issue...")
                    # Try to restart the A2UI server
                    print("   🔄 Attempting to restart A2UI Protocol Server...")
                    a2ui_thread = threading.Thread(
                        target=run_a2ui_server,
                        name="A2UIProtocolServer-Restart",
                        daemon=True
                    )
                    a2ui_thread.start()
                    time.sleep(3)
                    print("   ✅ A2UI Protocol Server restarted")
                    print("\n❌ PayPal MCP Server thread died unexpectedly")
                    print("   Attempting to diagnose issue...")
                    # Try to restart the PayPal server
                    print("   🔄 Attempting to restart PayPal MCP Server...")
                    paypal_thread = threading.Thread(
                        target=run_paypal_mcp_server,
                        name="PayPalMCPServer-Restart",
                        daemon=True
                    )
                    paypal_thread.start()
                    time.sleep(3)
                    print("   ✅ PayPal MCP Server restarted")
                
                last_check = current_time
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Keyboard interrupt received")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        print("\n🔄 Cleaning up...")
        print("   Stopping all servers...")
        os._exit(0)

if __name__ == "__main__":
    main()