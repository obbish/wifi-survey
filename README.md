### For macOS
* Make sure you have the pip modules at the top of the script
* Make sure Python is allowed Location Services in System Settings
* Make sure you have an iperf3 server on your network (or use an online one)
* Modify first section of the script to your set up

When you change location type where you are and press Enter. That way you can analyze wifi coverage.

#### Demo – When running the script it looks like this:

```
--- Live Wi-Fi Survey v14.4 ---

--- GLOBAL ---------------------------------------------------
Location:                    Reception area
Survey Start Time:           15:08:27
Data Log Interval (approx):  2 s
Live View Update Interval:   2 s

--- RADIO ----------------------------------------------------
SSID:                        AllYourBase-5G
BSSID:                       b8:12:4b:4f:8f:ab
Channel:                     132
RSSI:                        -69 dBm
Noise:                       -92 dBm

--- DATA -----------------------------------------------------
Throughput (Rx/Tx):          176.0 / 106.0 Mbps
Retransmits (Rx/Tx):         8 / 0
Latency (LAN/WAN):           91.413ms (0.0%) / 92.466ms (0.0%)

--- SESSION TOTALS -------------------------------------------
Run Time:                    0:09:26
Total Data (Rx/Tx):          3304.60 / 2070.00 MB
Avg. Throughput (Rx/Tx):     189.79 / 117.81 Mbps
Avg. Ping (LAN/WAN):         15.72 / 17.29 ms
Ping Pkts Sent (LAN/WAN):    219 / 219
Ping Pkts Lost (LAN/WAN):    5 / 3
Unique APs:                  1
Hops (Roams):                0
Locations Logged:            2
--------------------------------------------------------------
(Press Ctrl+C to stop)
Enter new location and press Enter:
```
#### Demo – The resultant log file is in JSONL format and will look like this:

```
{"Epoch time": 1757339391, "Watch time": "2025-09-08T15:49:51+02:00", "script_version": "14.4", "bssid_changed": false, "location": "Reception area", "wifi_details": {"ssid": "AllYourBase-5G", "bssid": "b8:12:4b:4f:8f:ab", "rssi_dbm": -67, "noise_dbm": -92, "tx_rate_mbps": 206.0, "channel": 132, "phy_mode": "Other"}, "lan_ping": {"avg_ms": 11.006, "packet_loss_percent": 0.0, "packets_transmitted": 3, "packets_received": 3}, "wan_ping": {"avg_ms": 20.562, "packet_loss_percent": 33.3, "packets_transmitted": 3, "packets_received": 2}, "throughput": {"rx_mbps": 226.0, "retransmissions_rx": 53, "transfer_rx_mbytes": 54.0, "tx_mbps": 50.8, "retransmissions_tx": 110, "transfer_tx_mbytes": 13.5, "tx_error": "iPerf Tx timed out", "rx_error": "iPerf Rx timed out"}}
```

It's recommended to use a JSON parser such as ```jq``` to analyze your log file. 
Or use ```jq``` to convert to  human readable formats such as CSV. Then you can make pretty graphs and what not.


Free to use, share and modify as per GNU GPLv3.0. 
