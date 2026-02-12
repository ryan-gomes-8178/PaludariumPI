---
title: How to debug PaludariumPI
categories: [Website, FAQ]
tags: [debug]
---

1. Stop the PaludariumPI service: `sudo service paludariumpi stop`.
2. Enter the PaludariumPI folder: `cd /home/pi/PaludariumPI/`
3. Enable Python3 virtual environment: `source venv/bin/activate`
4. Manual start PaludariumPI: `python paludariumPI.py`

This should start the PaludariumPI in console mode. So all errors should now be
visible to the console.

When the log line
`PaludariumPI 4.X.Y is up and running at address: http://0.0.0.0:8090 in XX.XX seconds`
appears, PaludariumPI is fully started and you can enter the web gui as normal.

When you are done debugging, you can press `Ctrl+C` once to stop PaludariumPI.

![PaludariumPI running in debug mode](/assets/img/PaludariumPIInDebugMode.webp)
