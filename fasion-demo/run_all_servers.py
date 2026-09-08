#!/usr/bin/env python3
"""
All Servers Launcher
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
PAYPAL_MCP_HOST = os.getenv("PAYPAL_MCP_HOST", "localhost")
PAYPAL_MCP_PORT = int(os.getenv("PAYPAL_MCP_PORT", "8010"))
PAYPAL_MCP_BIND_HOST = os.getenv("PAYPAL_MCP_BIND_HOST", "0.0.0.0")
PAYPAL_MCP_SERVER_URL = f"http://{PAYPAL_MCP_HOST}:{PAYPAL_MCP_PORT}"

# A2UI Protocol Server Configuration
A2UI_PORT = int(os.getenv("A2UI_PORT", "8020"))
A2UI_SERVER_URL = os.getenv("A2UI_SERVER_URL", "http://localhost:8020")

def run_flask_app():
    """Run the Flask application"""
    try:
        print("🌐 Starting Flask App (app.py)...")
        print("   URL: http://localhost:5000")
        print("   Environment: Development")
        
        # Import and run the Flask app
        from app import app
        app.run(host="localhost", port=5000, debug=False, use_reloader=False, threaded=True)
        
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
        print("💳 Starting PayPal MCP Server (Paypal_MCP_Server.py)...")
        print(f"   URL: {PAYPAL_MCP_SERVER_URL}")
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
        print("🚀 Starting A2UI Protocol Server (a2ui_protocol_server.py)...")
        print(f"   URL: {A2UI_SERVER_URL}")
        print(f"   WebSocket: ws://localhost:{A2UI_PORT}/ws/{{session_id}}")
        print("   Environment: Development")
        
        # Brief delay to ensure clean startup
        time.sleep(0.5)
        
        # Run uvicorn server with proper error handling
        uvicorn.run(
            "a2ui_protocol_server:app",
            host="0.0.0.0",
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
    print("🚀 ALL SERVERS LAUNCHER")
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
        
        # Start A2UI Protocol Server first (for WebSocket support)
        print("1️⃣ Starting A2UI Protocol Server...")
        a2ui_thread.start()
        time.sleep(2)
        print("   ✅ A2UI Protocol Server started")
        
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
                response = requests.get(f"{PAYPAL_MCP_SERVER_URL}/health", timeout=3)
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
            print(f"   ℹ️ Note: You can verify server status later at {PAYPAL_MCP_SERVER_URL}/health")
        
        # Start Flask app last
        print("3️⃣ Starting Flask App...")
        flask_thread.start()
        time.sleep(2)
        print("   ✅ Flask App started")
        
        print("\n" + "=" * 70)
        print("✅ ALL SERVERS STARTED SUCCESSFULLY!")
        print("=" * 70)
        print("\n📋 SERVER STATUS:")
        print("   🌐 Flask App:              http://localhost:5000")
        print("   🎯 A2UI Demo:              http://localhost:5000/a2ui_demo")
        print(f"   💳 PayPal MCP Server:      {PAYPAL_MCP_SERVER_URL}")
        print(f"   🚀 A2UI Protocol Server:   {A2UI_SERVER_URL}")
        print(f"   🔌 A2UI WebSocket:         ws://localhost:{A2UI_PORT}/ws/{{session_id}}")
        print(f"   📖 PayPal Health Check:    {PAYPAL_MCP_SERVER_URL}/health")
        print(f"   📖 A2UI Health Check:      {A2UI_SERVER_URL}/")
        print("\n💡 USAGE:")
        print("   • Open http://localhost:5000 in your browser to access the main application")
        print("   • Try the A2UI demo at http://localhost:5000/a2ui_demo")
        print("   • PayPal MCP Server handles payment processing in the background")
        print("   • A2UI Protocol Server enables real-time UI updates via WebSocket")
        print("   • View cross-sell products below chat window (powered by A2UI)")
        print("   • Press Ctrl+C to stop all servers")
        print("=" * 70)
        
        # Keep the main thread alive and monitor thread health
        check_interval = 10  # Check every 10 seconds
        last_check = time.time()
        
        while True:
            current_time = time.time()
            
            # Periodically check thread status
            if current_time - last_check >= check_interval:
                threads_ok = True
                
                if not flask_thread.is_alive():
                    print("\n❌ Flask App thread died unexpectedly")
                    threads_ok = False
                    
                if not paypal_thread.is_alive():
                    print("\n⚠️ PayPal MCP Server thread died - Attempting restart...")
                    paypal_thread = threading.Thread(
                        target=run_paypal_mcp_server,
                        name="PayPalMCPServer-Restart",
                        daemon=True
                    )
                    paypal_thread.start()
                    time.sleep(3)
                    print("   ✅ PayPal MCP Server restarted")
                    
                if not a2ui_thread.is_alive():
                    print("\n⚠️ A2UI Protocol Server thread died - Attempting restart...")
                    a2ui_thread = threading.Thread(
                        target=run_a2ui_server,
                        name="A2UIProtocolServer-Restart",
                        daemon=True
                    )
                    a2ui_thread.start()
                    time.sleep(3)
                    print("   ✅ A2UI Protocol Server restarted")
                
                if not threads_ok:
                    print("   ⚠️ One or more servers have stopped. Please check the logs.")
                    break
                
                last_check = current_time
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Keyboard interrupt received")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n🔄 Cleaning up...")
        print("   Stopping all servers...")
        os._exit(0)

if __name__ == "__main__":
    main()
