# Bluetooth Audio to OSC Latency Optimizations

> Current capture uses readiness notifications rather than timer polling.
> `pacat` requests a 20 ms latency and a 10 ms processing interval; the server
> may choose different values. If processing falls behind, the newest 20 ms
> of PCM is retained and older samples are discarded. Bluetooth envelope attack
> and release are 5 ms and 60 ms respectively. The historical estimates below
> were not measured and do not establish end-to-end latency.

## Summary
Implemented several key optimizations to reduce latency in the Bluetooth audio → OSC update pipeline.

## Changes Made

### 1. **Historical timer interval change**
- **Before:** 50ms polling interval
- **After:** 10ms polling interval
- **Impact:** Reduced the polling interval, but did not bound capture or
  end-to-end latency. The timer has since been replaced by a readiness notifier.

### 2. **Vectorized Peak Amplitude Calculation**
- **Before:** Python loop using `struct.unpack_from()` for each sample
- **After:** NumPy vectorized operations on entire buffer
- **Impact:** Uses vectorized operations; the performance difference has not
  been measured on the target system.
- **Methods affected:**
  - Replaced per-sample struct unpacking with `np.frombuffer()`
  - Used NumPy's optimized `np.max()` for peak detection
  - Supported formats: UInt8, Int16, Int32, Float

### 3. **Added NumPy Dependency**
- **Import:** `import numpy as np`
- **Benefit:** Vectorized operations on audio samples provide significant performance boost

### 4. **Improved Level Change Detection**
- **Before:** Exact equality check (`self.level == self._last_sent_level`)
- **After:** Threshold-based detection (default: 0.1% change)
- **Impact:** 
  - Reduces unnecessary OSC messages
  - Prevents quantization noise from triggering updates
  - Maintains responsiveness for meaningful changes
- **Threshold:** `_level_change_threshold = 0.001` (adjustable per instance)

## Measurement
Measure end-to-end latency on the target system. Bluetooth transport, audio
server buffering, UI scheduling and the renderer can all contribute delay.

## Configuration
The latency and process-time requests are passed to `pacat` in
`start_bluetooth_input_capture`. `_level_change_threshold` controls the minimum
level change needed to send another OSC update.

## Compatibility
- Requires NumPy package: `pip install numpy`
- Maintains backward compatibility with existing code
- No breaking changes to public API
