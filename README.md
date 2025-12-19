# Definitive Wi-Fi Survey Tool v0.3.0

A totally vibe coded, professional-grade, active Wi-Fi survey tool for macOS. It logs Layer 2 Wi-Fi metrics alongside active L3/L4 performance tests (Ping, iPerf3) correlated with location.

## Key Features
- **Real-time Live View**: Monitor Wi-Fi health and performance metrics instantly in your terminal.
- **Roaming Tracking**: Automatically detects and logs BSSID transitions (roaming events).
- **Dual Ping Targets**: Monitor both LAN (Gateway) and WAN (e.g., 8.8.8.8) latency simultaneously.
- **iPerf3 Integration**: Measure actual throughput (Rx/Tx) as you move.
- **Auto-Export**: Automatically converts JSONL logs to Excel (.xlsx) and CSV for easy analysis.
- **macOS Native**: Uses `CoreWLAN` via PyObjC for deep system integration.

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
Copy the example configuration and edit it:
```bash
cp config.json.example config.json
```

Key configuration options in `config.json`:
- `iperf_server`: IP address of your iPerf3 server.
- `lan_icmp_target`: Set to `"gateway"` (default) to auto-detect your router, or specify a static IP.
- `iperf_path`: The tool will try to find `iperf3` automatically, but you can override it here.

### 4. Critical: Enable Location Services
For the tool to see **SSID** and **BSSID**, you must grant Location permission to Python. We provide a helper script for this:

```bash
python3 request_location.py
```
Follow the system prompt to allow access.

## Usage

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
