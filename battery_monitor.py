#!/usr/bin/env python3
import time
import json
import argparse
import os
import platform
import sys
from datetime import datetime

# Fix import for FordPassAPI - handle different module naming conventions
try:
    from fordpass_api import FordPassAPI
except ImportError:
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("fordpass_module", "fordpass-api.py")
        fordpass_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fordpass_module)
        FordPassAPI = fordpass_module.FordPassAPI
    except ImportError:
        try:
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            if os.path.exists("fordpass_api.py"):
                from fordpass_api import FordPassAPI
            elif os.path.exists("fordpass-api.py"):
                import importlib.util
                spec = importlib.util.spec_from_file_location("fordpass_module", "fordpass-api.py")
                fordpass_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(fordpass_module)
                FordPassAPI = fordpass_module.FordPassAPI
            else:
                print("Could not import FordPassAPI. Make sure fordpass-api.py or fordpass_api.py is in the same directory.")
                sys.exit(1)
        except ImportError:
            print("Could not import FordPassAPI. Make sure fordpass-api.py or fordpass_api.py is in the same directory.")
            sys.exit(1)

# Platform detection
PLATFORM = platform.system()
print(f"Detected platform: {PLATFORM}")

# Windows-specific imports
if PLATFORM == "Windows":
    try:
        from win10toast import ToastNotifier
        win_toaster = ToastNotifier()
        win_notification_available = True
    except ImportError:
        win_notification_available = False
        print("win10toast package not installed. For Windows notifications, install with: pip install win10toast")

# Linux-specific imports
if PLATFORM == "Linux":
    # Try multiple notification methods for Linux
    linux_notification_method = None
    
    # Try GObject Introspection first
    try:
        import gi
        gi.require_version('Notify', '0.7')
        from gi.repository import Notify
        Notify.init("FordPass Battery Monitor")
        linux_notification_method = "gi"
    except (ImportError, ValueError):
        # Try notify2 next
        try:
            import notify2
            notify2.init("FordPass Battery Monitor")
            linux_notification_method = "notify2"
        except ImportError:
            # Last resort - check if notify-send is available
            try:
                import subprocess
                subprocess.run(["notify-send", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                linux_notification_method = "notify-send"
            except (ImportError, FileNotFoundError):
                print("No notification method available on Linux. Install either python3-notify2, python3-gi, or libnotify-bin package.")
                linux_notification_method = None

class BatteryMonitor:
    def __init__(self, username, password, vin, interval=60, config_file="battery_monitor_config.json"):
        """
        Initialize the battery monitor
        
        Args:
            username (str): FordPass username/email
            password (str): FordPass password
            vin (str): Vehicle identification number
            interval (int): Polling interval in seconds (default: 60)
            config_file (str): Path to config file for saving last known state
        """
        self.ford_api = FordPassAPI(username, password, vin)
        self.interval = interval
        self.config_file = config_file
        self.last_range = None
        self.last_charge = None
        
        # Load previous state if available
        self.load_state()

    def load_state(self):
        """Load the previous battery state if available"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.last_range = data.get('last_range')
                    self.last_charge = data.get('last_charge')
                    print(f"Loaded previous state: Range: {self.last_range} miles, Charge: {self.last_charge}%")
            except Exception as e:
                print(f"Error loading previous state: {e}")

    def save_state(self):
        """Save the current battery state"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump({
                    'last_range': self.last_range,
                    'last_charge': self.last_charge,
                    'last_update': time.strftime("%Y-%m-%d %H:%M:%S")
                }, f)
        except Exception as e:
            print(f"Error saving state: {e}")

    def show_notification(self, title, message):
        """
        Show a platform-specific notification
        
        Args:
            title (str): Notification title
            message (str): Notification message
        """
        try:
            # Windows notifications
            if PLATFORM == "Windows":
                if win_notification_available:
                    win_toaster.show_toast(title, message, duration=10, threaded=True)
                    return True
                else:
                    # Fallback for Windows
                    print(f"[NOTIFICATION] {title}: {message}")
                    return False
                    
            # macOS notifications
            elif PLATFORM == "Darwin":
                try:
                    # Escape double quotes in the message
                    message_esc = message.replace('"', '\\"')
                    title_esc = title.replace('"', '\\"')
                    script = f'display notification "{message_esc}" with title "{title_esc}"'
                    os.system(f"osascript -e '{script}'")
                    return True
                except Exception as e:
                    print(f"Error showing macOS notification: {e}")
                    return False
                    
            # Linux notifications
            elif PLATFORM == "Linux":
                if linux_notification_method == "gi":
                    notification = gi.repository.Notify.Notification.new(title, message)
                    notification.set_urgency(1)  # Normal urgency
                    return notification.show()
                    
                elif linux_notification_method == "notify2":
                    notification = notify2.Notification(title, message)
                    notification.set_urgency(notify2.URGENCY_NORMAL)
                    return notification.show()
                    
                elif linux_notification_method == "notify-send":
                    subprocess.run(["notify-send", title, message])
                    return True
                    
                else:
                    # Fallback for Linux
                    print(f"[NOTIFICATION] {title}: {message}")
                    return False
                    
            # Other platforms - just log
            else:
                print(f"[NOTIFICATION] {title}: {message}")
                return False
                
        except Exception as e:
            print(f"Error showing notification: {e}")
            # Always print the message to terminal as fallback
            print(f"\n{title}: {message}")
            return False

    def check_battery(self):
        """Check the battery status and show notification if changed"""
        try:
            battery_info = self.ford_api.get_battery_status()
            
            # Get the raw values
            raw_range = battery_info.get('ev_battery_range_miles')
            raw_charge = battery_info.get('ev_battery_actual_charge')
            
            if raw_range is None or raw_charge is None:
                print("Battery information not available")
                return False
            
            # Round values to the nearest whole number
            current_range = round(raw_range) if raw_range is not None else None
            current_charge = round(raw_charge) if raw_charge is not None else None
            
            # Format values for display
            current_range_str = str(current_range) if current_range is not None else "N/A"
            current_charge_str = str(current_charge) if current_charge is not None else "N/A"
            
            # Print current values regardless of change
            print(f"Current battery status - Range: {current_range_str} miles, Charge: {current_charge_str}%")
            
            # Check if values have changed AND if we have previous values to compare against
            # This prevents notification on first run
            if (self.last_range is not None and self.last_charge is not None and 
                (current_range != self.last_range or current_charge != self.last_charge)):
                
                # Create notification message
                change_message = ""
                if current_range != self.last_range:
                    change = current_range - self.last_range
                    direction = "increased" if change > 0 else "decreased"
                    change_message += f"Range has {direction} by {abs(change)} miles. "
                
                if current_charge != self.last_charge:
                    change = current_charge - self.last_charge
                    direction = "increased" if change > 0 else "decreased"
                    change_message += f"Charge has {direction} by {abs(change)}%. "
                
                # Show notification
                title = "Ford EV Battery Update"
                message = f"Range: {current_range_str} miles\nCharge: {current_charge_str}%\n{change_message}"
                self.show_notification(title, message)
                
                # Update stored values
                self.last_range = current_range
                self.last_charge = current_charge
                self.save_state()
                
                return True
            else:
                # Still update stored values even if no notification is shown
                # This will also happen on first run
                self.last_range = current_range
                self.last_charge = current_charge
                self.save_state()
                return False
            
        except Exception as e:
            print(f"Error checking battery: {e}")
            return False

    def run(self):
        """Run the battery monitor in a loop"""
        print(f"Starting FordPass Battery Monitor on {PLATFORM}. Checking every {self.interval} seconds.")
        
        while True:
            try:
                # Record the check time
                check_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"Checking battery status at {check_time}")
                
                changed = self.check_battery()
                if changed:
                    print("Battery status changed - notification displayed")
                else:
                    print("No change in battery status")
                
                # Sleep for the configured interval
                print(f"Sleeping for {self.interval} seconds...")
                time.sleep(self.interval)
            except KeyboardInterrupt:
                print("\nMonitor stopped by user")
                break
            except Exception as e:
                print(f"Unexpected error: {str(e)}")
                print("Retrying in 30 seconds...")
                time.sleep(30)

def run_monitor(args):
    """Run the monitor with the given arguments"""
    # Get credentials
    username = args.username
    password = args.password
    vin = args.vin
    
    # Check for credentials in environment variables
    if not username:
        username = os.environ.get('FORDPASS_USERNAME')
    if not password:
        password = os.environ.get('FORDPASS_PASSWORD')
    if not vin:
        vin = os.environ.get('FORDPASS_VIN')
    
    # If still missing, prompt for credentials
    if not username:
        username = input("Enter your FordPass username/email: ")
    if not password:
        try:
            import getpass
            password = getpass.getpass("Enter your FordPass password: ")
        except ImportError:
            password = input("Enter your FordPass password: ")
    if not vin:
        vin = input("Enter your vehicle VIN: ")
    
    # Log the startup
    print(f"Starting FordPass Battery Monitor for VIN: {vin}")
    print(f"Checking every {args.interval} seconds")
    
    # Create and run the monitor
    monitor = BatteryMonitor(username, password, vin, args.interval, args.config)
    monitor.run()

def main():
    """Main function to parse arguments and start the monitor"""
    parser = argparse.ArgumentParser(description='Monitor Ford EV battery status and show notifications on changes')
    parser.add_argument('--username', '-u', help='FordPass username/email')
    parser.add_argument('--password', '-p', help='FordPass password')
    parser.add_argument('--vin', '-v', help='Vehicle identification number')
    parser.add_argument('--interval', '-i', type=int, default=60, 
                        help='Check interval in seconds (default: 60)')
    parser.add_argument('--config', '-c', default='battery_monitor_config.json',
                        help='Config file path for saving state')
    
    # Add daemon mode option only for Linux and macOS
    if PLATFORM != "Windows":
        parser.add_argument('--daemon', '-d', action='store_true',
                            help='Run as a daemon in the background (Linux/macOS only)')
    
    args = parser.parse_args()
    
    # Run as daemon if requested (Linux/macOS only)
    if PLATFORM != "Windows" and hasattr(args, 'daemon') and args.daemon:
        try:
            import daemon
            with daemon.DaemonContext():
                run_monitor(args)
        except ImportError:
            print("python-daemon package not installed. Running in foreground instead.")
            run_monitor(args)
    else:
        # For Windows, we'll just run normally
        run_monitor(args)

if __name__ == "__main__":
    main()
