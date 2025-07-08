#!/bin/bash

# Ollama Discord Bot - Log Tailing Script

SERVICE_NAME="ollama-discord"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

print_header() {
    echo -e "${BLUE}$1${NC}"
}

# Function to check if service is running
check_service_running() {
    if systemctl --user is-active --quiet "$SERVICE_NAME.service"; then
        return 0
    else
        return 1
    fi
}

# Function to show service info
show_service_info() {
    print_header "=== Ollama Discord Bot Service Information ==="
    echo ""
    
    if check_service_running; then
        print_status "Service is running"
        echo "Status: $(systemctl --user is-active $SERVICE_NAME.service)"
        echo "Since: $(systemctl --user show $SERVICE_NAME.service --property=ActiveEnterTimestamp --value | cut -d' ' -f2-)"
        
        # Try to determine if it's production or development mode
        if systemctl --user show $SERVICE_NAME.service --property=ExecStart --value | grep -q "entr"; then
            echo "Mode: Development (auto-restart enabled)"
        else
            echo "Mode: Production"
        fi
    else
        print_warning "Service is not running"
        echo "To start the service:"
        echo "  Production: scripts/install-service.sh install"
        echo "  Development: scripts/install-service.sh install --dev"
    fi
    echo ""
}

# Function to tail logs with options
tail_logs() {
    local lines="$1"
    local follow="$2"
    
    if ! check_service_running; then
        print_error "Service is not running. No logs to show."
        echo ""
        echo "Start the service first:"
        echo "  scripts/install-service.sh install      # Production mode"
        echo "  scripts/install-service.sh install --dev # Development mode"
        exit 1
    fi
    
    if [ "$follow" = "true" ]; then
        print_header "=== Following logs (Ctrl+C to stop) ==="
        echo ""
        if [ -n "$lines" ]; then
            journalctl --user -u "$SERVICE_NAME.service" -f -n "$lines"
        else
            journalctl --user -u "$SERVICE_NAME.service" -f
        fi
    else
        print_header "=== Recent logs (last $lines lines) ==="
        echo ""
        journalctl --user -u "$SERVICE_NAME.service" -n "$lines" --no-pager
    fi
}

# Function to show help
show_help() {
    echo "Ollama Discord Bot - Log Tailing Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -f, --follow       Follow logs in real-time (like tail -f)"
    echo "  -n, --lines NUM    Show last NUM lines (default: 50)"
    echo "  -i, --info         Show service information"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                 # Show last 50 lines"
    echo "  $0 -f              # Follow logs in real-time"
    echo "  $0 -n 100          # Show last 100 lines"
    echo "  $0 -f -n 20        # Follow logs, starting with last 20 lines"
    echo "  $0 -i              # Show service information"
    echo ""
    echo "Shortcuts:"
    echo "  scripts/install-service.sh logs    # Show recent logs"
    echo "  scripts/install-service.sh follow  # Follow logs"
    echo "  scripts/install-service.sh status  # Service status"
    echo ""
}

# Default values
LINES=50
FOLLOW=false
SHOW_INFO=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -n|--lines)
            LINES="$2"
            shift 2
            ;;
        -i|--info)
            SHOW_INFO=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate lines parameter
if ! [[ "$LINES" =~ ^[0-9]+$ ]]; then
    print_error "Lines parameter must be a number: $LINES"
    exit 1
fi

# Main logic
if [ "$SHOW_INFO" = "true" ]; then
    show_service_info
else
    show_service_info
    tail_logs "$LINES" "$FOLLOW"
fi