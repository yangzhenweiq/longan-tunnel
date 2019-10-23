# Longan Tunnel

This integration shows how you integrate a inlets tunnel into Home Assistant.

If you use this integration, make sure you tweak the following places:

 - `manifest.json`: update the requirements to point at your Python library
 - `switch.py`: update the code to interact with your library

### Installation
Install inlets first `curl -sLS https://get.inlets.dev | sudo sh`

Copy this folder to `<config_dir>/custom_components/longan-tunnel/`.

Add the following entry in your `configuration.yaml`:

```yaml
switch:
  - platform: longan-tunnel
    inlets_bin: /usr/local/bin/inlets
    port_local: 8123
