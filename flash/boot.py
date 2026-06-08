# Enable a second USB serial (data) so esptool has a dedicated passthrough port,
# separate from the CircuitPython console/REPL.
import usb_cdc
usb_cdc.enable(console=True, data=True)
