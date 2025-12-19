# Wi-Fi Survey Tool for macOS – v0.3.1

A totally vibe coded, professional-grade, Wi-Fi survey and performance tool for macOS. Logs location, Wi-Fi detials, radio stats, and network performance (Ping, iPerf3).

Saves all recorded data into JSON, CSV and XLSX for all your viewing and troubleshooting needs.

## Key Features
- **Real-time Live View**: Monitor Wi-Fi health and performance metrics instantly in your terminal.
- **Roaming Tracking**: Automatically detects and logs BSSID transitions (roaming events).
- **Dual Ping Targets**: Monitor latency to two hosts simultaneously (LAN+WAN eg.)
- **iPerf3 Integration**: Measure actual throughput via iperf as you move.
- **macOS Native**: Uses `CoreWLAN` via PyObjC, no sudo to run.

## Prerequisites

- **macOS** (Tested on 26.2)
- **Python 3.10+**
- **iperf3**

### 1. Install System Dependencies
Install `iperf3` via Homebrew:
```bash
brew install iperf3
```

## Setup

### 1. Clone & Prepare Virtual Environment
```bash
git clone https://github.com/obbish/wifi-survey.git
cd wifi-survey
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configuration
The tool creates a default config file in the script directory on its first run. To set your target `iperf_server` or to change program paths, run once then edit. Or if you prefer to create it yourself as `config.json` you can use this template:

*(Setting `"icmp_lan_server": "gateway",` will use your detected gateway as lan ping target)*

```JSON
{
    "script_version": "0.3.1",
    "log_dir": "surveys",
    "iperf_path": "/path/to/iperf3",
    "iperf_server": "YOUR_IPERF_SERVER",
    "icmp_lan_server": "gateway",
    "icmp_wan_server": "8.8.8.8",
    "log_interval_s": 2,
    "wifi_scan_interval_s": 1,
    "icmp_interval_s": 1.5,
    "icmp_packet_count": 4,
    "iperf_interval_s": 15,
    "iperf_duration_s": 2,
    "export_logs": true
}
```

### 4. Critical: Enable Location Services
For the tool to see **SSID** and **BSSID**, you must grant Location permission to Python. A helper script is provided for this:

```bash
python3 request_location.py
```
Follow the system prompt to allow python access.

## Main script usage

### Running a Survey
```bash
python3 wifi-survey.py
```

*By default, the tool logs data every 2 seconds.*

1. **Enter Location**: Type your current location (e.g., "Reception") and press Enter.
2. **Change Location**: Type a new location name whenever you move to a new spot.
3. **Stop**: Press `Ctrl+C`. The tool will save the log and automatically attempt to export it to Excel/CSV.

### Resulting Files
- **Logs**: Saved in `surveys/survey_<START>-<END>.jsonl`.
- **Exports**: If `export_logs` is enabled, `.xlsx` and `.csv` files are generated in the same directory.

## Troubleshooting

- **SSID/BSSID shows N/A**: Ensure Location Services are enabled for your Terminal/IDE and that you've run `request_location.py`.
- **iPerf3 Errors**: Ensure an `iperf3 -s` server is reachable at the IP specified in `config.json`.
- **PyObjC Errors**: Re-install dependencies using `pip install --force-reinstall -r requirements.txt`.

## License
This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
