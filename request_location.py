#!/usr/bin/env python3
import objc
from objc import NSObject


import sys
import time
# Load Foundation framework
try:
    objc.loadBundle('Foundation', bundle_path='/System/Library/Frameworks/Foundation.framework', module_globals=globals())
except ImportError:
    print("Failed to load Foundation framework.")
    sys.exit(1)

# Load CoreLocation framework
try:
    objc.loadBundle('CoreLocation', bundle_path='/System/Library/Frameworks/CoreLocation.framework', module_globals=globals())
except ImportError:
    print("Failed to load CoreLocation framework.")
    sys.exit(1)

# specific constants might not be available if not defined in bridgesupport, so we define them or use raw values
# kCLAuthorizationStatusNotDetermined = 0
# kCLAuthorizationStatusRestricted = 1
# kCLAuthorizationStatusDenied = 2
# kCLAuthorizationStatusAuthorizedAlways = 3
# kCLAuthorizationStatusAuthorizedWhenInUse = 4

# Keep references global to prevent GC
manager = None
delegate = None

class LocationDelegate(NSObject):
    # Old Delegate
    def locationManager_didChangeAuthorizationStatus_(self, manager, status):
        print(f"Delegate (Old): Authorization status: {status}")
        self._check_status(status)

    # New Delegate (macOS 11+)
    def locationManagerDidChangeAuthorization_(self, manager):
        # We need to get status from manager
        status = manager.authorizationStatus()
        print(f"Delegate (New): Authorization status: {status}")
        self._check_status(status)

    def _check_status(self, status):
        if status == 3 or status == 4: # AuthorizedAlways or AuthorizedWhenInUse
            print("Access GRANTED! You can now run wifi-survey.py.")
            sys.exit(0)
        elif status == 2: # Denied
            print("Access DENIED. Please enable in System Settings.")
            sys.exit(0)
        # 0 is NotDetermined

    def locationManager_didFailWithError_(self, manager, error):
        print(f"Location Manager failed: {error}")

def main():
    global manager, delegate
    print("--- macOS Location Services Request ---")
    
    delegate = LocationDelegate.alloc().init()
    manager = CLLocationManager.alloc().init()  # noqa: F821
    manager.setDelegate_(delegate)
    
    print("Requesting Authorization... (Look for a popup!)")
    manager.requestAlwaysAuthorization()
    
    print("Waiting for response (up to 60s)...")
    start_time = time.time()
    
    try:
        # Run loop driving
        run_loop = NSRunLoop.currentRunLoop()  # noqa: F821
        while time.time() - start_time < 60:
            # Run for small slices
            run_loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))  # noqa: F821
    except Exception as e:
        print(f"Loop error: {e}")

    print("Timed out.")

if __name__ == "__main__":
    main()
