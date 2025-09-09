import subprocess
import time
import json
import sys
import os
import re
import threading
from datetime import datetime, timezone, timedelta

# --- Configuration ---
SCRIPT_VERSION = "14.4"
LOG_FILE = "/Users/user123/wifi_survey_log.jsonl"
IPERF_PATH = "/usr/bin/iperf3-darwin"
IPERF_SERVER = "YOUR IPERF3-SERVER"
LAN_PING_TARGET = "SOME LOCAL HOST"
WAN_PING_TARGET = "8.8.8.8"
# The main loop now controls the display and logging rate
LIVE_VIEW_UPDATE_INTERVAL_S = 2
# Each worker has its own data collection interval
WIFI_SCAN_INTERVAL_S = 2
PING_INTERVAL_S = 2
IPERF_INTERVAL_S = 5
IPERF_DURATION_S = 2
PING_PACKET_COUNT = 3

# --- PyObjC Loading ---
try:
    import objc
    objc.loadBundle('CoreWLAN', bundle_path='/System/Library/Frameworks/CoreWLAN.framework', module_globals=globals())
except ImportError:
    sys.exit("FATAL ERROR: PyObjC is not installed. Please run 'pip3 install pyobjc-core'")

# --- Shared State ---
data_lock = threading.Lock()
# This dictionary holds the most recent data from all worker threads
latest_data = {
    "location": "Initializing...",
    "wifi_details": {}, "lan_ping": {}, "wan_ping": {}, "throughput": {}
}

# --- Input Thread ---
def location_input_thread():
    global latest_data
    try:
        new_location = input("Enter starting location: ")
        with data_lock: latest_data["location"] = new_location
        while True:
            new_location = input()
            with data_lock: latest_data["location"] = new_location
    except EOFError:
        return

# --- Worker Threads ---
def wifi_worker():
    while True:
        try:
            interface = CWWiFiClient.sharedWiFiClient().interface()
            if interface:
                phy_map = {0:"Unknown", 1:"11a", 2:"11b", 3:"11g", 4:"11n", 5:"11ac", 6:"11ax"}
                details = {
                    "ssid": interface.ssid(), "bssid": interface.bssid(),
                    "rssi_dbm": interface.rssiValue(), "noise_dbm": interface.noiseMeasurement(),
                    "tx_rate_mbps": interface.transmitRate(), "channel": interface.channel(),
                    "phy_mode": phy_map.get(interface.phyMode(), "Other")
                }
                with data_lock: latest_data["wifi_details"] = details
        except Exception as e:
            with data_lock: latest_data["wifi_details"] = {"error": f"CoreWLAN Error: {e}"}
        time.sleep(WIFI_SCAN_INTERVAL_S)

def ping_worker(target, data_key):
    while True:
        try:
            ping_raw = subprocess.run(
                ["ping", "-c", str(PING_PACKET_COUNT), "-i", "0.2", "-t", "2", target],
                capture_output=True, text=True, timeout=3
            ).stdout
            
            loss_match = re.search(r"(\d+\.?\d*)%\s+packet\s+loss", ping_raw)
            packet_loss = float(loss_match.group(1)) if loss_match else 100.0
            
            rtt_match = re.search(r"min/avg/max/stddev\s*=\s*[\d.]+/([\d.]+)/", ping_raw)
            avg_ms = float(rtt_match.group(1)) if rtt_match else None
            
            transmitted_match = re.search(r"(\d+)\s+packets\s+transmitted", ping_raw)
            packets_transmitted = int(transmitted_match.group(1)) if transmitted_match else 0

            received_match = re.search(r"(\d+)\s+packets\s+received", ping_raw)
            packets_received = int(received_match.group(1)) if received_match else 0

            with data_lock:
                latest_data[data_key] = {
                    "avg_ms": avg_ms, 
                    "packet_loss_percent": packet_loss,
                    "packets_transmitted": packets_transmitted,
                    "packets_received": packets_received
                }
        except subprocess.TimeoutExpired:
            with data_lock:
                latest_data[data_key] = {"avg_ms": None, "packet_loss_percent": 100.0, "error": "Ping timed out", "packets_transmitted": PING_PACKET_COUNT, "packets_received": 0}
        except Exception as e:
            with data_lock:
                latest_data[data_key] = {"error": f"Ping Error: {e}"}
        time.sleep(PING_INTERVAL_S)

def iperf_worker():
    while True:
        try:
            iperf_rx_raw = subprocess.run([IPERF_PATH, "-c", IPERF_SERVER, "-t", str(IPERF_DURATION_S), "-R"], capture_output=True, text=True, timeout=IPERF_DURATION_S + 2).stdout
            rx_mbps, rx_retr, rx_mbytes, _ = parse_iperf(iperf_rx_raw)
            with data_lock:
                latest_data["throughput"]["rx_mbps"] = rx_mbps
                latest_data["throughput"]["retransmissions_rx"] = rx_retr
                latest_data["throughput"]["transfer_rx_mbytes"] = rx_mbytes
        except subprocess.TimeoutExpired:
            with data_lock: latest_data["throughput"]["rx_error"] = "iPerf Rx timed out"
        except Exception as e:
            with data_lock: latest_data["throughput"]["rx_error"] = f"iPerf Rx Error: {e}"

        try:
            iperf_tx_raw = subprocess.run([IPERF_PATH, "-c", IPERF_SERVER, "-t", str(IPERF_DURATION_S)], capture_output=True, text=True, timeout=IPERF_DURATION_S + 2).stdout
            tx_mbps, tx_retr, tx_mbytes, _ = parse_iperf(iperf_tx_raw)
            with data_lock:
                latest_data["throughput"]["tx_mbps"] = tx_mbps
                latest_data["throughput"]["retransmissions_tx"] = tx_retr
                latest_data["throughput"]["transfer_tx_mbytes"] = tx_mbytes
        except subprocess.TimeoutExpired:
            with data_lock: latest_data["throughput"]["tx_error"] = "iPerf Tx timed out"
        except Exception as e:
            with data_lock: latest_data["throughput"]["tx_error"] = f"iPerf Tx Error: {e}"
            
        time.sleep(IPERF_INTERVAL_S)

def parse_iperf(block_text):
    if not block_text: return None, None, None, "Throughput data not found"
    error_match = re.search(r"iperf3: error - (.+)", block_text)
    if error_match: return None, None, None, error_match.group(1).strip()
    
    receiver_match = re.search(r"\[\s*\d+\].*receiver", block_text)
    sender_match = re.search(r"\[\s*\d+\].*sender", block_text)
    if not receiver_match or not sender_match: return None, None, None, "Test timed out or summary not found"

    bitrate_match = re.search(r"([\d.]+)\s+(M|G)bits/sec", receiver_match.group(0))
    throughput_mbps = float(bitrate_match.group(1)) * (1000 if bitrate_match.group(2) == 'G' else 1) if bitrate_match else None
    transfer_match = re.search(r"([\d.]+)\s+MBytes", receiver_match.group(0))
    transfer_mbytes = float(transfer_match.group(1)) if transfer_match else None
    retr_match = re.search(r"\s+(\d+)\s+sender", sender_match.group(0))
    retransmissions = int(retr_match.group(1)) if retr_match else None
    
    return throughput_mbps, retransmissions, transfer_mbytes, None

# --- Live View Function ---
def display_live_view_from_log(log_file_path, live_view_interval):
    os.system('cls' if os.name == 'nt' else 'clear')
    
    try:
        with open(log_file_path, 'r') as f:
            log_entries = [json.loads(line) for line in f if line.strip()]
    except (FileNotFoundError, json.JSONDecodeError):
        log_entries = []

    if not log_entries:
        print("--- Live Wi-Fi Survey ---\n\nWaiting for first data point...")
        print("\nEnter new location and press Enter: ", end="", flush=True)
        return

    record = log_entries[-1]
    
    stats = {
        'start_time_iso': log_entries[0].get('Watch time'), 'unique_bssids': set(), 'unique_locations': set(),
        'lan_pings': [], 'wan_pings': [], 'rx_throughputs': [], 'tx_throughputs': [],
        'total_rx_mbytes': 0.0, 'total_tx_mbytes': 0.0, 'roaming_events': 0,
        'lan_packets_sent': 0, 'lan_packets_lost': 0, 'wan_packets_sent': 0, 'wan_packets_lost': 0
    }
    for entry in log_entries:
        if entry.get('bssid_changed'): stats['roaming_events'] += 1
        bssid = entry.get('wifi_details', {}).get('bssid')
        if bssid: stats['unique_bssids'].add(bssid)
        loc = entry.get('location')
        if loc and loc != "Initializing...": stats['unique_locations'].add(loc)
        
        lan_ping = entry.get('lan_ping', {})
        if lan_ping.get('avg_ms') is not None: stats['lan_pings'].append(lan_ping['avg_ms'])
        sent = lan_ping.get('packets_transmitted', 0)
        rcvd = lan_ping.get('packets_received', 0)
        stats['lan_packets_sent'] += sent
        stats['lan_packets_lost'] += (sent - rcvd)

        wan_ping = entry.get('wan_ping', {})
        if wan_ping.get('avg_ms') is not None: stats['wan_pings'].append(wan_ping['avg_ms'])
        sent = wan_ping.get('packets_transmitted', 0)
        rcvd = wan_ping.get('packets_received', 0)
        stats['wan_packets_sent'] += sent
        stats['wan_packets_lost'] += (sent - rcvd)

        tput = entry.get('throughput', {})
        if tput.get('rx_mbps') is not None: stats['rx_throughputs'].append(tput['rx_mbps'])
        if tput.get('tx_mbps') is not None: stats['tx_throughputs'].append(tput['tx_mbps'])
        if tput.get('transfer_rx_mbytes') is not None: stats['total_rx_mbytes'] += tput['transfer_rx_mbytes']
        if tput.get('transfer_tx_mbytes') is not None: stats['total_tx_mbytes'] += tput['transfer_tx_mbytes']

    print(f"--- Live Wi-Fi Survey v{record.get('script_version', 'N/A')} ---")
    
    print("\n--- GLOBAL " + "-"*51)
    start_time_obj = datetime.fromisoformat(stats.get('start_time_iso'))
    print(f"{'Location:':<28} {record.get('location', 'N/A')}")
    print(f"{'Survey Start Time:':<28} {start_time_obj.strftime('%H:%M:%S')}")
    print(f"{'Data Log Interval (approx):':<28} {live_view_interval} s")
    print(f"{'Live View Update Interval:':<28} {live_view_interval} s")
    
    print("\n--- RADIO " + "-"*52)
    wifi = record.get('wifi_details', {})
    bssid_display = f"{wifi.get('bssid', 'N/A')} (*ROAMED*)" if record.get('bssid_changed') else wifi.get('bssid', 'N/A')
    print(f"{'SSID:':<28} {wifi.get('ssid', 'N/A')}")
    print(f"{'BSSID:':<28} {bssid_display}")
    print(f"{'Channel:':<28} {str(wifi.get('channel', 'N/A'))}")
    print(f"{'RSSI:':<28} {wifi.get('rssi_dbm', 'N/A')} dBm")
    print(f"{'Noise:':<28} {wifi.get('noise_dbm', 'N/A')} dBm")
    
    print("\n--- DATA " + "-"*53)
    tput = record.get('throughput', {})
    lan_ping = record.get('lan_ping', {})
    wan_ping = record.get('wan_ping', {})
    lan_display = f"{lan_ping.get('avg_ms', 'FAIL')}ms ({lan_ping.get('packet_loss_percent', 0.0)}%)"
    wan_display = f"{wan_ping.get('avg_ms', 'FAIL')}ms ({wan_ping.get('packet_loss_percent', 0.0)}%)"
    print(f"{'Throughput (Rx/Tx):':<28} {tput.get('rx_mbps', 'FAIL')} / {tput.get('tx_mbps', 'FAIL')} Mbps")
    print(f"{'Retransmits (Rx/Tx):':<28} {tput.get('retransmissions_rx', 'N/A')} / {tput.get('retransmissions_tx', 'N/A')}")
    print(f"{'Latency (LAN/WAN):':<28} {lan_display} / {wan_display}")

    print("\n--- SESSION TOTALS " + "-"*43)
    runtime_s = int(record.get("Epoch time")) - int(log_entries[0].get("Epoch time"))
    runtime_str = str(timedelta(seconds=runtime_s))
    avg_lan_ping = sum(stats['lan_pings']) / len(stats['lan_pings']) if stats['lan_pings'] else 0
    avg_wan_ping = sum(stats['wan_pings']) / len(stats['wan_pings']) if stats['wan_pings'] else 0
    avg_rx_tput = sum(stats['rx_throughputs']) / len(stats['rx_throughputs']) if stats['rx_throughputs'] else 0
    avg_tx_tput = sum(stats['tx_throughputs']) / len(stats['tx_throughputs']) if stats['tx_throughputs'] else 0
    print(f"{'Run Time:':<28} {runtime_str}")
    print(f"{'Total Data (Rx/Tx):':<28} {stats['total_rx_mbytes']:.2f} / {stats['total_tx_mbytes']:.2f} MB")
    print(f"{'Avg. Throughput (Rx/Tx):':<28} {avg_rx_tput:.2f} / {avg_tx_tput:.2f} Mbps")
    print(f"{'Avg. Ping (LAN/WAN):':<28} {avg_lan_ping:.2f} / {avg_wan_ping:.2f} ms")
    print(f"{'Ping Pkts Sent (LAN/WAN):':<28} {stats['lan_packets_sent']} / {stats['wan_packets_sent']}")
    print(f"{'Ping Pkts Lost (LAN/WAN):':<28} {stats['lan_packets_lost']} / {stats['wan_packets_lost']}")
    print(f"{'Unique APs:':<28} {len(stats['unique_bssids'])}")
    print(f"{'Hops (Roams):':<28} {stats['roaming_events']}")
    print(f"{'Locations Logged:':<28} {len(stats['unique_locations'])}")

    print("-" * 62)
    print("(Press Ctrl+C to stop)")
    print("Enter new location and press Enter: ", end="", flush=True)

# --- Main Execution ---
if __name__ == "__main__":
    if not os.path.exists(IPERF_PATH): sys.exit(f"FATAL ERROR: iperf3 not found at: {IPERF_PATH}")

    print(f"--- Definitive Wi-Fi Survey Tool v{SCRIPT_VERSION} ---")
    
    threading.Thread(target=location_input_thread, daemon=True).start()
    threading.Thread(target=wifi_worker, daemon=True).start()
    threading.Thread(target=ping_worker, args=(LAN_PING_TARGET, "lan_ping"), daemon=True).start()
    threading.Thread(target=ping_worker, args=(WAN_PING_TARGET, "wan_ping"), daemon=True).start()
    threading.Thread(target=iperf_worker, daemon=True).start()
    
    previous_bssid = None
    first_run = True
    with open(LOG_FILE, "a") as f:
        while True:
            try:
                if first_run:
                    time.sleep(1) # Give workers a moment to populate initial data
                    first_run = False
                
                time.sleep(LIVE_VIEW_UPDATE_INTERVAL_S)

                with data_lock:
                    record_to_log = json.loads(json.dumps(latest_data))

                timestamp = int(time.time())
                current_bssid = record_to_log.get("wifi_details", {}).get('bssid')
                bssid_changed = (previous_bssid is not None and current_bssid is not None and current_bssid != previous_bssid)
                if current_bssid: previous_bssid = current_bssid

                final_record = {
                    "Epoch time": timestamp,
                    "Watch time": datetime.fromtimestamp(timestamp, tz=timezone(timedelta(hours=2))).isoformat(),
                    "script_version": SCRIPT_VERSION,
                    "bssid_changed": bssid_changed,
                    **record_to_log
                }

                f.write(json.dumps(final_record) + "\n")
                f.flush()
                
                display_live_view_from_log(LOG_FILE, LIVE_VIEW_UPDATE_INTERVAL_S)

            except KeyboardInterrupt:
                print("\n\n--- Survey stopped by user. ---")
                sys.exit(0)
            except Exception as e:
                print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
                time.sleep(5)


