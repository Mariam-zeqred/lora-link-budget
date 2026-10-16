"""Streamlit page over the same functions the CLI uses:  streamlit run app.py"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from lora_link_budget import (
    REGIONS,
    Hata,
    LinkBudget,
    airtime,
    battery_life,
    duty_cycle_check,
    free_space,
    log_distance,
    sensitivity_dbm,
)
from lora_link_budget.battery import NodeProfile

st.set_page_config(page_title="LoRa link budget", layout="wide")
st.title("LoRa / LoRaWAN link budget and range estimator")

with st.sidebar:
    region = REGIONS[st.selectbox("Region", list(REGIONS))]
    st.caption(region.note)
    tx_power = st.slider("TX power (dBm)", 0.0, 30.0, 14.0, 1.0)
    tx_gain = st.number_input("Node antenna gain (dBi)", value=2.0)
    tx_cable = st.number_input("Node cable loss (dB)", value=0.5)
    rx_gain = st.number_input("Gateway antenna gain (dBi)", value=2.0)
    rx_cable = st.number_input("Gateway cable loss (dB)", value=0.5)
    fade = st.slider("Fade margin (dB)", 0.0, 30.0, 10.0, 1.0)
    extra = st.number_input("Extra loss: vegetation / walls (dB)", value=0.0)
    nf = st.number_input("Receiver noise figure (dB)", value=6.0)
    model_name = st.selectbox("Path-loss model", ["log-distance", "free space", "Okumura-Hata"])
    exponent = st.slider("Log-distance exponent n", 2.0, 5.0, 3.0, 0.1)
    gw_h = st.number_input("Gateway antenna height (m)", value=10.0)
    node_h = st.number_input("Node antenna height (m)", value=1.5)
    env = st.selectbox("Hata environment", ["open", "suburban", "urban"])
    distance = st.number_input("Distance to check (m)", value=1500.0, step=100.0)
    payload = st.number_input("Application payload (bytes)", 1, 242, 12)
    per_hour = st.number_input("Messages per hour", 0.1, 3600.0, 6.0)
    capacity = st.number_input("Battery capacity (mAh)", value=2400.0)

budget = LinkBudget(tx_power, tx_gain, tx_cable, rx_gain, rx_cable, fade, nf, extra)
f = region.frequency_mhz
model = {
    "free space": free_space(f),
    "log-distance": log_distance(f, exponent),
    "Okumura-Hata": Hata(f, gw_h, node_h, env),
}[model_name]
bw = region.bandwidth_hz
if budget.eirp_dbm > region.max_eirp_dbm:
    st.warning(f"EIRP {budget.eirp_dbm:.1f} dBm exceeds the {region.max_eirp_dbm:g} dBm limit")

rows = []
for sf in range(7, 13):
    link = budget.evaluate(model, distance, sf, bw)
    t = airtime(payload, sf, bw).total_ms
    dc = duty_cycle_check(region, t, per_hour, sf, payload)
    b = battery_life(capacity, t, per_hour, NodeProfile())
    rows.append(
        {
            "SF": sf,
            "sensitivity dBm": round(sensitivity_dbm(sf, bw, nf), 1),
            "RX dBm": round(link.rx_power_dbm, 1),
            "margin dB": round(link.margin_db, 1),
            "link OK": link.ok,
            "max range m": round(link.max_range_m),
            "airtime ms": round(t, 1),
            "duty cycle": f"{dc.utilisation:.3%}",
            "regulatory OK": dc.ok,
            "TTN fair use": dc.ttn_fair_use_ok,
            "battery years": round(b.life_years, 2),
            "problems": "; ".join(dc.problems),
        }
    )
df = pd.DataFrame(rows).set_index("SF")

st.subheader(
    f"EIRP {budget.eirp_dbm:.1f} dBm · {model.name} · path loss at {distance:g} m = "
    f"{model.loss_db(distance) + extra:.1f} dB"
)
st.dataframe(df, use_container_width=True)
for w in model.warnings(distance):
    st.info(w)

left, right = st.columns(2)
left.caption("Maximum range per spreading factor (m)")
left.bar_chart(df["max range m"])
right.caption("Battery life per spreading factor (years, default node profile)")
right.bar_chart(df["battery years"])
st.caption(
    "Sensitivity = -174 dBm/Hz + 10 log10(BW) + NF + SNR limit per SF (SX1276 datasheet "
    "SNR table). Airtime from the SX1276 datasheet formula with 13 bytes LoRaWAN overhead. "
    "Battery life uses the illustrative node profile in battery.py."
)
