# Pico FIDO Commissioner CLI

A command-line tool for configuring Pico FIDO security keys using CTAP2 protocol.

---

## Part 1: Build Firmware

Before using the commissioner tool, you need to build and flash the firmware to your Pico board. Skip this step if the firmware is already flashed.

### 1.1 Install Pico SDK

#### On Linux/macOS:

```bash
# Install dependencies
sudo apt update
sudo apt install cmake gcc-arm-none-eabi build-essential

# Clone Pico SDK
cd /opt
sudo git clone https://github.com/raspberrypi/pico-sdk.git
cd pico-sdk
sudo git submodule update --init

# Set environment variable
export PICO_SDK_PATH=/opt/pico-sdk
```

#### On macOS (Homebrew):

```bash
brew install cmake
brew tap ArmMbed/homebrew-formulae
brew install arm-none-eabi-gcc

# Clone Pico SDK
cd /opt
sudo git clone https://github.com/raspberrypi/pico-sdk.git
cd pico-sdk
sudo git submodule update --init

export PICO_SDK_PATH=/opt/pico-sdk
```

### 1.2 Install ARM/RISC-V Toolchain

**For ARM-based boards (RP2040, RP2350-ARM):**

```bash
# Download ARM toolchain
wget https://developer.arm.com/-/media/Files/downloads/gnu-rm/10.3-2021.10/gcc-arm-none-eabi-10.3-2021.10-x86_64-linux.tar.bz2

# Extract to /opt
sudo tar xjf gcc-arm-none-eabi-10.3-2021.10-x86_64-linux.tar.bz2 -C /opt/

# Set path
export PATH="/opt/gcc-arm-none-eabi-10.3-2021.10/bin:$PATH"
```

**For RISC-V boards (RP2350-RISC-V):**

```bash
# Install RISC-V toolchain
sudo apt install gcc-riscv64-unknown-elf

# Or download from:
# https://github.com/riscv-collab/riscv-gnu-toolchain
```

### 1.3 Configure Build Options

Edit `build_pico_fido.sh` to configure your build:

```bash
# Line 21: Set your board
boards=("waveshare_rp2350_one")  # or pico, pico2, etc.

# Line 17: Set platform
PICO_PLATFORM="rp2350"  # or rp2040 for older boards

# Lines 27-32: Enable/disable features
-DENABLE_EDDSA=1                # EdDSA support (recommended)
-DENABLE_POWER_ON_RESET=1       # Factory reset feature (required for reset)
-DENABLE_OATH_APP=1             # TOTP/HOTP support
-DENABLE_OTP_APP=1              # OTP support
-DVIDPID=Yubikey5               # USB VID/PID preset
```

**Available boards:** Check `all_boards.txt` in project root

**Build options explained:**
- `ENABLE_EDDSA`: EdDSA cryptographic algorithm support
- `ENABLE_POWER_ON_RESET`: Allows factory reset within 10 seconds of power-on
- `ENABLE_OATH_APP`: TOTP/HOTP authenticator app support
- `ENABLE_OTP_APP`: One-time password support
- `VIDPID`: USB identifier preset (Yubikey5, Generic, Custom)

### 1.4 Build Firmware

```bash
cd /path/to/pico-fido

# Make script executable
chmod +x build_pico_fido.sh

# Build
./build_pico_fido.sh
```

Output: `release/pico_fido_[board]-[version].uf2`

### 1.5 Flash Firmware 

1. Hold **BOOTSEL** button on your Pico board
2. Plug in USB cable (while holding BOOTSEL)
3. Release BOOTSEL - device appears as USB drive
4. Copy firmware:

```bash
# Linux
cp release/pico_fido_*.uf2 /media/$USER/RP2350/

# macOS
cp release/pico_fido_*.uf2 /Volumes/RP2350/

# Windows
copy release\pico_fido_*.uf2 D:\
```

Device will automatically reboot with new firmware.

---

## Part 2: Setup Commissioner CLI Tool

#### 2.1 Install Dependencies

```bash
cd tools/commissioner-cli

# Install Python packages
pip3 install -r requirements.txt
```

#### 2.2 Verify Installation

```bash
# Make executable
chmod +x main.py

# Test
python3 main.py
```

You should see the commissioner interface.

#### 2.3 Linux USB Permissions (Optional)

If you get permission errors:

```bash
# Create udev rule
sudo tee /etc/udev/rules.d/70-pico-fido.rules << EOF
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="2e8a", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="2e8a", MODE="0666"
EOF

# Reload rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Or run with sudo
sudo python3 main.py
```

---

## Features

The Commissioner CLI supports the following configuration options:

- Device Security
    - **PIN Management**: Set/change device PIN (required for all operations)
    - **Factory Reset**: Erase all data and reset to defaults
- Button Configuration
    - **Button Press Timeout**: Configure physical button confirmation (0-255 seconds)
    - Enable/disable user presence verification
- LED Configuration
    - **GPIO Pin**: Set which pin controls the LED (0-29)
    - **Brightness**: Adjust LED brightness (0-255)
- PHY Options (Bit Flags)
    - **WebCCID Interface**: Enable/disable WebCCID
    - **LED Dimming**: Dim the LED for discreet use
    - **Power-On Reset Window**: Disable 10-second reset restriction
    - **Steady LED**: Stop LED blinking, keep it steady
- USB Configuration
    - **VID/PID**: Change USB Vendor/Product IDs (advanced)
- Device Information
    - View CTAP versions, AAGUID, capabilities
    - Display current VID/PID
    - Show supported features

---

## Usage

```bash
# Run the tool
python3 main.py

# Or make it executable and run
./main.py
```

The tool provides an interactive menu. Navigate using number keys and follow prompts.

#### First-Time Setup

1. **Set a PIN** (required for configuration):
   - Tool will prompt on first run
   - Or select Option 6 from menu
   - Minimum 4 characters

2. **Configure your device**:
   - Select options from the menu
   - Changes are persistent across reboots

---

## Requirements

- Python 3.14+
- Firmware compiled & flashed with configuration support
- USB HID access

---

## Troubleshooting

#### "No FIDO device found"
- Check USB connection
- Verify device is not being used by another application

#### "Configuration failed: PUAT_REQUIRED"
- Device PIN not set
- Set PIN using Option 6

#### "Configuration failed: NOT_ALLOWED" (Reset)
- More than 10 seconds since power-on
- Unplug device, replug, and try again within 10 seconds
- Or disable power-on reset restriction via PHY Options

#### "Firmware doesn't have PHY_UP_BTN handler"
- Rebuild firmware with latest code
- Ensure `src/fido/cbor_config.c` includes button timeout handler

---

## Protocol Details

This tool uses:
- **CTAP2** `authenticatorConfig` command (0x0D)
- **Vendor commands** for Pico FIDO-specific settings
- **PIN/UV Auth Token** for secure authentication
- **CBOR encoding** for data serialization

All operations are validated by firmware and reversible.

---

## Security Notes

- PIN is required for all configuration changes, set this before using any webauthn
- Factory reset requires physical button confirmation (if enabled)
- Power-on reset window prevents accidental data loss but is recommended to disable in production
- VID/PID changes may affect device recognition i.e new identity

---

## License

This tool is not officially part of the Pico FIDO project & is built as a hobby.
