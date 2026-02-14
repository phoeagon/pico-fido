PICO_SDK_PATH=../pico-sdk CC=/opt/arm-gnu-toolchain/bin/arm-none-eabi-gcc ASM=/opt/arm-gnu-toolchain/bin/arm-none-eabi-gcc \
CXX=/opt/arm-gnu-toolchain/bin/arm-none-eabi-g++ cmake .. -DPICO_BOARD=waveshare_rp2040_plus_16mb -DVIDPID=Yubikey5 \
-DUSB_VID=0x1050 -DUSB_PID=0x0402

make
