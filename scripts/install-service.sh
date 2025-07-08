#!/bin/bash

# Ollama Discord Bot - Service Installation Script

SERVICE_NAME="ollama-discord"
SERVICE_FILE="${SERVICE_NAME}.service"
USER_SERVICE_DIR="$HOME/.config/systemd/user"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if service file exists
check_service_file() {
    if [ ! -f "$SERVICE_FILE" ]; then
        print_error "Service file '$SERVICE_FILE' not found in current directory."
        echo "Make sure you're running this script from the ollama-discord directory."
        exit 1
    fi
}

# Function to install service
install_service() {
    print_status "Installing Ollama Discord Bot as user service..."
    
    # Create user systemd directory if it doesn't exist
    mkdir -p "$USER_SERVICE_DIR"
    
    # Copy service file
    cp "$SERVICE_FILE" "$USER_SERVICE_DIR/"
    print_status "Service file copied to $USER_SERVICE_DIR/"
    
    # Reload systemd user daemon
    systemctl --user daemon-reload
    print_status "Systemd user daemon reloaded"
    
    # Enable service
    systemctl --user enable "$SERVICE_NAME.service"
    print_status "Service enabled (will start on login)"
    
    # Start service
    systemctl --user start "$SERVICE_NAME.service"
    print_status "Service started"
    
    # Check status
    if systemctl --user is-active --quiet "$SERVICE_NAME.service"; then
        print_status "Service is running successfully!"
    else
        print_error "Service failed to start. Check logs with: journalctl --user -u $SERVICE_NAME.service"
        exit 1
    fi
}

# Function to uninstall service
uninstall_service() {
    print_status "Uninstalling Ollama Discord Bot service..."
    
    # Stop service
    systemctl --user stop "$SERVICE_NAME.service" 2>/dev/null
    print_status "Service stopped"
    
    # Disable service
    systemctl --user disable "$SERVICE_NAME.service" 2>/dev/null
    print_status "Service disabled"
    
    # Remove service file
    rm -f "$USER_SERVICE_DIR/$SERVICE_FILE"
    print_status "Service file removed"
    
    # Reload daemon
    systemctl --user daemon-reload
    print_status "Systemd user daemon reloaded"
    
    print_status "Service uninstalled successfully!"
}

# Function to show service status
show_status() {
    print_status "Service Status:"
    systemctl --user status "$SERVICE_NAME.service"
}

# Function to show service logs
show_logs() {
    print_status "Service Logs (last 50 lines):"
    journalctl --user -u "$SERVICE_NAME.service" -n 50
}

# Function to follow service logs
follow_logs() {
    print_status "Following service logs (Ctrl+C to stop):"
    journalctl --user -u "$SERVICE_NAME.service" -f
}

# Function to show help
show_help() {
    echo "Ollama Discord Bot Service Management"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  install     Install and start the service"
    echo "  uninstall   Stop and remove the service"
    echo "  status      Show service status"
    echo "  logs        Show recent service logs"
    echo "  follow      Follow service logs in real-time"
    echo "  help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 install    # Install and start the service"
    echo "  $0 status     # Check if service is running"
    echo "  $0 logs       # View recent log entries"
    echo ""
}

# Main script logic
case "$1" in
    install)
        check_service_file
        install_service
        ;;
    uninstall)
        uninstall_service
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    follow)
        follow_logs
        ;;
    help|--help|-h)
        show_help
        ;;
    "")
        print_warning "No command specified. Use 'help' for usage information."
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac