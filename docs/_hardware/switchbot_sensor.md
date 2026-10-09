---
title: SwitchBot Indoor/Outdoor Thermo-Hygrometer (BLE)
categories: [Hardware, Sensor]
tags: [sensor, temperature, humidity, bluetooth]

device_types: [temperature, humidity]
device_address: 'Bluetooth MAC address, optional Bluetooth adapter number. Ex: `ce:1b:c2:86:30:6a` or `ce:1b:c2:86:30:6a,1`'
device_auto_detect: true
device_url: https://www.switch-bot.com/products/switchbot-indoor-outdoor-thermo-hygrometer
---

## Information

The SwitchBot Indoor/Outdoor Thermo-Hygrometer (model W3400010) is a battery powered
temperature and humidity sensor. It broadcasts its measurements over Bluetooth LE
advertisements, so TerrariumPI only has to listen. No pairing, SwitchBot app, cloud
account or SwitchBot Hub is needed.

One physical meter provides two sensors: temperature and humidity. Both use the same
Bluetooth scan. Multiple meters are supported, and one scan reads all of them.

Readings older than 180 seconds are never used. Change this with the environment
variable `SWITCHBOT_MAX_AGE` (seconds).

Only the Indoor/Outdoor Thermo-Hygrometer is supported. Advertisements from other
SwitchBot models are ignored.

Use `contrib/switchbot_scan.py` to find the meters and check the readings. See
[docs/SWITCHBOT_BLE_SETUP.md](https://github.com/ryan-gomes-8178/PaludariumPI/blob/main/docs/SWITCHBOT_BLE_SETUP.md)
for the full setup guide.
