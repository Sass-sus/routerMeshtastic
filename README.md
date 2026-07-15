# Meshtastic Web Gateway for Raspberry Pi

This program runs continuously on the Raspberry Pi. It connects to a Meshtastic module (via USB or accessible over Wi-Fi/TCP), listens to messages on the mesh network, and provides a lightweight web interface accessible from any device on your local network. Each device in the mesh network has its own conversation (similar to a messaging app), in addition to the general broadcast channel.

## 1. Hardware Requirements

- A Raspberry Pi (any recent model is suitable).
- A Meshtastic module (e.g., Heltec, T-Beam, RAK...) connected via USB to the Pi **or** a module accessible over the Wi-Fi network (TCP connection).

## 2. Installation

```bash
# Copy this folder to the Raspberry Pi, for example to /home/pi/
cd /home/pi/meshtastic-web

# Create a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

If your module is connected via USB, identify its port with:

```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

## 3. Manual Launch (for testing)

```bash
source venv/bin/activate
export MESHTASTIC_PORT=/dev/ttyUSB0   # adjust according to your port, or leave empty for auto-detection
python3 app.py
```

Then open, from another device connected to the same local network as the Pi: `http://<pi-ip-address>:5000`

Find the Pi's IP address with `hostname -I`.

### Connection via Wi-Fi (TCP) instead of USB

If your Meshtastic module is already connected to the network (e.g., an ESP32 with Wi-Fi enabled), use:

```bash
export MESHTASTIC_CONNECTION=tcp
export MESHTASTIC_HOST=192.168.1.50   # IP address of the module
python3 app.py
```

## 4. Permanent Launch at Startup (systemd)

To ensure the program runs continuously, including after the Raspberry Pi restarts:

```bash
# Adjust paths and user in the file if needed
sudo cp meshtastic-web.service /etc/systemd/system/

# Add your user to the dialout group (for USB serial port access)
sudo usermod -aG dialout pi

sudo systemctl daemon-reload
sudo systemctl enable meshtastic-web
sudo systemctl start meshtastic-web
```

Check status and logs:

```bash
sudo systemctl status meshtastic-web
journalctl -u meshtastic-web -f
```

## 5. Messaging Functionality

- Each detected device on the mesh network appears in the left list, displaying its Meshtastic name.
- Clicking on a device opens its message history, showing sent and received **direct** (private) messages with that device.
- The **"General Broadcast"** channel aggregates messages sent to the entire network (broadcast), as in the classic Meshtastic app.
- Messages are saved in a `messages.db` file (SQLite), so history is preserved even after the Pi restarts.
- New messages appear in real-time without refreshing the page (using Socket.IO).

## 6. Notes and Limitations

- Only one Meshtastic device connected to the Pi can be managed at a time.
- The `messages.db` file grows over time; you may manually clear or archive it if needed.
- Port 5000 is open on all interfaces (`0.0.0.0`): do not expose this service directly to the internet without adding authentication.

## 7. Incoming updates

- Adding an auto-clear to the history every weeks
- Creating users for every device and only the device can access the `messages.db`
- Adding secure authentification with the MAC adress and cutting access to the internet
- Preventing access from the public network
