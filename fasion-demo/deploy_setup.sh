#!/bin/bash

################################################################################
# AWS EC2 Deployment Setup Script
# E-commerce AI Assistant Application
# 
# This script automates the initial setup of the application on AWS EC2
# Run this script after connecting to your EC2 instance
################################################################################

set -e  # Exit on any error

echo "======================================"
echo "E-commerce AI Assistant - EC2 Setup"
echo "======================================"
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Variables
APP_DIR="/var/www/ecommerce-ai"
VENV_DIR="$APP_DIR/venv"
PYTHON_VERSION="python3.11"

# Functions
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}→ $1${NC}"
}

# Step 1: Update System
print_info "Updating system packages..."
sudo apt update && sudo apt upgrade -y
print_success "System updated"

# Step 2: Install Python 3.11
print_info "Installing Python 3.11..."
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
print_success "Python 3.11 installed"

# Step 3: Install System Dependencies
print_info "Installing system dependencies..."
sudo apt install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-pip \
    nginx \
    git \
    curl \
    unzip \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev
print_success "System dependencies installed"

# Step 4: Create Application Directory
print_info "Creating application directory..."
sudo mkdir -p $APP_DIR
sudo chown -R $USER:$USER $APP_DIR
cd $APP_DIR
print_success "Application directory created: $APP_DIR"

# Step 5: Setup Python Virtual Environment
print_info "Creating Python virtual environment..."
$PYTHON_VERSION -m venv $VENV_DIR
source $VENV_DIR/bin/activate
print_success "Virtual environment created"

# Step 6: Upgrade pip
print_info "Upgrading pip..."
pip install --upgrade pip setuptools wheel
print_success "Pip upgraded"

# Step 7: Create Directory Structure
print_info "Creating directory structure..."
mkdir -p $APP_DIR/logs
mkdir -p $APP_DIR/image_cache
mkdir -p $APP_DIR/temp_payment_status
mkdir -p $APP_DIR/static
mkdir -p $APP_DIR/templates
mkdir -p $APP_DIR/data
mkdir -p $APP_DIR/modules
print_success "Directory structure created"

# Step 8: Setup Swap (for memory optimization)
print_info "Setting up swap file..."
if [ ! -f /swapfile ]; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    print_success "Swap file created (2GB)"
else
    print_info "Swap file already exists"
fi

# Step 9: Create Gunicorn Config
print_info "Creating Gunicorn configuration..."
cat > $APP_DIR/gunicorn_config.py << 'EOF'
import multiprocessing

# Server socket
bind = "0.0.0.0:8080"
backlog = 2048

# Worker processes
workers = 2
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 2

# Logging
accesslog = "/var/www/ecommerce-ai/logs/access.log"
errorlog = "/var/www/ecommerce-ai/logs/error.log"
loglevel = "info"

# Process naming
proc_name = "ecommerce-ai-assistant"

# Server mechanics
daemon = False
pidfile = "/var/www/ecommerce-ai/gunicorn.pid"
EOF
print_success "Gunicorn configuration created"

# Step 10: Create .env template
print_info "Creating .env template..."
cat > $APP_DIR/.env.template << 'EOF'
# Flask Configuration
SECRET_KEY=your-secure-random-secret-key-here
FLASK_ENV=production

# Google AI API
GOOGLE_API_KEY=your-google-api-key-here

# PayPal Configuration
PAYPAL_MCP_HOST=localhost
PAYPAL_MCP_PORT=8000

# Application Settings
PORT=8080
HOST=0.0.0.0
EOF
print_success ".env template created"

# Step 11: Create systemd service
print_info "Creating systemd service..."
sudo tee /etc/systemd/system/ecommerce-ai.service > /dev/null << 'EOF'
[Unit]
Description=E-commerce AI Assistant Gunicorn Application
After=network.target

[Service]
Type=notify
User=ubuntu
Group=ubuntu
WorkingDirectory=/var/www/ecommerce-ai
Environment="PATH=/var/www/ecommerce-ai/venv/bin"
ExecStart=/var/www/ecommerce-ai/venv/bin/gunicorn \
    --config /var/www/ecommerce-ai/gunicorn_config.py \
    app:app
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
print_success "Systemd service created"

# Step 12: Create Nginx configuration
print_info "Creating Nginx configuration..."
PUBLIC_IP=$(curl -s http://checkip.amazonaws.com)
sudo tee /etc/nginx/sites-available/ecommerce-ai > /dev/null << EOF
server {
    listen 80;
    server_name $PUBLIC_IP;

    client_max_body_size 10M;

    access_log /var/log/nginx/ecommerce-ai-access.log;
    error_log /var/log/nginx/ecommerce-ai-error.log;

    location /static {
        alias /var/www/ecommerce-ai/static;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /image_cache {
        alias /var/www/ecommerce-ai/image_cache;
        expires 7d;
        add_header Cache-Control "public";
    }

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        proxy_connect_timeout 120s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
        
        proxy_buffering off;
    }
}
EOF

# Enable site
sudo ln -sf /etc/nginx/sites-available/ecommerce-ai /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
print_success "Nginx configuration created"

# Step 13: Setup UFW Firewall
print_info "Configuring firewall..."
sudo ufw --force enable
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
print_success "Firewall configured"

# Step 14: Create backup script
print_info "Creating backup script..."
cat > ~/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/home/ubuntu/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

tar -czf $BACKUP_DIR/app_$DATE.tar.gz /var/www/ecommerce-ai \
    --exclude=/var/www/ecommerce-ai/venv \
    --exclude=/var/www/ecommerce-ai/__pycache__

find $BACKUP_DIR -name "app_*.tar.gz" -mtime +7 -delete

echo "Backup completed: app_$DATE.tar.gz"
EOF
chmod +x ~/backup.sh
print_success "Backup script created"

# Step 15: Create deployment helper script
print_info "Creating deployment helper script..."
cat > $APP_DIR/deploy.sh << 'EOF'
#!/bin/bash
# Quick deployment script after git pull

cd /var/www/ecommerce-ai
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart ecommerce-ai
sudo systemctl restart nginx

echo "✓ Application deployed and restarted"
echo "✓ Check status: sudo systemctl status ecommerce-ai"
EOF
chmod +x $APP_DIR/deploy.sh
print_success "Deployment helper created"

echo ""
echo "======================================"
echo "         Setup Complete! 🎉"
echo "======================================"
echo ""
echo "Next Steps:"
echo "1. Transfer your application files to: $APP_DIR"
echo "   scp -i your-key.pem -r * ubuntu@$PUBLIC_IP:$APP_DIR/"
echo ""
echo "2. Configure environment variables:"
echo "   nano $APP_DIR/.env"
echo "   (Use .env.template as reference)"
echo ""
echo "3. Install Python dependencies:"
echo "   cd $APP_DIR"
echo "   source venv/bin/activate"
echo "   pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu"
echo "   pip install -r requirements.txt"
echo ""
echo "4. Start the application:"
echo "   sudo systemctl start ecommerce-ai"
echo "   sudo systemctl restart nginx"
echo ""
echo "5. Access your application:"
echo "   http://$PUBLIC_IP"
echo ""
echo "Useful Commands:"
echo "  - View logs: sudo journalctl -u ecommerce-ai -f"
echo "  - Restart app: sudo systemctl restart ecommerce-ai"
echo "  - Check status: sudo systemctl status ecommerce-ai"
echo ""
print_success "Setup script completed successfully!"
