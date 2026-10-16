# lora-link-budget

A LoRa / LoRaWAN planning calculator: link budget and maximum range (free space, log-distance
and Okumura-Hata path loss), receiver sensitivity per spreading factor, time on air per payload
size, EU868 duty-cycle and US915 dwell-time checks, and a battery-life estimate for a
sleep-and-transmit sensor node. One Python package drives both a CLI and a Streamlit page.
This repo shows the arithmetic behind "how far will it reach and how long will the battery
last" for a farm-scale sensor network, with every formula and assumption written down.

```
 TX power ─┐                                        ┌─ SF, BW ──> SNR limit ──> sensitivity
 + antenna ├─> EIRP ──> − path loss(d, model) ──> RX power ──> margin ─┬─> OK? (≥ fade margin)
 − cable  ─┘              free space | log-distance | Hata            └─> max range (inverse)

 payload bytes + 13 (LoRaWAN) ──> SX1276 airtime formula ──> ms ─┬─> EU868 1 % duty cycle / TTN 30 s/day
                                                                 ├─> US915 400 ms dwell, max payload per SF
                                                                 └─> charge per cycle ──> battery life
```

## Run it

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt          # pandas + streamlit for the page; the core is stdlib only
make check                               # ruff + 41 tests (airtime vs published figures, inverses, rules)
make example                             # the farm worked example below
PYTHONPATH=src python -m lora_link_budget range --tx-power 14 --model hata --gw-height 30 --environment open
PYTHONPATH=src python -m lora_link_budget budget --distance 1500 --extra-loss 6 --json
PYTHONPATH=src python -m lora_link_budget airtime --payload 51 --region US915
PYTHONPATH=src python -m lora_link_budget dutycycle --payload 20 --per-hour 12 --region US915
PYTHONPATH=src python -m lora_link_budget battery --capacity 2000 --per-hour 2 --sleep-ma 0.01
make app                                 # Streamlit page on http://localhost:8501
```

Every command takes `--sf` (one or more of 7..12), `--region EU868|US915` and `--json`;
`--help` lists the radio-path flags with their defaults.

## Worked example: a farm with LoRa sensor nodes

Nodes on beehives and in a poultry house send a 12-byte uplink (temperature, humidity, weight,
battery) every 10 minutes to one gateway at the farmhouse. EU868, 14 dBm, 2 dBi antennas with
0.5 dB of cable at each end, 10 dB fade margin, gateway antenna 10 m up, nodes at 1.5 m. The
tables below are the output of `make example` (nothing is measured; they are what the models say
for these inputs).

**Maximum range, log-distance model with n = 3** (flat farmland with crops and some trees):

| SF | sensitivity dBm | max path loss dB | range m |
|---|---|---|---|
| 7 | -124.5 | 131.5 | 2208 |
| 8 | -127.0 | 134.0 | 2675 |
| 9 | -129.5 | 136.5 | 3241 |
| 10 | -132.0 | 139.0 | 3927 |
| 11 | -134.5 | 141.5 | 4757 |
| 12 | -137.0 | 144.0 | 5763 |

The same budget through Okumura-Hata "open" gives 5.1 km at SF7 to 10.9 km at SF12, with a
warning: Hata was fitted for base antennas 30-200 m high, and a 10 m mast is an extrapolation.
Two models that disagree by a factor of two is the honest state of RF planning without a site
survey; the number to design against is the smaller one, and `--extra-loss` exists for the
vegetation or walls that neither model knows about.

**At 1.5 km** (the far end of the farm) every SF closes with margin: path loss 126.5 dB,
received -109.5 dBm, margin from 15 dB at SF7 to 27.5 dB at SF12, all above the 10 dB
fade margin. So SF7 is enough for range, and the next two tables say why you would want it.

**Duty cycle, 12 bytes every 10 minutes, EU868:**

| SF | airtime ms | duty | max msg/h at 1 % | airtime s/day | TTN fair use (30 s/day) |
|---|---|---|---|---|---|
| 7 | 61.7 | 0.010 % | 584 | 8.9 | yes |
| 9 | 205.8 | 0.034 % | 175 | 29.6 | yes |
| 10 | 411.6 | 0.069 % | 87 | 59.3 | no |
| 12 | 1482.8 | 0.247 % | 24 | 213.5 | no |

The legal 1 % limit is far away at this rate; The Things Network's 30 s/day fair-use policy is
the binding constraint from SF10 up. In US915 the same 12 bytes at SF10 take 411.6 ms, which
breaks the 400 ms dwell limit and the 11-byte payload cap, so the tool reports both.

**Battery, 2 x AA lithium (2400 mAh), illustrative ESP32 + SX1276 profile** (20 uA sleep,
40 mA for 0.5 s awake, 120 mA transmit, 11 mA for 0.1 s of receive windows):

| SF | airtime ms | average uA | TX share | life |
|---|---|---|---|---|
| 7 | 61.7 | 67.5 | 18 % | 2.9 years |
| 9 | 205.8 | 96.3 | 43 % | 2.1 years |
| 12 | 1482.8 | 351.7 | 84 % | 0.6 years |

At SF7 the awake time (sensor read, frame build) costs more than the radio; at SF12 the radio
dominates. The profile values are typical datasheet numbers, not measurements of a board: the
README of a real deployment should replace them with a current-probe trace.

## What is in the package

| file | what it computes | checked against |
|---|---|---|
| `airtime.py` | SX1276 time-on-air formula, LDRO rule, 13-byte LoRaWAN overhead | TTN's published 61.7 ms (SF7) and 1482.8 ms (SF12) for 10 bytes, exact |
| `pathloss.py` | free space, log-distance, Okumura-Hata (urban / suburban / open) and their inverses | FSPL 91.22 dB at 868 MHz / 1 km; Hata urban 126.4 dB at 900 MHz, 30 m, 1 km (worked by hand); inverse(loss(d)) == d |
| `linkbudget.py` | sensitivity = -174 + 10 log BW + NF + SNR limit; EIRP, RX power, margin, max range | -137 dBm at SF12 / 125 kHz, within 1-2 dB of the SX1276 datasheet table |
| `regions.py` | EU868 1 % duty cycle, TTN 30 s/day, US915 400 ms dwell, max payload per SF | counts of messages/hour, SF11 rejected in US915 |
| `battery.py` | charge per wake cycle, average current, life with usable fraction and self-discharge | closed-form cases (sleep-only, TX-only) |
| `cli.py`, `app.py` | argparse front end with `--json`; Streamlit page over the same functions | CLI end to end; page rendered headless with `streamlit.testing` |

## Limitations

- Path-loss models are statistical. None of them knows about the actual terrain, the Fresnel
  zone clearance, or the antenna's real pattern. Expect the measured range to differ from any
  model by several dB; that is what the fade margin is for, and 10 dB is a modest choice for
  a rural link. Hata is used outside its fitted range for low gateway masts and flags it.
- Sensitivity is the theoretical noise-floor figure with a configurable noise figure; real
  gateways and nodes differ by a few dB, and interference raises the floor further.
- Airtime is for uplinks with the LoRaWAN defaults (8 preamble symbols, CR 4/5, explicit
  header, CRC). FOpts bytes, confirmed-uplink downlinks and ADR behaviour are not modelled.
- The duty-cycle check applies the 1 % limit of the EU868 default sub-band to every channel;
  the 0.1 % and 10 % sub-bands are not modelled. US915 is checked for dwell time and payload,
  not for the 64-channel hopping plan.
- The battery profile is illustrative. Self-discharge and the usable fraction are single
  numbers; temperature, cell chemistry and regulator efficiency are not modelled.

## Next steps

- Terrain-aware loss (SRTM profile + knife-edge diffraction) for a chosen gateway position.
- Read a real gateway's RSSI/SNR log and fit the log-distance exponent from it.
- Downlink and confirmed-message airtime, and the ADR data-rate choice as a function of margin.
