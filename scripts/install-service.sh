#!/bin/bash

# Ollama Discord Bot - Service Installation Script

SERVICE_NAME="ollama-discord"
SERVICE_FILE="${SERVICE_NAME}.service"
DEV_SERVICE_FILE="${SERVICE_NAME}-dev.service"
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
    local file="$1"
    if [ ! -f "$file" ]; then
        print_error "Service file '$file' not found in current directory."
        echo "Make sure you're running this script from the ollama-discord directory."
        exit 1
    fi
}

# Function to check if entr is available
check_entr() {
    if ! command -v entr &> /dev/null; then
        print_error "entr command not found. Please install it first:"
        echo "  Ubuntu/Debian: sudo apt install entr"
        echo "  macOS: brew install entr"
        echo "  Arch Linux: sudo pacman -S entr"
        exit 1
    fi
}

# Function to install service
install_service() {
    local dev_mode="$1"
    local service_file="$SERVICE_FILE"
    local mode_desc="production"
    
    if [ "$dev_mode" = "--dev" ]; then
        check_entr
        service_file="$DEV_SERVICE_FILE"
        mode_desc="development (with auto-restart)"
    fi
    
    check_service_file "$service_file"
    
    print_status "Installing Ollama Discord Bot as user service ($mode_desc)..."
    
    # Create user systemd directory if it doesn't exist
    mkdir -p "$USER_SERVICE_DIR"
    
    # Copy service file
    cp "$service_file" "$USER_SERVICE_DIR/$SERVICE_FILE"
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
        if [ "$dev_mode" = "--dev" ]; then
            print_status "Development service is running successfully!"
            print_status "The bot will automatically restart when you modify .py or .yaml files."
        else
            print_status "Production service is running successfully!"
        fi
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
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  install [--dev]  Install and start the service"
    echo "  uninstall        Stop and remove the service"
    echo "  status           Show service status"
    echo "  logs             Show recent service logs"
    echo "  follow           Follow service logs in real-time"
    echo "  help             Show this help message"
    echo ""
    echo "Options:"
    echo "  --dev           Install in development mode with auto-restart on file changes"
    echo "                  (requires 'entr' to be installed)"
    echo ""
    echo "Examples:"
    echo "  $0 install           # Install production service"
    echo "  $0 install --dev     # Install development service with auto-restart"
    echo "  $0 status            # Check if service is running"
    echo "  $0 logs              # View recent log entries"
    echo ""
    echo "Development mode requirements:"
    echo "  Ubuntu/Debian: sudo apt install entr"
    echo "  macOS: brew install entr"
    echo "  Arch Linux: sudo pacman -S entr"
    echo ""
}

# Main script logic
case "$1" in
    install)
        install_service "$2"
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