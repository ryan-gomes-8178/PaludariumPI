---
title: How to start/stop/restart and disable/enable PaludariumPI
categories: [Website, FAQ]
tags: [systemd, service]
---

PaludariumPI is using systemd for startup. Here you can find the commands to
manually start, stop or restart it. Also there is an option to disable or enable
PaludariumPI at boot up.

### Start

run `sudo service paludariumpi start` to start PaludariumPI

### Stop

run `sudo service paludariumpi stop` to stop PaludariumPI

### Restart

run `sudo service paludariumpi restart` to restart PaludariumPI

### Enable startup

run `sudo systemctl enable paludariumpi` to enable PaludariumPI at startup

### Disable startup

run `sudo systemctl disable paludariumpi` to disable PaludariumPI at startup
