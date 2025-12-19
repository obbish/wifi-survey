#!/usr/bin/env python3
import subprocess
import time
import json
import sys
import os
import re
import threading
import shutil
from datetime import datetime, timezone, timedelta

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILENAME = "config.json"
CONFIG_FILE = os.path.join(SCRIPT_DIR, CONFIG_FILENAME)

# Default Config (Grouped: Meta, Paths, Targets, Timers, Features)
DEFAULT_CONFIG = {
    "script_version": "0.3.1",
    
    "log_dir": "surveys",
    "iperf_path": shutil.which("iperf3") or "/usr/bin/iperf3",
    
    "iperf_server": "127.0.0.1",
    "icmp_lan_server": "gateway",
    "icmp_wan_server": "8.8.8.8",
    
    "log_interval_s": 2,
    "wifi_scan_interval_s": 1,
    "icmp_interval_s": 1.5,
    "icmp_packet_count": 4,
    "iperf_interval_s": 15,
    "iperf_duration_s": 2,
    
    "export_logs": True
}

# Load or Create Config
config = DEFAULT_CONFIG.copy()
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, 'r') as f:
            user_config = json.load(f)
            config.update(user_config)
            print(f"Loaded configuration from {CONFIG_FILE}")
    except Exception as e:
        print(f"Error loading {CONFIG_FILENAME}: {e}. Using defaults.")
else:
    # Create default config file for user to edit
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        print(f"Created default configuration: {CONFIG_FILE}")
    except Exception as e:
        print(f"Warning: Could not create {CONFIG_FILENAME}: {e}. Using defaults.")

# Apply Config
SCRIPT_VERSION = config["script_version"]
LOG_DIR = os.path.join(SCRIPT_DIR, config.get("log_dir", "logs"))
IPERF_PATH = config["iperf_path"]
IPERF_SERVER = config["iperf_server"]
ICMP_LAN_SERVER = config["icmp_lan_server"]
ICMP_WAN_SERVER = config["icmp_wan_server"]
LOG_INTERVAL_S = config["log_interval_s"]
WIFI_SCAN_INTERVAL_S = config["wifi_scan_interval_s"]
ICMP_INTERVAL_S = config["icmp_interval_s"]
ICMP_PACKET_COUNT = config["icmp_packet_count"]
IPERF_INTERVAL_S = config["iperf_interval_s"]
IPERF_DURATION_S = config["iperf_duration_s"]
EXPORT_LOGS = config.get("export_logs", False)

# --- PyObjC Loading ---
try:
    import objc
    objc.loadBundle('CoreWLAN', bundle_path='/System/Library/Frameworks/CoreWLAN.framework', module_globals=globals())
except ImportError:
    sys.exit("FATAL ERROR: PyObjC is not installed. Please run 'pip3 install pyobjc-core'")

# --- Shared State ---
data_lock = threading.Lock()
# Initialize with flattened keys ensuring order for first print
latest_data = {
    # Keys will be populated by workers
    "location": "Initializing...",
    "ssid": None, "bssid": None, "channel": None, 
    "tx_rate_mbps": None, "rssi_dbm": None, "noise_dbm": None,
    # New Fields
    "nic_ip": None, "nic_gw_ip": None, "auth_mode": None,
    "country_code": None, "nic_mac": None, "channel_width": None, "phy_mode": None,
    # Stats
    "icmp_lan_ms": None, "icmp_lan_lost": None, "icmp_lan_count": None,
    "icmp_wan_ms": None, "icmp_wan_lost": None, "icmp_wan_count": None,
    "iperf_rx_mbps": None, "iperf_tx_mbps": None, "iperf_updated_at": None
}

# --- Workers ---
def location_input_thread():
    try:
        new_location = input("Enter starting location: ")
        with data_lock: latest_data["location"] = new_location
        while True:
            new_location = input()
            with data_lock: latest_data["location"] = new_location
    except EOFError:
        return

def get_gateway_ip():
    try:
        res = subprocess.run(["route", "-n", "get", "default"], capture_output=True, text=True)
        match = re.search(r"gateway:\s+([\d\.]+)", res.stdout)
        return match.group(1) if match else None
    except: return None

def wifi_worker():
    loop_count = 0
    last_bssid = None
    
    while True:
        try:
            client = CWWiFiClient.sharedWiFiClient()  # noqa: F821
            interface = client.interface()
            
            if interface:
                # Helper to safely get attributes that might be missing on older OS
                def safe_get(obj, attr, default=None):
                    try:
                        val = getattr(obj, attr)
                        return val() if callable(val) else val
                    except: return default

                # Mappings
                phy_map = {0:"Unknown", 1:"11a", 2:"11b", 3:"11g", 4:"11n", 5:"11ac", 6:"11ax", 7:"11be"}
                
                # Security/Auth Mode Mapping
                sec_map = {
                    0: "Open",
                    1: "WEP",
                    2: "WPA-PSK",
                    3: "WPA/2-PSK",
                    4: "WPA2-PSK",
                    5: "Personal",
                    6: "Dynamic WEP",
                    7: "WPA-EAP",
                    8: "WPA/2-EAP",
                    9: "WPA2-EAP", 
                    10: "Enterprise",
                    11: "WPA3-SAE",
                    12: "WPA3-EAP",
                    13: "WPA3-Mix"
                }
                sec_raw = safe_get(interface, 'security')
                auth_mode = sec_map.get(sec_raw, str(sec_raw) if sec_raw is not None else "Unknown")

                # Channel Width & Band
                cw_channel = safe_get(interface, 'wlanChannel')
                chan_band_str = "Unknown"
                chan_width_str = "Unknown"
                if cw_channel:
                    # Band Mapping
                    b = safe_get(cw_channel, 'channelBand')
                    if b == 1: chan_band_str = "2.4GHz"
                    elif b == 2: chan_band_str = "5GHz"
                    elif b == 3: chan_band_str = "6GHz"
                    
                    # Width Mapping
                    w = safe_get(cw_channel, 'channelWidth')
                    if w == 1: chan_width_str = "20MHz"
                    elif w == 2: chan_width_str = "40MHz"
                    elif w == 3: chan_width_str = "80MHz"
                    elif w == 4: chan_width_str = "160MHz"
                    elif w == 5: chan_width_str = "320MHz"

                curr_bssid = interface.bssid()
                roam_event = (last_bssid and curr_bssid and curr_bssid != last_bssid)
                last_bssid = curr_bssid

                with data_lock:
                    latest_data["ssid"] = interface.ssid()
                    latest_data["bssid"] = curr_bssid
                    latest_data["channel"] = interface.channel()
                    latest_data["rssi_dbm"] = interface.rssiValue()
                    latest_data["noise_dbm"] = interface.noiseMeasurement()
                    latest_data["tx_rate_mbps"] = interface.transmitRate()
                    latest_data["phy_mode"] = phy_map.get(safe_get(interface, 'activePHYMode'), "Other")
                    
                    # New Metadata
                    latest_data["auth_mode"] = auth_mode
                    latest_data["nic_mac"] = safe_get(interface, 'hardwareAddress')
                    latest_data["country_code"] = safe_get(interface, 'countryCode')
                    latest_data["channel_band"] = chan_band_str
                    latest_data["channel_width"] = chan_width_str
                    
                # Throttled IP/Gateway Fetch
                if loop_count % 5 == 0 or roam_event:
                    try:
                        # IP Fetch
                        ip_raw = subprocess.run(["ipconfig", "getifaddr", "en0"], capture_output=True, text=True).stdout.strip()
                        # Gateway Fetch
                        gw_ip = get_gateway_ip()

                        with data_lock: 
                            latest_data["nic_ip"] = ip_raw
                            latest_data["nic_gw_ip"] = gw_ip
                    except: pass
                    
                loop_count += 1
                    
        except Exception as e:
            pass # Keep silent to not span console, user sees N/A in live view

        time.sleep(WIFI_SCAN_INTERVAL_S)

def icmp_worker(target_config, prefix):
    while True:
        # Resolve "gateway" to actual IP
        if target_config == "gateway":
            with data_lock:
                target = latest_data.get("nic_gw_ip")
            if not target:
                time.sleep(ICMP_INTERVAL_S)
                continue  # Gateway not yet detected, skip this cycle
        else:
            target = target_config
        
        try:
            # Using -n to avoid DNS lookups for speed
            cmd = ["ping", "-c", str(ICMP_PACKET_COUNT), "-i", "0.1", "-t", "1", target]
            icmp_raw = subprocess.run(cmd, capture_output=True, text=True, timeout=2).stdout
            
            loss_match = re.search(r"(\d+\.?\d*)%\s+packet\s+loss", icmp_raw)
            packet_loss = float(loss_match.group(1)) if loss_match else 100.0
            
            rtt_match = re.search(r"min/avg/max/stddev\s*=\s*[\d.]+/([\d.]+)/", icmp_raw)
            avg_ms = round(float(rtt_match.group(1))) if rtt_match else None
            
            with data_lock:
                latest_data[f"icmp_{prefix}_ms"] = avg_ms
                latest_data[f"icmp_{prefix}_lost"] = round(packet_loss)
                if prefix == "lan": latest_data["icmp_lan_count"] = ICMP_PACKET_COUNT
                elif prefix == "wan": latest_data["icmp_wan_count"] = ICMP_PACKET_COUNT
                
        except:
             with data_lock:
                latest_data[f"icmp_{prefix}_ms"] = None
                latest_data[f"icmp_{prefix}_lost"] = 100.0
                if prefix == "lan": latest_data["icmp_lan_count"] = ICMP_PACKET_COUNT
                elif prefix == "wan": latest_data["icmp_wan_count"] = ICMP_PACKET_COUNT

        time.sleep(ICMP_INTERVAL_S)

def iperf_worker():
    while True:
        # Rx
        try:
            res = subprocess.run([IPERF_PATH, "-c", IPERF_SERVER, "-t", str(IPERF_DURATION_S), "-R", "--json"], 
                                capture_output=True, text=True, timeout=IPERF_DURATION_S+2)
            data = json.loads(res.stdout)
            rx_mbps = data['end']['sum_received']['bits_per_second'] / 1e6
        except: rx_mbps = None
        
        with data_lock:
            latest_data["iperf_rx_mbps"] = rx_mbps
            latest_data["iperf_updated_at"] = time.time()

        time.sleep(2)  # Give radio a moment to recover

        # Tx
        try:
            res = subprocess.run([IPERF_PATH, "-c", IPERF_SERVER, "-t", str(IPERF_DURATION_S), "--json"], 
                                capture_output=True, text=True, timeout=IPERF_DURATION_S+2)
            data = json.loads(res.stdout)
            tx_mbps = data['end']['sum_sent']['bits_per_second'] / 1e6
        except: tx_mbps = None

        with data_lock:
            latest_data["iperf_tx_mbps"] = tx_mbps
            latest_data["iperf_updated_at"] = time.time()
        
        time.sleep(IPERF_INTERVAL_S)

# --- Live View ---
def display_live_view(log_path):
    os.system('cls' if os.name == 'nt' else 'clear')
    try:
        # Read last line
        with open(log_path, 'rb') as f:
            try:  # Handle empty file
                f.seek(-4096, 2)
            except IOError: 
                f.seek(0)
            last_line = f.readlines()[-1].decode()
            record = json.loads(last_line)
    except:
        print("Waiting for data...")
        return

    print(f"--- Definitive Wi-Fi Survey v{SCRIPT_VERSION} ---\n")
    
    # Header Info
    print(f"Time: {record.get('timestamp', '?')[11:19]}  |  Location: {record.get('location', 'Unknown')}")
    print("-" * 60)
    
    # Network ID Section (The "Identifiers")
    roam = "!! ROAM !!" if record.get('bss_transition') else ""
    # Safe getters for text alignment
    ssid_str = record.get('ssid') or "N/A"
    bssid_str = record.get('bssid') or "N/A"
    auth_str = record.get('auth_mode') or "N/A"
    
    chan_str = str(record.get('channel'))
    if record.get('channel_band') and record.get('channel_width'):
        chan_str += f" ({record.get('channel_band')}, {record.get('channel_width')})"

    print(f"SSID:    {ssid_str:<20}  BSSID:   {bssid_str} {roam}")
    print(f"Channel: {chan_str:<20}  Mode:    {record.get('phy_mode')}")
    print(f"Country: {record.get('country_code', 'N/A'):<20}  Auth:    {auth_str}")
    print(f"NIC IP:  {record.get('nic_ip', 'N/A'):<20}  NIC MAC: {record.get('nic_mac', 'N/A')}")
    
    # RF Section
    print("-" * 60)
    print(f"RSSI:    {record.get('rssi_dbm', 0)} dBm {'(Good)' if record.get('rssi_dbm', -100) > -65 else '(Poor)'}")
    print(f"Noise:   {record.get('noise_dbm', 0)} dBm")
    print(f"SNR:     {int(record.get('rssi_dbm', 0)) - int(record.get('noise_dbm', 0))} dB")
    print(f"Tx Rate: {record.get('tx_rate_mbps', 0)} Mbps")
    
    # Performance Section
    print("-" * 60)
    print(f"LAN Ping: {record.get('icmp_lan_ms', 'N/A')} ms (Lost: {record.get('icmp_lan_lost')}%)")
    print(f"WAN Ping: {record.get('icmp_wan_ms', 'N/A')} ms (Lost: {record.get('icmp_wan_lost')}%)")
    
    # Iperf Staleness Check
    iperf_time = record.get('iperf_updated_at')
    stale_label = ""
    if iperf_time and (time.time() - iperf_time > 10):
        stale_label = " (cached)"
    
    rx = int(record.get('iperf_rx_mbps', 0) or 0)
    tx = int(record.get('iperf_tx_mbps', 0) or 0)
    print(f"Speed:    Rx {rx} Mbps  /  Tx {tx} Mbps{stale_label}")
    
    print("\n")
    print("Enter new location and press Enter, or Ctrl+C to save and quit > ", end="", flush=True)

# --- Main ---
if __name__ == "__main__":
    if not os.path.exists(IPERF_PATH): print(f"WARNING: iperf3 not found at {IPERF_PATH}")

    # Start Daemons
    threading.Thread(target=location_input_thread, daemon=True).start()
    threading.Thread(target=wifi_worker, daemon=True).start()
    threading.Thread(target=icmp_worker, args=(ICMP_LAN_SERVER, "lan"), daemon=True).start()
    threading.Thread(target=icmp_worker, args=(ICMP_WAN_SERVER, "wan"), daemon=True).start()
    threading.Thread(target=iperf_worker, daemon=True).start()

    previous_bssid = None
    
    # Dynamic Filename Setup
    if not os.path.exists(LOG_DIR): os.makedirs(LOG_DIR)
    
    start_epoch = int(time.time())
    current_log_file = os.path.join(LOG_DIR, f"survey_{start_epoch}_running.jsonl")
    
    print(f"Logging to {current_log_file}...")
    
    # Ordered Field Keys for consistent JSON/CSV look
    # Order: Time, Loc, NIC, Radio, Signal, Perf
    FIELD_ORDER = [
        "epoch", "timestamp", 
        "location", "country_code", "ssid", "bssid", "bss_transition",
        "nic_mac", "nic_ip", "nic_gw_ip",
        "auth_mode", "phy_mode", "channel", "channel_band", "channel_width", "tx_rate_mbps",
        "rssi_dbm", "noise_dbm", "snr",
        "iperf_rx_mbps", "iperf_tx_mbps", 
        "icmp_lan_count", "icmp_lan_ms", "icmp_lan_lost", 
        "icmp_wan_count", "icmp_wan_ms", "icmp_wan_lost"
    ]

    with open(current_log_file, "a") as f:
        while True:
            try:
                time.sleep(LOG_INTERVAL_S)
                
                # Snapshot data
                with data_lock:
                    snapshot = latest_data.copy()
                
                # Computed Fields
                ts = int(time.time())
                snapshot["epoch"] = ts
                snapshot["timestamp"] = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                
                curr_bssid = snapshot.get("bssid")
                snapshot["bss_transition"] = 1 if (previous_bssid and curr_bssid and curr_bssid != previous_bssid) else 0
                if curr_bssid: previous_bssid = curr_bssid
                
                try: snapshot["snr"] = int(snapshot["rssi_dbm"]) - int(snapshot["noise_dbm"])
                except: snapshot["snr"] = 0

                # Reconstruct Ordered Dict
                final_record = {k: snapshot.get(k) for k in FIELD_ORDER}
                
                # Write
                f.write(json.dumps(final_record) + "\n")
                f.flush()
                
                display_live_view(current_log_file)
                
            except KeyboardInterrupt:
                print("\n\n--- Survey Stopped ---")
                
                # Rename file with final epoch
                end_epoch = int(time.time())
                final_filename = os.path.join(LOG_DIR, f"survey_{start_epoch}-{end_epoch}.jsonl")
                try:
                    os.rename(current_log_file, final_filename)
                    print(f"Log saved to: {final_filename}")
                    
                    if EXPORT_LOGS:
                        print("Exporting logs...")
                        converter_script = os.path.join(SCRIPT_DIR, "convert_logs.py")
                        subprocess.run([sys.executable, converter_script, final_filename])

                except OSError as e:
                    print(f"Error handling log file: {e}")
                    print(f"Log saved to: {current_log_file}")
                
                sys.exit(0)
            except Exception as e:
                # print(f"Error: {e}") 
                pass
