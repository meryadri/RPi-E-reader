# Raspberry Pi setup

Common setup for **both** apps — the display, the OS and the Python environment.
Do this once, then follow the guide for whichever app you want to run:

- **[apps/ereader/SETUP.md](apps/ereader/SETUP.md)** — the e-reader (needs buttons)
- **[apps/dashboard/SETUP.md](apps/dashboard/SETUP.md)** — the dashboard (no buttons)

Everything here works on any Raspberry Pi with a 40-pin header. Commands assume
you are SSH'd in as `<user>` at `<pi-host>` — substitute your own.

---

## 1. Connect the display

Push the Waveshare 7.5" e-ink HAT (800×480, V2) onto the 40-pin header, lining up
pin 1. That is the whole job for the panel itself — no wiring.

Only if a case or heat sink blocks the header do you need jumper wires:

| HAT label | Function | BCM pin | Physical pin |
|---|---|---|---|
| VCC | Logic power | 3.3V | 1 |
| PWR | Display power | 3.3V | 17 |
| GND | Ground | GND | 6 |
| DIN | SPI data | GPIO 10 (MOSI) | 19 |
| CLK | SPI clock | GPIO 11 (SCLK) | 23 |
| CS | Chip select | GPIO 8 (CE0) | 24 |
| DC | Data/Command | GPIO 25 | 22 |
| RST | Reset | GPIO 17 | 11 |
| BUSY | Busy signal | GPIO 24 | 18 |

These are the Waveshare driver's defaults — no code changes needed.

## 2. Enable SPI

```bash
sudo raspi-config nonint do_spi 0
sudo reboot
```

**The reboot is required** — SPI is not live until you do it. Reconnect and check:

```bash
ls -l /dev/spi*          # expect /dev/spidev0.0 and /dev/spidev0.1
```

If those are missing, the display test below fails with
`FileNotFoundError` on `SPI.open(0, 0)`.

## 3. Set the time zone

A fresh Raspberry Pi OS runs on **UTC**. Left alone, the calendar and habit day
roll over at the wrong hour — and it looks perfect in the laptop simulator, so
you would never catch it there.

```bash
sudo timedatectl set-timezone <Region/City>     # e.g. Europe/Lisbon
timedatectl                                     # check "System clock synchronized: yes"
```

## 4. Install

```bash
git clone <your-repo-url> ~/RPi-E-reader-
cd ~/RPi-E-reader-

sudo apt update && sudo apt install -y python3-lgpio git

python3 -m venv --copies --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt
pip install spidev

# Waveshare driver — not on PyPI
git clone https://github.com/waveshare/e-Paper
pip install ./e-Paper/RaspberryPi_JetsonNano/python/
```

`--system-site-packages` lets the venv see the system `lgpio` that the e-ink
driver needs.

## 5. Test the panel

```bash
source venv/bin/activate
python -c "
from waveshare_epd import epd7in5_V2
from PIL import Image, ImageDraw
epd = epd7in5_V2.EPD(); epd.init(); epd.Clear()
img = Image.new('1', (800, 480), 255)
ImageDraw.Draw(img).text((100, 200), 'It works', fill=0)
epd.display(epd.getbuffer(img)); epd.sleep()
"
```

If "It works" appears, the hardware is done.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `FileNotFoundError: SPI.open(0, 0)` | `/dev/spidev0.0` missing — SPI not enabled, or no reboot after enabling |
| `ModuleNotFoundError: waveshare_epd` | venv not active (`source venv/bin/activate`), or you used `sudo python` instead of `sudo venv/bin/python` |
| Blank screen, no error | HAT not seated, or SPI disabled |
| Everything a day out | Time zone — step 3 |
| `ssh: Undefined error: 0` (macOS) | IPv6 tried first — use the IP, or `ssh -4` |

### Newer Pi models

The Waveshare installer may pull in `Jetson.GPIO`, which ships an `RPi.GPIO`
shim that fails on Raspberry Pi hardware. That only matters for apps that use
buttons — check which backend the driver picked:

```bash
python -c "from waveshare_epd import epdconfig; print(type(epdconfig.implementation).__name__)"
```

It should print `RaspberryPi`.

### Finding the Pi on your network

```bash
ping <pi-host>.local
arp -a | grep -iE "b8:27:eb|dc:a6:32|e4:5f:01|d8:3a:dd|2c:cf:67"   # Raspberry Pi MAC prefixes
```
