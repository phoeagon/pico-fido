#!/usr/bin/env python3
"""
Pico FIDO Commissioner Tool
A Python alternative to PicoKey App for configuring Pico FIDO devices.

This tool uses CTAP2 authenticatorConfig vendor commands to safely
configure device settings without direct flash manipulation.
"""

from fido2.hid import CtapHidDevice as CtaphidDevice
from fido2.ctap2.base import Ctap2
from fido2.ctap2.pin import ClientPin, PinProtocol
import sys
import os
from typing import Optional, Tuple
import getpass
import hmac
import hashlib
import cbor2

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, Confirm
console = Console()


def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


CTAP_AUTHENTICATOR_CONFIG = 0x0D

CTAP_CONFIG_PHY_VIDPID = 0x6fcb19b0cbe3acfa
CTAP_CONFIG_PHY_LED_BTNESS = 0x76a85945985d02fd
CTAP_CONFIG_PHY_LED_GPIO = 0x7b392a394de9f948
CTAP_CONFIG_PHY_OPTS = 0x269f3b09eceb805f
CTAP_CONFIG_PHY_UP_BTN = 0x1a2b3c4d5e6f7890

PHY_OPT_WCID = 0x1
PHY_OPT_DIMM = 0x2
PHY_OPT_DISABLE_POWER_RESET = 0x4
PHY_OPT_LED_STEADY = 0x8


class PicoFIDODevice:
    """Wrapper for Pico FIDO device communication"""
    
    def __init__(self):
        self.dev = None
        self.ctap2 = None
        self.info = None
        self.client_pin = None
        self.pin_token = None
        self.pin_protocol = None
        
    def find_device(self) -> bool:
        """Find and connect to Pico FIDO device"""
        devices = list(CtaphidDevice.list_devices())
        if not devices:
            return False
        
        self.dev = devices[0]
        self.ctap2 = Ctap2(self.dev)
        
        try:
            self.info = self.ctap2.get_info()
            return True
        except Exception as e:
            print(f"Error getting device info: {e}")
            return False
    
    def get_device_name(self) -> str:
        """Get device product name"""
        if self.dev:
            return self.dev.descriptor.product_name or "Unknown Device"
        return "No Device"
    
    def get_vid_pid(self) -> Tuple[int, int]:
        """Get device VID and PID"""
        if self.dev and hasattr(self.dev.descriptor, 'vid') and hasattr(self.dev.descriptor, 'pid'):
            return (self.dev.descriptor.vid, self.dev.descriptor.pid)
        return (0, 0)
    
    def get_pin_token(self, pin: str = None) -> bool:
        """Get PIN token with authenticatorConfig permission"""
        try:
            if not self.ctap2:
                return False
            
            if not self.info.options.get("clientPin"):
                print("⚠ Device does not support PIN")
                return False
            
            self.client_pin = ClientPin(self.ctap2)
            
            if hasattr(self.client_pin, 'protocol') and self.client_pin.protocol:
                self.pin_protocol = self.client_pin.protocol
            else:
                try:
                    from fido2.ctap2.pin import PinProtocolV2
                    self.pin_protocol = PinProtocolV2()
                except:
                    from fido2.ctap2.pin import PinProtocolV1
                    self.pin_protocol = PinProtocolV1()
            
            if pin is None:
                pin = getpass.getpass("→ Enter device PIN: ")
            
            PERMISSION_ACFG = 0x20
            
            self.pin_token = self.client_pin.get_pin_token(pin, PERMISSION_ACFG)
            
            return True
            
        except Exception as e:
            print(f"✗ PIN authentication failed: {e}")
            return False
    
    def reset_device(self) -> bool:
        """Reset the device to factory defaults"""
        try:
            if not self.ctap2:
                return False
            
            print("\n⚠ You must press the physical button on your device to confirm!")
            print("Waiting for button press...")
            
            self.ctap2.reset()
            
            self.info = self.ctap2.get_info()
            self.pin_token = None
            self.client_pin = None
            
            return True
            
        except Exception as e:
            error_msg = str(e)
            if "NOT_ALLOWED" in error_msg or "0x30" in error_msg:
                print(f"\n✗ Reset not allowed!")
                print("\nPossible reasons:")
                print("  1. More than 10 seconds since device power-on")
                print("  2. Firmware not compiled with ENABLE_POWER_ON_RESET")
                print("  3. PHY_OPT_DISABLE_POWER_RESET flag is set")
                print("\nTo reset:")
                print("  • Unplug the device")
                print("  • Replug the device")
                print("  • Run reset within 10 seconds")
            elif "TIMEOUT" in error_msg or "0x2f" in error_msg:
                print(f"\n✗ Button press timeout!")
                print("You didn't press the button in time.")
            else:
                print(f"✗ Reset failed: {e}")
            return False
    
    def set_pin(self, new_pin: str = None) -> bool:
        """Set a new PIN on the device or change existing PIN"""
        try:
            if not self.ctap2:
                return False
            
            if not self.client_pin:
                self.client_pin = ClientPin(self.ctap2)
            
            has_pin = self.info.options.get("clientPin", False)
            
            if has_pin:
                print("→ Device already has a PIN set. You can change it.")
                old_pin = getpass.getpass("→ Enter current PIN: ")
                if new_pin is None:
                    new_pin = getpass.getpass("→ Enter new PIN (min 4 chars): ")
                    confirm_pin = getpass.getpass("→ Confirm new PIN: ")
                    
                    if new_pin != confirm_pin:
                        print("✗ PINs don't match!")
                        return False
                
                self.client_pin.change_pin(old_pin, new_pin)
                print("✓ PIN changed successfully!")
            else:
                print("→ Setting up PIN for the first time")
                if new_pin is None:
                    new_pin = getpass.getpass("→ Enter new PIN (min 4 chars): ")
                    confirm_pin = getpass.getpass("→ Confirm new PIN: ")
                    
                    if new_pin != confirm_pin:
                        print("✗ PINs don't match!")
                        return False
                
                if len(new_pin) < 4:
                    print("✗ PIN must be at least 4 characters!")
                    return False
                
                self.client_pin.set_pin(new_pin)
                print("✓ PIN set successfully!")
                
                self.info = self.ctap2.get_info()
            
            self.pin_token = None
            
            return True
            
        except Exception as e:
            print(f"✗ Failed to set/change PIN: {e}")
            return False
    
    def send_config_command(self, vendor_command_id: int, param_value: int) -> bool:
        """Send a vendor configuration command to the device"""
        try:
            if not self.pin_token:
                if not self.get_pin_token():
                    return False
            
            subcommand_params = {
                0x01: vendor_command_id,
                0x03: param_value
            }
            
            subcommand_bytes = cbor2.dumps(subcommand_params)
            
            message = b'\xff' * 32 + b'\x0d' + b'\xff' + subcommand_bytes
            
            pin_auth = self.pin_protocol.authenticate(self.pin_token, message)
            
            config_data = {
                0x01: 0xFF,
                0x02: subcommand_params,
                0x03: self.pin_protocol.VERSION,
                0x04: pin_auth
            }
            
            response = self.ctap2.send_cbor(CTAP_AUTHENTICATOR_CONFIG, config_data)
            
            return True
            
        except Exception as e:
            print(f"Configuration failed: {e}")
            self.pin_token = None
            return False


def print_header():
    """Print tool header"""
    console.print(Panel.fit(
        "[bold cyan]Pico FIDO Commissioner[/bold cyan]\n"
        "[dim]Configure your Pico FIDO device settings[/dim]",
        border_style="cyan"
    ))


def print_menu():
    """Print main menu"""
    table = Table(title="", show_header=False)
    table.add_column("Option", style="cyan")
    table.add_column("Description", style="white")
    
    table.add_row("1", "Configure Button Press Timeout")
    table.add_row("2", "Configure LED Settings")
    table.add_row("3", "Configure PHY Options")
    table.add_row("4", "Configure VID/PID")
    table.add_row("5", "View Device Information")
    table.add_row("6", "Set/Change Device PIN")
    table.add_row("7", "[RESET] Factory Reset Device")
    table.add_row("0", "Exit")
    
    console.print(table)


def configure_button_timeout(device: PicoFIDODevice) -> bool:
    """Configure user presence button timeout"""
    console.print("\n[bold cyan]Button Press Configuration[/bold cyan]")
    console.print("[dim]Set the timeout for physical button confirmation[/dim]\n")
    
    print("Current options:")
    print("  0 = Disabled (no button press required)")
    print("  1-255 = Timeout in seconds")
    print("  Recommended: 30 seconds")
    
    try:
        timeout = IntPrompt.ask("\nEnter timeout value", default=30)
        
        if timeout < 0 or timeout > 255:
            print("✗ Error: Timeout must be between 0-255")
            return False
        
        print(f"\n→ Configuring button timeout to {timeout} seconds...")
        
        success = device.send_config_command(CTAP_CONFIG_PHY_UP_BTN, timeout)
        
        if success:
            if timeout == 0:
                print("✓ Button confirmation disabled")
            else:
                print(f"✓ Button confirmation enabled with {timeout} second timeout")
            return True
        else:
            print("✗ Configuration failed")
            print("\nPossible reasons:")
            print("  • Firmware doesn't have PHY_UP_BTN handler (need to rebuild)")
            print("  • Device requires PIN authentication")
            return False
            
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def configure_led_settings(device: PicoFIDODevice):
    """Configure LED brightness and GPIO"""
    console.print("\n[bold cyan]LED Configuration[/bold cyan]")
    
    print("\nLED Configuration Options:")
    print("  1. Set LED GPIO Pin")
    print("  2. Set LED Brightness")
    print("  0. Back to main menu")
    
    try:
        choice = input("\nSelect option (0-2): ").strip()
        
        if choice == "0":
            return
        elif choice == "1":
            print("\nLED GPIO Pin Configuration")
            print("Enter the GPIO pin number for your LED (e.g., 25 for Pico)")
            print("Common values:")
            print("  - Raspberry Pi Pico: 25")
            print("  - Waveshare RP2350-One: Check your board documentation")
            
            gpio_pin = int(input("\nEnter GPIO pin number (0-29): ") or "25")
            
            if gpio_pin < 0 or gpio_pin > 29:
                print("✗ Error: GPIO pin must be between 0-29")
                return
            
            print(f"\n→ Setting LED GPIO to pin {gpio_pin}...")
            success = device.send_config_command(CTAP_CONFIG_PHY_LED_GPIO, gpio_pin)
            
            if success:
                print(f"✓ LED GPIO configured to pin {gpio_pin}")
            else:
                print("✗ Configuration failed")
                
        elif choice == "2":
            print("\nLED Brightness Configuration")
            print("Enter brightness value (0-255):")
            print("  0 = Off/Very dim")
            print("  128 = Medium brightness")
            print("  255 = Maximum brightness")
            print("  Recommended: 128")
            
            brightness = int(input("\nEnter brightness (0-255): ") or "128")
            
            if brightness < 0 or brightness > 255:
                print("✗ Error: Brightness must be between 0-255")
                return
            
            print(f"\n→ Setting LED brightness to {brightness}...")
            success = device.send_config_command(CTAP_CONFIG_PHY_LED_BTNESS, brightness)
            
            if success:
                print(f"✓ LED brightness set to {brightness}")
            else:
                print("✗ Configuration failed")
        else:
            print("✗ Invalid option")
            
    except ValueError:
        print("✗ Error: Invalid input")
    except Exception as e:
        print(f"✗ Error: {e}")


def configure_phy_options(device: PicoFIDODevice):
    """Configure PHY option flags"""
    console.print("\n[bold cyan]PHY Options Configuration[/bold cyan]")
    
    print("\nPHY Options are bit flags that control device behavior:")
    print(f"  Bit 0x1 (1): WebCCID Interface")
    print(f"  Bit 0x2 (2): Dim LED")
    print(f"  Bit 0x4 (4): Disable 10-second power-on reset window")
    print(f"  Bit 0x8 (8): Steady LED (no blinking)")
    
    print("\nYou can combine flags by adding their values:")
    print("  Example: 6 = Dim LED (2) + Disable power reset (4)")
    
    print("\nCommon configurations:")
    print("  0  = Default (all features enabled, blinking LED)")
    print("  2  = Dim LED only")
    print("  4  = Disable 10s reset window only")
    print("  6  = Dim LED + Disable reset window")
    print("  8  = Steady LED (no blinking)")
    print("  10 = Dim + Steady LED")
    
    try:
        current = input("\nEnter current PHY options value (press Enter to skip): ").strip()
        if current:
            print(f"Current value: {current} = {bin(int(current))}")
        
        print("\nEnter new PHY options value (0-15):")
        opts_value = int(input("> ") or "0")
        
        if opts_value < 0 or opts_value > 15:
            print("✗ Error: PHY options must be between 0-15")
            return
        
        print(f"\nYou selected: {opts_value} = {bin(opts_value)}")
        print("This enables:")
        if opts_value & PHY_OPT_WCID:
            print("  ✓ WebCCID Interface")
        if opts_value & PHY_OPT_DIMM:
            print("  ✓ Dim LED")
        if opts_value & PHY_OPT_DISABLE_POWER_RESET:
            print("  ✓ Disable 10-second reset window")
        if opts_value & PHY_OPT_LED_STEADY:
            print("  ✓ Steady LED (no blinking)")
        if opts_value == 0:
            print("  (Default configuration)")
        
        confirm = input("\nApply this configuration? (y/n): ").strip().lower()
        if confirm != 'y':
            print("✗ Cancelled")
            return
        
        print(f"\n→ Setting PHY options to {opts_value}...")
        success = device.send_config_command(CTAP_CONFIG_PHY_OPTS, opts_value)
        
        if success:
            print(f"✓ PHY options configured to {opts_value}")
        else:
            print("✗ Configuration failed")
            
    except ValueError:
        print("✗ Error: Invalid input")
    except Exception as e:
        print(f"✗ Error: {e}")


def configure_vidpid(device: PicoFIDODevice):
    """Configure USB VID/PID"""
    console.print("\n[bold cyan]USB VID/PID Configuration[/bold cyan]")
    
    print("\n⚠ WARNING: Changing VID/PID can cause serious issues!")
    print("Only change this if you know what you're doing.")
    print("\nRisks:")
    print("  - Device may not be recognized by OS")
    print("  - May conflict with other USB devices")
    print("  - May require driver reinstallation")
    
    print("\nCommon VID/PID values:")
    print("  RaspberryPi default: VID=0x2E8A, PID=0x10FE")
    print("  Yubikey 5:          VID=0x1050, PID=0x0407")
    print("  Custom/Generic:     VID=0xFEFF, PID=0xFCFD")
    
    try:
        confirm = input("\nDo you want to continue? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("✗ Cancelled")
            return
        
        print("\nEnter VID (Vendor ID) in hexadecimal:")
        print("  Example: 2E8A or 0x2E8A")
        vid_str = input("VID (hex): ").strip().replace('0x', '').replace('0X', '')
        vid = int(vid_str, 16)
        
        print("\nEnter PID (Product ID) in hexadecimal:")
        print("  Example: 10FE or 0x10FE")
        pid_str = input("PID (hex): ").strip().replace('0x', '').replace('0X', '')
        pid = int(pid_str, 16)
        
        if vid < 0 or vid > 0xFFFF:
            print("✗ Error: VID must be a 16-bit value (0x0000-0xFFFF)")
            return
        
        if pid < 0 or pid > 0xFFFF:
            print("✗ Error: PID must be a 16-bit value (0x0000-0xFFFF)")
            return
        
        print(f"\n⚠ You are about to set:")
        print(f"  VID: 0x{vid:04X} ({vid})")
        print(f"  PID: 0x{pid:04X} ({pid})")
        
        final_confirm = input("\nAre you ABSOLUTELY sure? (type 'YES' to confirm): ").strip()
        if final_confirm != 'YES':
            print("✗ Cancelled")
            return
        
        vidpid_value = (vid << 16) | pid
        
        print(f"\n→ Setting VID/PID to 0x{vid:04X}:0x{pid:04X}...")
        success = device.send_config_command(CTAP_CONFIG_PHY_VIDPID, vidpid_value)
        
        if success:
            print(f"✓ VID/PID configured successfully")
            print(f"\n⚠ IMPORTANT: You need to:")
            print("  1. Unplug the device")
            print("  2. Replug the device")
            print("  3. Device will appear with new VID/PID")
        else:
            print("✗ Configuration failed")
            
    except ValueError:
        print("✗ Error: Invalid hexadecimal value")
    except Exception as e:
        print(f"✗ Error: {e}")


def show_device_info(device: PicoFIDODevice):
    """Display device information"""
    console.print("\n[bold cyan]Device Information[/bold cyan]")
    
    if not device.info:
        print("✗ No device information available")
        return
    
    info = device.info
    
    table = Table(show_header=False, title="")
    table.add_column("Property", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")
    
    table.add_row("Device Name", device.get_device_name())
    
    vid, pid = device.get_vid_pid()
    aaguid_formatted = "N/A"

    if vid != 0 or pid != 0:
        table.add_row("VID:PID", f"0x{vid:04X}:0x{pid:04X} ({vid}:{pid})")

    if hasattr(info, 'aaguid'):
        aaguid_hex = info.aaguid.hex()
        aaguid_formatted = f"{aaguid_hex[0:8]}-{aaguid_hex[8:12]}-{aaguid_hex[12:16]}-{aaguid_hex[16:20]}-{aaguid_hex[20:32]}"
    
    table.add_row("CTAP Versions", ", ".join(info.versions))
    table.add_row("AAGUID", aaguid_formatted)
    table.add_row("Max Message Size", f"{info.max_msg_size} bytes")
    table.add_row("Max Creds in List", str(info.max_creds_in_list))
    table.add_row("Max Cred ID Length", str(info.max_cred_id_length))
    
    console.print(table)
    
    opt_table = Table(title="")
    opt_table.add_column("Option", style="cyan")
    opt_table.add_column("Supported", style="green")
    
    for opt, value in sorted(info.options.items()):
        opt_table.add_row(opt, "✓ Yes" if value else "✗ No")
    
    console.print(opt_table)
    

def setup_pin(device: PicoFIDODevice):
    """Setup or change device PIN"""
    console.print("\n[bold cyan]PIN Setup/Change[/bold cyan]")
    
    has_pin = device.info.options.get("clientPin", False)
    
    if has_pin:
        console.print("[dim]Your device already has a PIN configured.[/dim]\n")
        print("You can:")
        print("  • Change your existing PIN")
        print("  • Press Ctrl+C to cancel")
    else:
        console.print("[bold yellow]⚠ Your device does not have a PIN set.[/bold yellow]")
        console.print("[dim]A PIN is required for configuration commands.[/dim]\n")
        print("PIN Requirements:")
        print("  • Minimum 4 characters")
        print("  • Maximum 63 characters")
        print("  • Can contain any printable characters")
        print("  • Recommended: Use a memorable but secure PIN")
    
    print()
    
    try:
        success = device.set_pin()
        if success:
            print("\n✓ You can now use configuration commands!")
        return success
    except KeyboardInterrupt:
        print("\n\n✗ Cancelled")
        return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False


def factory_reset(device: PicoFIDODevice):
    """Factory reset the device"""
    console.print("\n[bold red][RESET] FACTORY RESET - WARNING[/bold red]")
    console.print("[bold yellow]This will PERMANENTLY DELETE ALL DATA on your device![/bold yellow]\n")
    
    print("What will be erased:")
    print("  ✗ All registered credentials (passkeys, security keys)")
    print("  ✗ Device PIN")
    print("  ✗ All configuration settings")
    print("  ✗ Everything - no recovery possible!")
    
    print("\nRequirements:")
    print("  • Firmware must be compiled with ENABLE_POWER_ON_RESET")
    print("  • Must be within 10 seconds of device power-on")
    print("  • Physical button press required")
    
    print("\n" + "="*60)
    console.print("[bold red]ARE YOU ABSOLUTELY SURE?[/bold red]")
    print("="*60)
    
    try:
        confirm1 = input("\nType 'RESET' (all caps) to continue: ").strip()
        if confirm1 != "RESET":
            print("✗ Cancelled - text didn't match")
            return False
        
        confirm2 = input("\nAre you REALLY sure? Type 'YES' to proceed: ").strip()
        if confirm2 != "YES":
            print("✗ Cancelled")
            return False
        
        print("\n" + "="*60)
        print("[RESET] RESETTING DEVICE...")
        print("="*60)
        
        success = device.reset_device()
        
        if success:
            print("\n" + "="*60)
            console.print("[bold green]✓ DEVICE RESET SUCCESSFULLY![/bold green]")
            print("="*60)
            print("\nYour device is now in factory default state:")
            print("  ✓ All data erased")
            print("  ✓ PIN removed")
            print("  ✓ Settings reset to defaults")
            print("\nYou can now:")
            print("  • Set a new PIN (Option 6)")
            print("  • Register new credentials")
            print("  • Configure settings")
            return True
        else:
            return False
            
    except KeyboardInterrupt:
        print("\n\n✗ Reset cancelled")
        return False
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return False


def main():
    """Main program loop"""
    clear_screen()
    print_header()
    
    device = PicoFIDODevice()
    
    if not device.find_device():
        print("✗ No FIDO device found!")
        print("\nMake sure your Pico FIDO is:")
        print("  • Plugged into a USB port")
        print("  • Running the Pico FIDO firmware")
        print("  • Not being used by another application")
        sys.exit(1)
    
    print(f"Device: {device.get_device_name()}")
    
    if not device.info.options.get("clientPin"):
        console.print("\n[bold yellow]⚠ Device has no PIN set![/bold yellow]")
        print("Configuration commands require a PIN to be set.")
        
        setup_now = input("\nWould you like to set up a PIN now? (y/n): ").strip().lower()
        if setup_now == 'y':
            if setup_pin(device):
                input("\nPress Enter to continue to main menu...")
            else:
                print("\n⚠ You can set up PIN later from the main menu (Option 6)")
                input("\nPress Enter to continue...")
        else:
            print("\n⚠ You can set up PIN from the main menu (Option 6)")
            input("\nPress Enter to continue to main menu...")
            print()
    
    while True:
        clear_screen()
        print_header()
        print(f"Device: {device.get_device_name()}")
        print_menu()
        
        try:
            choice = Prompt.ask("\nSelect option", choices=["0", "1", "2", "3", "4", "5", "6", "7"], default="0")
            
            if choice == "0":
                break
            elif choice == "1":
                configure_button_timeout(device)
            elif choice == "2":
                configure_led_settings(device)
            elif choice == "3":
                configure_phy_options(device)
            elif choice == "4":
                configure_vidpid(device)
            elif choice == "5":
                show_device_info(device)
            elif choice == "6":
                setup_pin(device)
            elif choice == "7":
                factory_reset(device)
            else:
                print("✗ Invalid option")
            
            input("\nPress Enter to continue...")
            clear_screen()
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n✗ Error: {e}")
            input("\nPress Enter to continue...")
            clear_screen()


if __name__ == "__main__":
    main()
