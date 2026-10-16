# Walkthrough (for Mariam)

## Why it is built this way

This is a calculator, so every number must trace to one formula and one input. `LinkBudget`
holds the radio path, a path-loss model object turns distance into dB and back, and
`airtime()` is the datasheet formula. The CLI and the Streamlit page call the same
functions, so one implementation is tested.

Each module's docstring says where its numbers come from: the SX1276 datasheet (airtime, SNR
limits), the Hata 1980 equations, the LoRaWAN Regional Parameters. The battery profile is the
one illustrative input, and it is labelled as such in the code, the CLI and the README.

## File map

- `src/lora_link_budget/airtime.py`: `airtime(payload, sf, bw)` returns symbol time, preamble,
  payload symbols, the low-data-rate flag and the total; 13 bytes of LoRaWAN overhead are added
  unless `lorawan=False`.
- `pathloss.py`: three classes with the same methods, `loss_db`, `distance_m`, `warnings`. The
  inverse is closed-form for all three, so `range` needs no solver.
- `linkbudget.py`: `sensitivity_dbm`, `LinkBudget` (EIRP, max path loss, `evaluate`) and the
  `LinkResult` record; `ok` means margin at least the fade margin.
- `regions.py`: EU868 and US915 tables; `duty_cycle_check` returns a list of problems, not a
  bare boolean, so the CLI can say why something fails.
- `battery.py`: charge per wake cycle over the period, plus sleep and self-discharge.
- `cli.py`: six sub-commands; `example` prints the README tables. `app.py`: the page.
- `tests/`: 41 tests; the airtime ones match six spreading factors to the figures The Things
  Network publishes.

## Three questions a professor may ask

**Why does SF12 reach further but you still recommend SF7 for this farm?**
Each spreading-factor step buys about 2.5 dB of sensitivity, so SF12 tolerates 12.5 dB more
path loss than SF7, which with n = 3 is 2.6 times the distance. But at 1.5 km SF7 already has
15 dB of margin, and SF12 costs 24 times the airtime: 213 s/day against the 30 s/day TTN
fair-use limit, and the battery life drops from 2.9 to 0.6 years. The right SF is the lowest
one that still has the fade margin, which is what ADR does automatically.

**How much do you trust a range of 2.2 km?**
Not to better than a factor of two. Log-distance with n = 3 and Okumura-Hata "open" disagree
by that much for the same budget, and Hata is being used below its fitted 30 m mast height.
The models give the order of magnitude and show which inputs matter: every 3 dB of extra loss
costs about 20 % of range at n = 3. A real RSSI log turns the estimate into a number.

**Where does the sensitivity formula come from and why is NF a parameter?**
Thermal noise is -174 dBm/Hz at 290 K; integrate over 125 kHz for +51 dB; add the receiver's
own noise figure; and the LoRa demodulator still decodes at a negative SNR that depends on
the spreading factor (-7.5 dB at SF7 to -20 dB at SF12, SX1276 datasheet). With NF = 6 dB
this reproduces the datasheet's typical sensitivities within 1-2 dB. NF is a parameter
because a gateway with a good LNA and a cheap node module differ by several dB, and the
formula shows exactly where that difference enters.

## One thing to extend

Add a `fit` command: give it a CSV of (distance, RSSI) from a real gateway and have it fit the
log-distance exponent and a constant offset by least squares, and print the fitted n and the
residual spread. That turns the site-assumption warning into a measurement and the residual
spread into a defensible fade margin.
