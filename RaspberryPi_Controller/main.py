from nicegui import ui, app
import serial
import serial.tools.list_ports
import threading
import socket
import time
import struct
import math
import json
import os
import random

# --- Configuration ---
ARTNET_PORT = 6454
BAUD_RATE = 115200
CONFIG_FILE = 'config.json'

# --- State & Persistence ---
class State:
    def __init__(self):
        self.mode = "MANUAL"
        self.dmx_data = [0] * 8
        self.feedback = [0] * 8
        self.targets = [0] * 8 # Global Target State
        self.connected_port = None
        
        # Smooth Transition State
        self.demo_transition_start = 0
        self.transition_positions = [0] * 8
        
        # Load Config
        config = self.load_config()
        self.limits = config.get('limits', [{"min": 10, "max": 1013} for _ in range(8)])
        self.demo_speed = config.get('demo', {}).get('speed', 1.0)
        self.demo_pattern = config.get('demo', {}).get('pattern', 'WAVE')
        
        # Random offsets for "Random" mode
        self.random_offsets = [random.random() * 6.28 for _ in range(8)]

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}

    def save_config(self):
        data = {
            "limits": self.limits,
            "demo": {
                "speed": self.demo_speed,
                "pattern": self.demo_pattern
            }
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f)
        ui.notify("Configuration Saved", type='positive')

state = State()

# --- Serial Manager ---
class SerialManager:
    def __init__(self):
        self.ser = None

    def connect(self, port):
        try:
            if self.ser: self.ser.close()
            self.ser = serial.Serial(port, BAUD_RATE, timeout=0.1)
            state.connected_port = port
            ui.notify(f"Connected to {port}", type='positive')
            # Send Config on Connect
            self.sync_config()
            return True
        except Exception as e:
            ui.notify(f"Connection Failed: {e}", type='negative')
            state.connected_port = None
            return False

    def sync_config(self):
        if not self.ser: return
        for i, lim in enumerate(state.limits):
            cmd = f"<CFG,{i},{lim['min']},{lim['max']}>"
            try:
                self.ser.write(cmd.encode('utf-8'))
                time.sleep(0.05) # Small delay to not flood buffer
            except:
                pass

    def send_target(self, motor_idx, target):
        if self.ser and self.ser.is_open:
            cmd = f"<SET,{motor_idx},{target}>"
            try:
                self.ser.write(cmd.encode('utf-8'))
            except:
                state.connected_port = None

    def read_feedback(self):
        if self.ser and self.ser.is_open and self.ser.in_waiting:
            try:
                lines = self.ser.read_all().decode('utf-8').split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith("<STA") and line.endswith(">"):
                        parts = line[5:-1].split(",")
                        if len(parts) == 8:
                            state.feedback = [int(p) for p in parts]
            except:
                pass

serial_mgr = SerialManager()

# --- ArtNet Listener ---
class ArtNetListener(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.running = True
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.5)
        try:
            self.sock.bind(("", ARTNET_PORT))
        except:
            print("Failed to bind ArtNet port")

    def run(self):
        while self.running:
            try:
                data, _ = self.sock.recvfrom(1024)
                if len(data) >= 18 and data[0:8] == b'Art-Net\x00':
                     if data[8] == 0x00 and data[9] == 0x50:
                        state.dmx_data = list(data[18:26])
            except socket.timeout:
                pass
            except Exception:
                pass

artnet = ArtNetListener()
artnet.daemon = True
artnet.start()

# --- Background Control Loop (Global) ---
def control_loop():
    while True:
        try:
            serial_mgr.read_feedback()
            
            # Logic to Determine Targets
            if state.mode == "ARTNET":
                for i in range(8):
                    state.targets[i] = state.dmx_data[i] * 4 
                    
            elif state.mode == "DEMO":
                t = time.time()
                base_speed = 0.3 * state.demo_speed 
                
                # Check for Transition
                time_in_demo = t - state.demo_transition_start
                transition_duration = 2.0 # Seconds to fade in
                
                for i in range(8):
                    wave = 0
                    if state.demo_pattern == "WAVE":
                        wave = (math.sin(t * base_speed + (i * 0.5)) + 1) / 2
                    elif state.demo_pattern == "RIPPLE":
                        dist_from_center = abs(3.5 - i)
                        wave = (math.sin(t * base_speed - dist_from_center * 0.8) + 1) / 2
                    elif state.demo_pattern == "BREATH":
                        wave = (math.sin(t * base_speed) + 1) / 2
                    elif state.demo_pattern == "RANDOM":
                        speed_var = 1.0 + (i % 3) * 0.2 
                        wave = (math.sin(t * base_speed * speed_var + state.random_offsets[i]) + 1) / 2
                    
                    target_val = int(wave * 1023)

                    # Apply Soft Transition Interpolation
                    if time_in_demo < transition_duration:
                        progress = time_in_demo / transition_duration
                        p_curve = progress # Simple linear blend
                        
                        start_pos = state.transition_positions[i]
                        target_val = int(start_pos * (1 - p_curve) + target_val * p_curve)

                    state.targets[i] = target_val

            # Send Targets to Arduino (if not Manual, or if Manual handled elsewhere)
            # Actually, let's have the Loop ALWAYS send the 'state.targets'.
            # In Manual mode, the UI updates 'state.targets'.
            
            # Optimization: Only send if changed? Or send periodically?
            # Arduino expects periodic updates or only on change?
            # To be safe, let's send continuously for now 
            # OR only if mode is NOT Manual (since Manual sends dedicated events)
            
            if state.mode != "MANUAL":
                for i in range(8):
                    serial_mgr.send_target(i, state.targets[i])

            time.sleep(0.05)
            
        except Exception as e:
            print(f"Control Loop Error: {e}")
            time.sleep(1)

# Start Control Thread
threading.Thread(target=control_loop, daemon=True).start()

# --- UI Theme ---
def apply_theme():
    ui.colors(primary='#3B82F6', secondary='#10B981', accent='#8B5CF6', dark='#0F172A')
    ui.query('body').classes('bg-slate-900 text-white')

# --- UI Pages ---
@ui.page('/')
def index():
    apply_theme()
    
    # --- HEADER ---
    with ui.header().classes('bg-slate-800 row items-center p-4 shadow-lg'):
        ui.icon('bolt', color='amber').classes('text-3xl')
        ui.label('KINSCULPT').classes('text-2xl font-bold tracking-widest ml-2')
        ui.label('8-AXIS CONTROLLER').classes('text-xs text-slate-400 mt-2 ml-1')
        
        with ui.row().classes('ml-auto gap-4 items-center'):
            status_label = ui.label('DISCONNECTED').classes('text-red-500 font-bold text-sm bg-slate-900 px-3 py-1 rounded')
            
            async def scan_ports():
                ports = serial.tools.list_ports.comports()
                valid_ports = [p.device for p in ports if "USB" in p.description or "Arduino" in p.description or "usbmodem" in p.device]
                if valid_ports:
                    if serial_mgr.connect(valid_ports[0]):
                        status_label.text = f"LINKED: {valid_ports[0]}"
                        status_label.classes(remove='text-red-500', add='text-emerald-400')
                else:
                    ui.notify("No USB Device Found", type='warning')

            ui.button('CONNECT', on_click=scan_ports).props('outline color=white icon=usb size=sm')

    # --- TABS ---
    with ui.tabs().classes('w-full bg-slate-800 text-white') as tabs:
        tab_control = ui.tab('CONTROL')
        tab_config = ui.tab('CONFIGURATION')

    with ui.tab_panels(tabs, value=tab_control).classes('w-full bg-slate-900 text-white p-4'):
        
        # --- CONTROL DASHBOARD ---
        with ui.tab_panel(tab_control):
            
            # Mode Switcher
            with ui.row().classes('w-full justify-center mb-8 gap-4 bg-slate-800 p-2 rounded-lg inline-flex'):
                
                # Define Buttons (refs needed for updating style)
                btn_manual = ui.button('MANUAL').props('unelevated color=slate-6')
                btn_artnet = ui.button('ARTNET').props('unelevated color=slate-6')
                btn_demo = ui.button('DEMO').props('unelevated color=slate-6')

                def update_mode_ui():
                    # Reset all
                    btn_manual.props('color=slate-7 text-color=slate-400')
                    btn_artnet.props('color=slate-7 text-color=slate-400')
                    btn_demo.props('color=slate-7 text-color=slate-400')
                    
                    # Highlight Active
                    if state.mode == "MANUAL":
                        btn_manual.props('color=blue-6 text-color=white')
                    elif state.mode == "ARTNET":
                        btn_artnet.props('color=purple-6 text-color=white')
                    elif state.mode == "DEMO":
                        btn_demo.props('color=amber-7 text-color=white')

                def set_mode(m): 
                    # If switching TO Demo from something else, trigger transition
                    if m == "DEMO" and state.mode != "DEMO":
                        state.demo_transition_start = time.time()
                        # Snapshot current position to fade from
                        state.transition_positions = list(state.feedback)
                        
                    state.mode = m
                    update_mode_ui()

                # Bind Clicks
                btn_manual.on_click(lambda: set_mode('MANUAL'))
                btn_artnet.on_click(lambda: set_mode('ARTNET'))
                btn_demo.on_click(lambda: set_mode('DEMO'))

                # Init UI
                update_mode_ui()

            # Sliders Grid
            with ui.grid(columns=8).classes('w-full gap-4'):
                
                # Local references for this client
                local_sliders = []
                local_feedback_bars = []
                
                for i in range(8):
                    with ui.column().classes('items-center bg-slate-800 p-4 rounded-xl shadow-lg border border-slate-700'):
                        ui.label(f"M{i+1}").classes('font-bold text-slate-300 mb-1')
                        
                        # Grid for Side-by-Side Feedback & Control
                        with ui.row().classes('h-64 justify-center items-end gap-4'):
                            
                            # Feedback Slider (Green, Read-only)
                            # Shows actual position from Arduino
                            with ui.column().classes('h-full items-center justify-end'):
                                fb = ui.slider(min=0, max=1023, value=0).props('vertical readonly color=green track-color=grey-8').classes('h-full')
                                local_feedback_bars.append(fb) 
                                ui.label('ACT').classes('text-[10px] text-green-500 font-bold')

                            # Control Slider (Blue)
                            # Control target position
                            with ui.column().classes('h-full items-center justify-end'):
                                def on_slide(e, idx=i):
                                    # In Manual Mode, user controls the Target
                                    if state.mode == "MANUAL":
                                        state.targets[idx] = int(e.value)
                                        serial_mgr.send_target(idx, int(e.value))
                                
                                sl = ui.slider(min=0, max=1023, value=0, step=1, on_change=on_slide).props('vertical').classes('h-full')
                                local_sliders.append(sl)
                                ui.label('TGT').classes('text-[10px] text-blue-500 font-bold')

            # Client-Side Sync Loop
            def sync_ui():
                # Update UI elements to match Global State
                for i in range(8):
                    # Feedback
                    if i < len(local_feedback_bars):
                        local_feedback_bars[i].value = state.feedback[i]
                    
                    # Target Sliders
                    if state.mode != "MANUAL":
                        if i < len(local_sliders):
                            local_sliders[i].value = state.targets[i]

            ui.timer(0.1, sync_ui)

        # --- SETUP PAGE ---
        with ui.tab_panel(tab_config):
            
            # Action Bar
            with ui.row().classes('w-full justify-between items-center mb-6'):
                ui.label('SYSTEM SETTINGS').classes('text-xl font-bold text-slate-200')
                def save_and_sync():
                    state.save_config()
                    serial_mgr.sync_config()
                ui.button('SAVE CONFIGURATION', on_click=save_and_sync, icon='save').props('color=emerald-600')

            # Demo Settings Card
            with ui.card().classes('w-full bg-slate-800 border-l-4 border-amber-500 mb-6 p-4'):
                ui.label('DEMO SETTINGS').classes('font-bold text-lg mb-4 text-amber-500')
                
                with ui.grid(columns=2).classes('w-full gap-8'):
                     # Pattern Selector
                     with ui.column():
                        ui.label('Motion Pattern').classes('text-slate-400 text-sm')
                        ui.select(['WAVE', 'RIPPLE', 'BREATH', 'RANDOM'], value=state.demo_pattern,
                            on_change=lambda e: setattr(state, 'demo_pattern', e.value)).classes('w-full').props('outlined dark')

                     # Speed Control
                     with ui.column():
                        ui.label('Global Speed Multiplier').classes('text-slate-400 text-sm')
                        with ui.row().classes('w-full items-center gap-4'):
                            ui.slider(min=0.1, max=3.0, step=0.1, value=state.demo_speed,
                                on_change=lambda e: setattr(state, 'demo_speed', e.value)).classes('flex-grow')
                            ui.label().bind_text_from(state, 'demo_speed', lambda v: f"{v}x")

            # Motor Limits Card
            with ui.card().classes('w-full bg-slate-800 border-l-4 border-blue-500 p-4'):
                ui.label('MOTOR CALIBRATION (Soft Limits)').classes('font-bold text-lg mb-4 text-blue-500')
                
                with ui.grid(columns=2).classes('w-full gap-8'):
                    for i in range(8):
                        with ui.row().classes('w-full justify-between items-center bg-slate-900 p-2 rounded'):
                            ui.label(f"Actuator {i+1}").classes('font-bold text-slate-300')
                            with ui.row().classes('gap-2'):
                                ui.number('MIN', value=state.limits[i]['min'], 
                                    on_change=lambda e, idx=i: state.limits[idx].update({'min': int(e.value)})).props('outlined dark dense style="width: 80px"')
                                ui.number('MAX', value=state.limits[i]['max'], 
                                    on_change=lambda e, idx=i: state.limits[idx].update({'max': int(e.value)})).props('outlined dark dense style="width: 80px"')



ui.run(title='Kinsculpt', port=8080, reload=False, dark=True)
