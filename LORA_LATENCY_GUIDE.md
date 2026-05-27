# LoRa Message Transmission Latency Measurement Guide

## Overview
Your road hazard system now **automatically measures and displays the time it takes for messages to travel from the front vehicle to the rear vehicle via LoRa**.

---

## How It Works

### 1. **Message Format (Front Vehicle)**
When a hazard is detected, the front vehicle sends:
```
POTHOLE:0.85:1234567890.123
[event]:[severity]:[send_timestamp]
```

**Components:**
- `POTHOLE` - Event type (POTHOLE, SPEED_HUMP, BRAKING, CRACK)
- `0.85` - Severity/confidence score (0.0 - 1.0)
- `1234567890.123` - **Timestamp when message was sent** (Unix time with milliseconds)

### 2. **Latency Calculation (Rear Vehicle)**
When the rear vehicle receives the message:
```
Latency (ms) = (Receive Time - Send Time) × 1000
```

For example:
- Sent at: 1234567890.123
- Received at: 1234567890.189
- **Latency: 66 milliseconds**

### 3. **Display Output**
You'll see latency in **three places**:

#### **A. Terminal Console (Rear Vehicle)**
```
📡 Front vehicle alert: POTHOLE (0.85) | Latency: 66.5ms
```

#### **B. Rear Camera Screen Overlay**
```
FRONT ALERT: POTHOLE (0.85) | Latency: 66.5ms
```

#### **C. CSV Log File** (in `/output/` folder)
The latency is tracked for analysis of system performance.

---

## Key Changes Made

### **File 1: `main.py` (Front Vehicle)**
**Function:** `send_to_esp32(event_type, severity)`

```python
# Before:
message = f"{msg_event}:{severity:.2f}\n"

# After:
send_time = time.time()  # Record current time
message = f"{msg_event}:{severity:.2f}:{send_time:.3f}\n"
```

### **File 2: `rear_main.py` (Rear Vehicle)**
**Function:** `listen_for_front_hazards()`

```python
# Extract and parse the timestamp
if len(parts) > 2:
    try:
        send_time = float(parts[2])
        latency_ms = (receive_time - send_time) * 1000
    except ValueError:
        latency_ms = 0.0

# Store latency in alert dictionary
front_hazard_alert = {
    "event": event,
    "severity": severity,
    "timestamp": receive_time,
    "latency_ms": latency_ms
}
```

**Console Output Update:**
```python
print(f"📡 Front vehicle alert: {event.upper()} ({severity:.2f}) | Latency: {latency_ms:.1f}ms")
```

**Screen Display Update:**
```python
cv2.putText(display, f"FRONT ALERT: {front_event.upper()} ({front_severity:.2f}) | Latency: {front_latency:.1f}ms", ...)
```

---

## What This Tells You

### **Typical LoRa Latency Ranges**
| Range | Interpretation |
|-------|-----------------|
| **20-50 ms** | Excellent - LoRa working well, close range |
| **50-150 ms** | Good - Normal operation, acceptable range |
| **150-300 ms** | Fair - Working but far distance or interference |
| **300-500 ms** | Poor - High interference, distance issues |
| **500+ ms** | Critical - Connection problem, retransmissions |

### **Why This Matters**
- ✅ **Confirms LoRa is working** - Consistently low latency = healthy link
- ✅ **Detects interference** - Sudden spikes = potential RF interference
- ✅ **Validates range** - Know how far apart your vehicles can be
- ✅ **System debugging** - Identifies communication bottlenecks

---

## Testing the Latency

### **Step 1: Run Front Vehicle**
```bash
python main.py
```

### **Step 2: Run Rear Vehicle** (in another terminal)
```bash
python rear_main.py 1
```
(Change `1` to your rear camera index if needed)

### **Step 3: Monitor Output**
Watch the terminal for LoRa messages:
```
📡 Front vehicle alert: POTHOLE (0.85) | Latency: 42.3ms
📡 Front vehicle alert: SPEED_HUMP (0.65) | Latency: 55.1ms
📡 Front vehicle alert: BRAKING (0.92) | Latency: 38.7ms
```

### **Step 4: Optimize**
- If latency is **consistently high**, check for RF interference
- If latency is **erratic/spiky**, move ESP32 antennas
- If **no messages received**, verify COM ports in code

---

## Analyzing Latency Data

### **In Your CSV Output File**
Example from `/output/session_20260408_114921.csv`:
```
timestamp,imu_z,motion_score,decision,motor_speed,confidence,ground_truth
14:30:25.123,1.2340,2.5000,NORMAL,100,85.0,NORMAL
14:30:26.456,2.8900,3.1200,HAZARD,50,92.0,HAZARD
```

### **Create Latency Statistics**
To analyze latency patterns over a session, you can add:

```python
# In rear_main.py, add after listening loop
latency_history = []
avg_latency = sum(latency_history) / len(latency_history) if latency_history else 0
max_latency = max(latency_history) if latency_history else 0
min_latency = min(latency_history) if latency_history else 0

print(f"\n📊 LoRa Latency Statistics:")
print(f"  Average: {avg_latency:.1f}ms")
print(f"  Min:     {min_latency:.1f}ms") 
print(f"  Max:     {max_latency:.1f}ms")
```

---

## Backward Compatibility

✅ **Your system is backward compatible**
- If the rear vehicle receives an old-format message without timestamp: `POTHOLE:0.85`
  - It will **safely ignore the missing timestamp**
  - Latency will be **0.0ms** (not an error)
  - System continues to work normally

---

## Troubleshooting

### **"Latency always shows 0.0ms"**
→ Front vehicle not sending timestamps
→ Verify `send_to_esp32()` includes `send_time` in message

### **"Latency is very high (500+ ms)"**
→ Check ESP32 COM port connections
→ Verify both ESP32 modules are powered
→ Look for RF interference (Wi-Fi, microwaves, etc.)

### **"Messages not received at all"**
→ Check `ESP32_PORT_RX` is correct in `rear_main.py`
→ Verify LoRa module wiring on both ESP32s
→ Test with `python test_camera.py` to verify COM ports

---

## Advanced: Real-Time Latency Monitoring

To create a real-time latency graph, add this to `rear_main.py`:

```python
import collections

# At top of file
latency_buffer = collections.deque(maxlen=100)  # Keep last 100 measurements

# In listen_for_front_hazards(), after calculating latency_ms:
latency_buffer.append(latency_ms)

# In display section:
avg_latency = sum(latency_buffer) / len(latency_buffer) if latency_buffer else 0
cv2.putText(display, f"Avg Latency: {avg_latency:.1f}ms", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 1)
```

---

## Summary

| Aspect | Implementation |
|--------|-----------------|
| **Measurement** | Timestamp embedded in LoRa message |
| **Calculation** | Receive time - Send time |
| **Display** | Console + Screen overlay + CSV log |
| **Units** | Milliseconds (ms) |
| **Accuracy** | ±1-2ms depending on system clock |
| **Backward Compatible** | Yes - gracefully handles missing timestamp |

---

**Your system is now ready to monitor real-time LoRa communication performance between front and rear vehicles!** 🚗📡
