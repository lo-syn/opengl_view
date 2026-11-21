"""
Example script demonstrating Bluetooth audio streaming with the AudioHandler.
This shows various common use cases and patterns.
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# This would need to be adapted to your actual imports
try:
    from audio_handler import AudioHandler
    from osc_handler import OscHandler
    from bluetooth_audio import BluetoothDevice
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you have all required modules in the same directory")
    sys.exit(1)


def example_1_basic_scan():
    """Example 1: Scan for Bluetooth devices without connecting."""
    print("\n=== Example 1: Scan for Bluetooth Devices ===\n")
    
    try:
        osc_handler = OscHandler()
        audio_handler = AudioHandler(osc_handler, enable_bluetooth=True)
        
        print("Scanning for Bluetooth audio devices...")
        devices = audio_handler.scan_bluetooth_devices()
        
        if not devices:
            print("No Bluetooth devices found")
            return
        
        print(f"\nFound {len(devices)} device(s):\n")
        for i, device in enumerate(devices, 1):
            print(f"{i}. {device.name}")
            print(f"   MAC Address: {device.mac_address}")
            print(f"   Audio Device: {device.is_audio_device}")
            print(f"   Currently Connected: {device.connected}\n")
            
    except Exception as e:
        print(f"Error: {e}")


def example_2_connect_and_play():
    """Example 2: Connect to a Bluetooth device and play audio."""
    print("\n=== Example 2: Connect to Bluetooth Device and Play Audio ===\n")
    
    try:
        osc_handler = OscHandler()
        audio_handler = AudioHandler(osc_handler, enable_bluetooth=True)
        
        # Scan for devices
        print("Scanning for Bluetooth audio devices...")
        devices = audio_handler.scan_bluetooth_devices()
        
        if not devices:
            print("No Bluetooth devices found")
            return
        
        # Connect to first audio device
        device = None
        for d in devices:
            if d.is_audio_device:
                device = d
                break
        
        if not device:
            device = devices[0]
            print(f"Warning: No audio-specific device found, using {device.name}")
        
        print(f"\nConnecting to {device.name}...")
        if audio_handler.connect_bluetooth_device(device, set_as_default=True):
            print("✓ Successfully connected!")
            
            # Save configuration for future use
            if audio_handler.save_bluetooth_config():
                print("✓ Configuration saved")
            
            # Play audio
            print("\nStarting audio playback...")
            audio_handler.play()
            print("✓ Playing audio through Bluetooth")
            
            # Keep running for a bit
            import time
            time.sleep(5)
            
            audio_handler.stop()
            print("\nStopped playback")
        else:
            print("✗ Failed to connect to device")
            
    except Exception as e:
        print(f"Error: {e}")


def example_3_auto_reconnect():
    """Example 3: Auto-reconnect to previously used device."""
    print("\n=== Example 3: Auto-reconnect to Previous Device ===\n")
    
    try:
        osc_handler = OscHandler()
        audio_handler = AudioHandler(osc_handler, enable_bluetooth=True)
        
        print("Attempting to reconnect to previously used device...")
        if audio_handler.load_bluetooth_config():
            print("✓ Successfully reconnected!")
            if audio_handler.bluetooth_manager:
                device = audio_handler.bluetooth_manager.current_device
                if device:
                    print(f"  Device: {device.name}")
                    print(f"  MAC Address: {device.mac_address}")
        else:
            print("✗ No previous device configuration found")
            print("  Tip: Connect to a device first to save configuration")
            
    except Exception as e:
        print(f"Error: {e}")


def example_4_switch_outputs():
    """Example 4: Switch between Bluetooth and default audio output."""
    print("\n=== Example 4: Switch Between Audio Outputs ===\n")
    
    try:
        osc_handler = OscHandler()
        audio_handler = AudioHandler(osc_handler, enable_bluetooth=True)
        
        # Scan for devices
        devices = audio_handler.scan_bluetooth_devices()
        if not devices:
            print("No Bluetooth devices found")
            return
        
        device = devices[0]
        
        # Play through default output
        print("Playing through default audio output...")
        audio_handler.play()
        import time
        time.sleep(2)
        
        # Switch to Bluetooth
        print(f"\nSwitching to Bluetooth output ({device.name})...")
        if audio_handler.enable_bluetooth_output(device):
            print("✓ Now playing through Bluetooth")
            time.sleep(2)
            
            # Switch back to default
            print("\nSwitching back to default audio output...")
            audio_handler.disable_bluetooth_output()
            print("✓ Back to default output")
            time.sleep(2)
        
        audio_handler.stop()
        
    except Exception as e:
        print(f"Error: {e}")


def example_5_check_status():
    """Example 5: Check current Bluetooth connection status."""
    print("\n=== Example 5: Check Bluetooth Status ===\n")
    
    try:
        osc_handler = OscHandler()
        audio_handler = AudioHandler(osc_handler, enable_bluetooth=True)
        
        # Check if Bluetooth is active
        print(f"Bluetooth output active: {audio_handler.use_bluetooth}")
        
        # Get connected devices
        connected = audio_handler.get_connected_bluetooth_devices()
        print(f"\nCurrently connected devices: {len(connected)}")
        for device in connected:
            print(f"  - {device.name} ({device.mac_address})")
        
        if not connected:
            print("  None")
        
    except Exception as e:
        print(f"Error: {e}")


def example_6_safe_connect():
    """Example 6: Safe connection with error handling."""
    print("\n=== Example 6: Safe Connection with Error Handling ===\n")
    
    try:
        osc_handler = OscHandler()
        audio_handler = AudioHandler(osc_handler, enable_bluetooth=True)
        
        print("Scanning for Bluetooth devices...")
        devices = audio_handler.scan_bluetooth_devices()
        
        if not devices:
            print("No devices found")
            return
        
        # Try to connect with retry logic
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            device = devices[0]
            print(f"\nAttempt {attempt}/{max_retries} to connect to {device.name}...")
            
            if audio_handler.connect_bluetooth_device(device):
                print("✓ Connection successful!")
                
                # Verify by checking connected devices
                connected = audio_handler.get_connected_bluetooth_devices()
                if connected:
                    print(f"✓ Verified: {len(connected)} device(s) connected")
                break
            else:
                print(f"✗ Connection failed")
                if attempt < max_retries:
                    print(f"  Retrying in 2 seconds...")
                    import time
                    time.sleep(2)
        else:
            print("\n✗ Failed to connect after all retries")
            
    except Exception as e:
        print(f"Error: {e}")


def print_menu():
    """Print the example menu."""
    print("\n" + "="*50)
    print("Bluetooth Audio Handler - Examples")
    print("="*50)
    print("\n1. Scan for Bluetooth devices")
    print("2. Connect to device and play audio")
    print("3. Auto-reconnect to previous device")
    print("4. Switch between audio outputs")
    print("5. Check Bluetooth status")
    print("6. Safe connection with error handling")
    print("0. Exit\n")


def main():
    """Run the example menu."""
    while True:
        print_menu()
        choice = input("Select an example (0-6): ").strip()
        
        try:
            if choice == '0':
                print("\nGoodbye!")
                break
            elif choice == '1':
                example_1_basic_scan()
            elif choice == '2':
                example_2_connect_and_play()
            elif choice == '3':
                example_3_auto_reconnect()
            elif choice == '4':
                example_4_switch_outputs()
            elif choice == '5':
                example_5_check_status()
            elif choice == '6':
                example_6_safe_connect()
            else:
                print("Invalid choice. Please try again.")
        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            break
        except Exception as e:
            print(f"\nError: {e}")
        
        input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()
