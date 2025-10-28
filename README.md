## 📘 GivEVC

Simple component to connect to the Givenergy EVC which doesn't rely on an Addon

---

### 🚀 Features

- ✅ Centralized polling via ModbusCoordinator
- ✅ UI-based config flow (host + scan interval)
- ✅ JSON-driven entity definitions
- ✅ Float and signed integer decoding
- ✅ Byte order control (ABCD, DCBA, etc.)
- ✅ Select entities with lookup tables
- ✅ Modular architecture for easy extension

---

### 🛠️ Installation

1. Copy this repository into your Home Assistant `custom_components` folder:

```
custom_components/
└── modbus_block/
    ├── __init__.py
    ├── config_flow.py
    ├── coordinator.py
    ├── helpers.py
    ├── manifest.json
    ├── const.py
    ├── sensor.py
    ├── number.py
    ├── switch.py
    ├── select.py
    └── register_map.json
```

2. Restart Home Assistant.
3. Go to Settings → Devices & Services → Add Integration → Search for “Modbus Block”.
4. Enter your Modbus device’s IP address and desired scan interval.

---

### 📦 HACS Installation

To install via HACS:

1. Go to HACS → Integrations → Custom Repositories
2. Add this repo URL: `https://github.com/yourusername/modbus-block`
3. Set category to `Integration`
4. Install and restart Home Assistant

---

### 📄 Register Map Example

Define your entities in `register_map.json`:

```json
[
  {
    "name": "Temperature",
    "type": "sensor",
    "register": 10,
    "float": true,
    "scale": 0.1,
    "unit": "°C"
  },
  {
    "name": "Setpoint",
    "type": "number",
    "register": 12,
    "float": true,
    "scale": 1.0,
    "unit": "°C",
    "min": 0,
    "max": 100,
    "step": 0.5
  },
  {
    "name": "Pump",
    "type": "switch",
    "register": 14
  },
  {
    "name": "Fan Mode",
    "type": "select",
    "register": 15,
    "lookup": {
      "0": "Off",
      "1": "Low",
      "2": "Medium",
      "3": "High"
    }
  }
]
```

---

### 🧠 Entity Types Supported

| Type    | Description                          |
|---------|--------------------------------------|
| sensor  | Read-only value from a register      |
| number  | Writable numeric value               |
| switch  | On/off control via register          |
| select  | Mapped value using lookup dictionary |

---

### 🧪 Advanced Features

- Byte order control: `ABCD`, `DCBA`, `BADC`, `CDAB`
- Float decoding: IEEE 754 32-bit
- Signed integer support: 16-bit and 32-bit
- External lookup files for select entities

---

### 🧑‍💻 Code Owners

Maintained by [@yourusername](https://github.com/yourusername)

---

Let me know if you’d like a badge section, screenshots, or a changelog template added.
