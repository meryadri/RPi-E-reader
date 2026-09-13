# Putting the dashboard on the Pi

Ten steps, about 30 minutes. Everything runs over SSH — you never need a monitor
on the Pi.

Throughout, the Pi is `meryadri@10.0.0.54` (hostname `pi-geon`). Pin that
address in your router's DHCP reservations so it doesn't move — the habit URL
and the systemd unit both assume it stays put.

---

## 1. Plug in the display

Push the Waveshare 7.5" HAT straight onto the 40-pin header, lining up pin 1.
That's the whole job — **no wiring and no buttons**. The dashboard declares
`uses_input=False`, so it never touches GPIO.

(Only if a case or heat sink blocks the header do you need jumper wires — the
pin table is in `HARDWARE.md`.)

## 2. SSH in and enable SPI

```bash
ssh meryadri@10.0.0.54          # or: ssh -4 meryadri@pi-geon.local

sudo raspi-config nonint do_spi 0    # enable SPI
sudo reboot                          # REQUIRED — SPI is not live until you do
```

Reconnect after the reboot and confirm the device nodes exist:

```bash
ls -l /dev/spi*      # expect /dev/spidev0.0 and /dev/spidev0.1
```

If that says "No such file", SPI did not enable and the display test in step 6
will fail with `FileNotFoundError` on `SPI.open(0, 0)`.

> `ssh` by hostname can fail on macOS with `Undefined error: 0` — that is the
> IPv6 address being tried first. Use the IP, or `ssh -4`.

## 3. Set the time zone

Do not skip this. A fresh Raspberry Pi OS runs on **UTC**, which would roll your
calendar and habit day over at 8pm Eastern.

```bash
sudo timedatectl set-timezone America/New_York
timedatectl                      # check "System clock synchronized: yes"
```

## 4. Get the code onto the Pi

```bash
git clone https://github.com/meryadri/RPi-E-reader.git ~/RPi-E-reader-
cd ~/RPi-E-reader-
```

## 5. Install dependencies

```bash
sudo apt update && sudo apt install -y python3-lgpio git

python3 -m venv --copies --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt
pip install spidev

# Waveshare driver — not on PyPI, so it has to be cloned
git clone https://github.com/waveshare/e-Paper
pip install ./e-Paper/RaspberryPi_JetsonNano/python/
```

`--system-site-packages` lets the venv see the system `lgpio` that the e-ink
driver needs. You do **not** need `RPi.GPIO` — that's only for the e-reader's
buttons.

## 6. Test the screen

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

**`FileNotFoundError` on `SPI.open(0, 0)`** means `/dev/spidev0.0` is missing —
go back to step 2 and make sure you rebooted.

**On a Pi 5**, also confirm the driver picked the right backend:

```bash
python -c "from waveshare_epd import epdconfig; print(type(epdconfig.implementation).__name__)"
```

It must print `RaspberryPi`. The Pi 5 replaced the BCM GPIO controller with the
RP1 chip, so Waveshare's platform sniffing can fall through to its Jetson
branch — which is why `pip` may have pulled in `Jetson.GPIO`.

## 7. Copy your private files from your laptop

These are gitignored, so the clone in step 4 didn't bring them. Run this **on
your laptop**, not on the Pi:

```bash
cd /path/to/RPi-E-reader-

# Google Calendar: the service account key AND the list of calendar IDs
# you registered with --add-calendar
scp integrations/google_calendar/secrets/service_account.json \
    integrations/google_calendar/secrets/calendars.json \
    meryadri@10.0.0.54:~/RPi-E-reader-/integrations/google_calendar/secrets/

# Your habit list
scp private/habits.json meryadri@10.0.0.54:~/RPi-E-reader-/private/
```

Then lock the key down, back on the Pi:

```bash
chmod 600 ~/RPi-E-reader-/integrations/google_calendar/secrets/service_account.json
```

## 8. Check the data sources

```bash
cd ~/RPi-E-reader- && source venv/bin/activate

python -m integrations.open_meteo          # weather — should print a temperature
python -m integrations.google_calendar     # calendar — should list your calendars
```

If the calendar shows `0 calendar(s) visible`, `calendars.json` didn't copy
across. Either repeat that half of step 7, or re-register on the Pi:

```bash
python -m integrations.google_calendar --add-calendar you@gmail.com
```

## 9. Run it

```bash
python main.py --app dashboard --backend rpi
```

The panel should paint within a few seconds, and the console prints your habit
URL:

```
Habits: http://10.0.0.67:3004/?t=Xk3p...
```

Open that on your phone and bookmark it. Press Ctrl-C to stop.

## 10. Start it on boot

```bash
sudo cp deploy/dashboard.service /etc/systemd/system/
sudo systemctl enable --now dashboard
```

Check it:

```bash
systemctl status dashboard
journalctl -u dashboard -f        # live logs, Ctrl-C to stop watching
```

Edit `User=` and the paths in the unit file first if your username isn't `pi`.

**Done.** The dashboard now starts on every boot and survives crashes.

---

## Day to day

| Task | Command |
|---|---|
| Restart after a code change | `sudo systemctl restart dashboard` |
| See logs | `journalctl -u dashboard -n 50` |
| Update the code | `cd ~/RPi-E-reader- && git pull && sudo systemctl restart dashboard` |
| Stop it | `sudo systemctl stop dashboard` |
| Get your habit URL again | `journalctl -u dashboard | grep Habits | tail -1` |

### Back up your habit history

It lives only on the SD card and is not in git. SD cards fail.

```bash
scp meryadri@10.0.0.54:~/RPi-E-reader-/private/habit_log.json ~/backups/
```

Or tap **Download backup** on the History page.

---

## If something's wrong

| Symptom | Fix |
|---|---|
| Blank screen, no errors | SPI not enabled — `sudo raspi-config nonint do_spi 0`, then **reboot** |
| `FileNotFoundError: SPI.open(0, 0)` | `/dev/spidev0.0` missing — same fix, and check `ls /dev/spi*` |
| `ssh: Undefined error: 0` | macOS trying IPv6 — use the IP or `ssh -4` |
| `ModuleNotFoundError: waveshare_epd` | Step 5's `pip install ./e-Paper/...` didn't run inside the venv |
| Everything a day out | Time zone — step 3 |
| "Calendar not connected" | `service_account.json` missing or unreadable — step 7 |
| Calendar connects but shows nothing | `calendars.json` didn't copy — step 7 |
| "Weather unavailable" | No network; it retries automatically and keeps the last reading |
| "No habits configured" | `private/habits.json` didn't copy — step 7 |
| Habit page won't load | Phone is on a different network (guest Wi-Fi is a common cause) |
| Panel flickers every minute | Shouldn't happen — the minute tick uses a partial refresh. Report it. |
