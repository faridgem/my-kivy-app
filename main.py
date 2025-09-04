import requests
import json
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.uix.gridlayout import GridLayout
import threading
import hashlib
import hmac
import time
import socket

class GoldTradingApp(App):
    def __init__(self):
        super().__init__()
        # Fixed API configuration - MATCH YOUR SERVER SETTINGS
        self.api_base_url = "http://92.118.46.58:5000/api"  # Ensure this matches your Flask server
        self.api_key = "12345"  # Must match server
        self.api_secret = "mysecret123"  # Must match server
        
        # Trading variables
        self.current_price = 0.0
        self.balance = 10000.0  # Demo balance
        self.position = 0.0
        self.symbol = None  # Will be auto-detected
        self.available_symbols = []  # Store available symbols
        self.market_closed_shown = False  # Track if market closed popup was shown
        self.symbol_detected = False  # Track if symbol was successfully detected
        
    def build(self):
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Title
        title = Label(text='Gold Trading App', size_hint_y=None, height=50, 
                     font_size=24, bold=True)
        main_layout.add_widget(title)
        
        # Symbol display
        self.symbol_label = Label(text='Detecting gold symbol...', 
                                size_hint_y=None, height=30, font_size=14)
        main_layout.add_widget(self.symbol_label)
        
        # Price display
        self.price_label = Label(text=f'Gold Price: ${self.current_price:.2f}', 
                               size_hint_y=None, height=40, font_size=18)
        main_layout.add_widget(self.price_label)
        
        # Account info
        account_layout = GridLayout(cols=2, size_hint_y=None, height=80, spacing=5)
        
        self.balance_label = Label(text=f'Balance: ${self.balance:.2f}', font_size=16)
        self.position_label = Label(text=f'Position: {self.position:.3f} oz', font_size=16)
        
        account_layout.add_widget(self.balance_label)
        account_layout.add_widget(self.position_label)
        main_layout.add_widget(account_layout)
        
        # Lot size input
        lot_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=50)
        lot_layout.add_widget(Label(text='Lot Size:', size_hint_x=0.3))
        self.lot_input = TextInput(text='0.01', multiline=False, size_hint_x=0.7)
        lot_layout.add_widget(self.lot_input)
        main_layout.add_widget(lot_layout)
        
        # Trading buttons
        button_layout = GridLayout(cols=2, size_hint_y=None, height=100, spacing=10)
        
        self.buy_button = Button(text='BUY', background_color=(0, 0.8, 0, 1), 
                               font_size=20, bold=True, disabled=True)
        self.buy_button.bind(on_press=self.on_buy_pressed)
        
        self.sell_button = Button(text='SELL', background_color=(0.8, 0, 0, 1), 
                                font_size=20, bold=True, disabled=True)
        self.sell_button.bind(on_press=self.on_sell_pressed)
        
        button_layout.add_widget(self.buy_button)
        button_layout.add_widget(self.sell_button)
        main_layout.add_widget(button_layout)
        
        # Refresh button
        refresh_button = Button(text='Refresh Connection', size_hint_y=None, height=50,
                              background_color=(0, 0.5, 1, 1))
        refresh_button.bind(on_press=self.refresh_connection)
        main_layout.add_widget(refresh_button)
        
        # Status label
        self.status_label = Label(text='Connecting to server...', size_hint_y=None, height=40)
        main_layout.add_widget(self.status_label)
        
        # Check server connection and symbols on startup
        Clock.schedule_once(self.check_initial_connection, 1)
        
        # Start price updates (will only work after symbol is detected)
        Clock.schedule_interval(self.update_price, 3)  # Update every 3 seconds
        
        return main_layout
    
    def check_initial_connection(self, dt):
        """Check initial server connection and detect gold symbol"""
        def check_connection():
            if self.check_server_connection():
                def update_status_connected(dt):
                    self.update_status("Server connected - Detecting gold symbol...")
                    # Run debug_connection for additional diagnostics
                    self.debug_connection()
                Clock.schedule_once(update_status_connected, 0)
                self.detect_gold_symbol()
            else:
                def update_status_offline(dt):
                    self.update_status("Server offline - Please start Flask API")
                    self.show_popup("Connection Error", 
                                  "Cannot connect to Flask server. Please ensure it is running at 92.118.46.58:5000.")
                Clock.schedule_once(update_status_offline, 0)
        
        threading.Thread(target=check_connection, daemon=True).start()
    
    def detect_gold_symbol(self):
        """Detect the correct gold symbol from the server"""
        def detect_symbol():
            try:
                # First, check server status
                response = requests.get(f"{self.api_base_url}/status", timeout=10)
                print(f"Status response: {response.status_code} - {response.text}")
                if response.status_code == 200:
                    data = response.json()
                    detected_symbol = data.get('detected_gold_symbol')
                    
                    if detected_symbol:
                        self.symbol = detected_symbol
                        self.symbol_detected = True
                        def on_symbol_detected_callback(dt):
                            self.on_symbol_detected(detected_symbol)
                        Clock.schedule_once(on_symbol_detected_callback, 0)
                        return
                
                # If no symbol detected, try to trigger detection with authentication
                headers = {
                    'Content-Type': 'application/json',
                    'X-API-Key': self.api_key,
                    'X-Signature': self.generate_signature({'timestamp': int(time.time() * 1000)})
                }
                
                # Ensure POST request for detect_gold_symbol
                payload = {'timestamp': int(time.time() * 1000)}
                response = requests.post(f"{self.api_base_url}/detect_gold_symbol", 
                                      json=payload, headers=headers, timeout=15)
                
                print(f"Detection response status: {response.status_code}")
                print(f"Detection response: {response.text}")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success') and data.get('gold_symbol'):
                        self.symbol = data['gold_symbol']
                        self.symbol_detected = True
                        def on_symbol_detected_callback(dt):
                            self.on_symbol_detected(data['gold_symbol'])
                        Clock.schedule_once(on_symbol_detected_callback, 0)
                    else:
                        # Handle case where no gold symbol is detected
                        possible_symbols = data.get('possible_gold_symbols', [])
                        if possible_symbols:
                            def show_symbol_selection_callback(dt):
                                self.show_symbol_selection(possible_symbols)
                            Clock.schedule_once(show_symbol_selection_callback, 0)
                        else:
                            def update_status_no_symbols(dt):
                                self.update_status("No gold symbols found. Check MT5 configuration.")
                                self.show_popup("No Symbols", 
                                              "No gold symbols detected. Ensure gold is available in MT5 terminal.")
                            Clock.schedule_once(update_status_no_symbols, 0)
                else:
                    error_msg = f"Status {response.status_code}: {response.text}"
                    def update_status_failed(dt):
                        self.update_status(f"Failed to detect gold symbol: {error_msg}")
                        self.show_popup("Detection Error", 
                                      f"Failed to detect gold symbol: {error_msg}")
                    Clock.schedule_once(update_status_failed, 0)
                    
            except requests.exceptions.RequestException as e:
                print(f"Symbol detection error: {e}")
                error_msg = str(e)
                def update_status_error(dt):
                    self.update_status(f"Symbol detection failed: {error_msg}")
                    self.show_popup("Network Error", 
                                  f"Network error during symbol detection: {error_msg}")
                Clock.schedule_once(update_status_error, 0)
        
        threading.Thread(target=detect_symbol, daemon=True).start()
    
    def on_symbol_detected(self, symbol):
        """Called when gold symbol is successfully detected"""
        self.symbol_label.text = f'Gold Symbol: {symbol}'
        self.update_status("Gold symbol detected - Ready to trade")
        self.buy_button.disabled = False
        self.sell_button.disabled = False
        self.fetch_account_info()
    
    def show_symbol_selection(self, possible_symbols):
        """Show popup for manual symbol selection"""
        if not possible_symbols:
            self.show_popup("No Gold Symbols", 
                          "No gold symbols found. Please check MT5 terminal and ensure gold is available.")
            return
        
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text='Select your broker\'s gold symbol:'))
        
        for symbol in possible_symbols[:10]:  # Show max 10 symbols
            btn = Button(text=symbol, size_hint_y=None, height=40)
            btn.bind(on_press=lambda x, sym=symbol: self.set_manual_symbol(sym))
            content.add_widget(btn)
        
        close_btn = Button(text='Cancel', size_hint_y=None, height=40,
                          background_color=(0.5, 0.5, 0.5, 1))
        content.add_widget(close_btn)
        
        popup = Popup(title='Select Gold Symbol', content=content, size_hint=(0.8, 0.8))
        close_btn.bind(on_press=popup.dismiss)
        self.symbol_popup = popup
        popup.open()
    
    def set_manual_symbol(self, symbol):
        """Set gold symbol manually"""
        def set_symbol():
            try:
                response = self.make_secure_request('set_gold_symbol', {'symbol': symbol})
                if response and response.get('success'):
                    self.symbol = symbol
                    self.symbol_detected = True
                    def on_manual_symbol_set_callback(dt):
                        self.on_manual_symbol_set(symbol)
                    Clock.schedule_once(on_manual_symbol_set_callback, 0)
                else:
                    error_msg = response.get('error', 'Failed to set symbol') if response else 'Connection error'
                    def show_error_popup(dt):
                        self.show_popup("Error", f"Failed to set symbol: {error_msg}")
                    Clock.schedule_once(show_error_popup, 0)
            except Exception as e:
                error_msg = str(e)
                def show_error_popup(dt):
                    self.show_popup("Error", f"Error setting symbol: {error_msg}")
                Clock.schedule_once(show_error_popup, 0)
        
        if hasattr(self, 'symbol_popup'):
            self.symbol_popup.dismiss()
        
        threading.Thread(target=set_symbol, daemon=True).start()
    
    def on_manual_symbol_set(self, symbol):
        """Called when symbol is manually set successfully"""
        self.symbol_label.text = f'Gold Symbol: {symbol}'
        self.update_status(f"Symbol set to {symbol} - Ready to trade")
        self.buy_button.disabled = False
        self.sell_button.disabled = False
        self.fetch_account_info()
    
    def refresh_connection(self, instance):
        """Refresh connection and re-detect symbol"""
        self.symbol = None
        self.symbol_detected = False
        self.buy_button.disabled = True
        self.sell_button.disabled = True
        self.symbol_label.text = 'Detecting gold symbol...'
        self.update_status('Refreshing connection...')
        Clock.schedule_once(self.check_initial_connection, 0.5)
    
    def fetch_account_info(self):
        """Fetch real account info from MT5"""
        def fetch_info():
            try:
                response = self.make_secure_request('get_account_info')
                if response and response.get('success'):
                    self.balance = response.get('balance', self.balance)
                    def update_ui_callback(dt):
                        self.update_ui()
                    Clock.schedule_once(update_ui_callback, 0)
                    
                # Also fetch current positions
                pos_response = self.make_secure_request('get_positions')
                if pos_response and pos_response.get('success'):
                    gold_positions = pos_response.get('gold_positions', [])
                    total_volume = sum(pos['volume'] if pos['type'] == 'buy' else -pos['volume'] 
                                     for pos in gold_positions)
                    self.position = total_volume
                    def update_ui_callback2(dt):
                        self.update_ui()
                    Clock.schedule_once(update_ui_callback2, 0)
                    
            except Exception as e:
                print(f"Error fetching account info: {e}")
        
        threading.Thread(target=fetch_info, daemon=True).start()
    
    def generate_signature(self, data):
        """Generate HMAC signature for secure API requests"""
        message = json.dumps(data, sort_keys=True)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def make_secure_request(self, endpoint, data=None):
        """Make secure API request with authentication"""
        if data is None:
            data = {}
        
        # Add timestamp for replay attack prevention
        data['timestamp'] = int(time.time() * 1000)
        
        headers = {
            'Content-Type': 'application/json',
            'X-API-Key': self.api_key,
            'X-Signature': self.generate_signature(data)
        }
        
        try:
            url = f"{self.api_base_url}/{endpoint}"
            print(f"Making request to: {url} with data: {data}")
            
            response = requests.post(url, json=data, headers=headers, timeout=10)
            
            print(f"Response status: {response.status_code}")
            print(f"Response text: {response.text}")
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"API error: {response.text}")
                return {'error': f'API returned status {response.status_code}: {response.text}'}
                
        except requests.exceptions.ConnectionError:
            print("Connection error: Flask server not running")
            return {'error': 'Flask server not running. Please start the Flask API server first.'}
        except requests.exceptions.Timeout:
            print("Request timeout")
            return {'error': 'Request timeout. Server may be overloaded.'}
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return {'error': f'Network error: {str(e)}'}
        except Exception as e:
            print(f"Unexpected error: {e}")
            return {'error': f'Unexpected error: {str(e)}'}
    
    def check_server_connection(self):
        """Check if Flask server is running"""
        try:
            response = requests.get(f"{self.api_base_url}/status", timeout=5)
            print(f"Server status check: {response.status_code}")
            return response.status_code == 200
        except Exception as e:
            print(f"Server connection check failed: {e}")
            return False
    
    def update_price(self, dt):
        """Update gold price from MT5 via Flask API"""
        if not self.symbol_detected or not self.symbol:
            return
        
        def fetch_price():
            try:
                response = self.make_secure_request('get_price', {})
                if response:
                    if 'price' in response:
                        self.current_price = response['price']
                        self.market_closed_shown = False
                        def update_ui_callback(dt):
                            self.update_ui()
                        Clock.schedule_once(update_ui_callback, 0)
                    elif 'error' in response:
                        print(f"Price fetch error: {response['error']}")
                        if "not found" in response['error'].lower():
                            def update_status_redetect(dt):
                                self.update_status("Symbol issue - Re-detecting...")
                            Clock.schedule_once(update_status_redetect, 0)
                            self.symbol_detected = False
                            self.detect_gold_symbol()
                        elif "market is closed" in response['error'].lower() and not self.market_closed_shown:
                            symbol_name = self.symbol
                            def show_market_closed_popup(dt):
                                self.show_popup("Market Closed", 
                                              f"Market is closed for {symbol_name}. Price updates paused.")
                            Clock.schedule_once(show_market_closed_popup, 0)
                            self.market_closed_shown = True
                            def update_status_closed(dt):
                                self.update_status(f"Market closed for {symbol_name}")
                            Clock.schedule_once(update_status_closed, 0)
                        else:
                            error_msg = response['error']
                            def update_status_error(dt):
                                self.update_status(f"Price error: {error_msg}")
                            Clock.schedule_once(update_status_error, 0)
            except Exception as e:
                print(f"Price update error: {e}")
                def update_status_failed(dt):
                    self.update_status("Price update failed")
                Clock.schedule_once(update_status_failed, 0)
        
        threading.Thread(target=fetch_price, daemon=True).start()
    
    def update_status(self, message):
        """Update status label"""
        self.status_label.text = message
    
    def update_ui(self):
        """Update UI elements on main thread"""
        self.price_label.text = f'Gold Price: ${self.current_price:.2f}'
        self.balance_label.text = f'Balance: ${self.balance:.2f}'
        self.position_label.text = f'Position: {self.position:.3f} oz'
        
        if self.symbol:
            self.symbol_label.text = f'Symbol: {self.symbol}'
    
    def on_buy_pressed(self, instance):
        """Handle buy button press"""
        if not self.symbol_detected:
            self.show_popup("Error", "Gold symbol not detected yet. Please wait or refresh connection.")
            return
        
        try:
            lot_size = float(self.lot_input.text)
            if lot_size <= 0:
                self.show_popup("Error", "Lot size must be positive")
                return
            self.execute_trade('buy', lot_size)
        except ValueError:
            self.show_popup("Error", "Invalid lot size. Please enter a number.")
    
    def on_sell_pressed(self, instance):
        """Handle sell button press"""
        if not self.symbol_detected:
            self.show_popup("Error", "Gold symbol not detected yet. Please wait or refresh connection.")
            return
        
        try:
            lot_size = float(self.lot_input.text)
            if lot_size <= 0:
                self.show_popup("Error", "Lot size must be positive")
                return
            self.execute_trade('sell', lot_size)
        except ValueError:
            self.show_popup("Error", "Invalid lot size. Please enter a number.")
    
    def execute_trade(self, action, lot_size):
        """Execute trade via MT5 API"""
        def trade_thread():
            def update_status_executing(dt):
                self.update_status(f"Executing {action.upper()}...")
            Clock.schedule_once(update_status_executing, 0)
            
            trade_data = {
                'action': action,
                'lot_size': lot_size
            }
            
            response = self.make_secure_request('execute_trade', trade_data)
            
            if response and response.get('success'):
                def trade_success_callback(dt):
                    self.trade_success(action, lot_size, response)
                Clock.schedule_once(trade_success_callback, 0)
                self.fetch_account_info()
            else:
                error_msg = response.get('error', 'Trade failed') if response else 'Connection error'
                print(f"Trade failed: {error_msg}")
                if "market is closed" in error_msg.lower():
                    symbol_name = self.symbol
                    def show_market_closed_popup(dt):
                        self.show_popup("Market Closed", 
                                      f"Cannot execute trade: Market is closed for {symbol_name}.")
                    Clock.schedule_once(show_market_closed_popup, 0)
                elif "symbol" in error_msg.lower() and "not found" in error_msg.lower():
                    def show_symbol_error_popup(dt):
                        self.show_popup("Symbol Error", 
                                      "Gold symbol issue. Trying to re-detect symbol...")
                    Clock.schedule_once(show_symbol_error_popup, 0)
                    self.symbol_detected = False
                    self.detect_gold_symbol()
                else:
                    def trade_failed_callback(dt):
                        self.trade_failed(error_msg)
                    Clock.schedule_once(trade_failed_callback, 0)
        
        threading.Thread(target=trade_thread, daemon=True).start()
    
    def trade_success(self, action, lot_size, response):
        """Handle successful trade"""
        actual_price = response.get('price', self.current_price)
        order_id = response.get('order_id', 'Unknown')
        
        self.status_label.text = f"{action.upper()} {lot_size} oz executed successfully"
        self.show_popup("Trade Executed", 
                       f"{action.upper()} {lot_size} oz of Gold\n"
                       f"Price: ${actual_price:.2f}\n"
                       f"Order ID: {order_id}")
    
    def trade_failed(self, error_msg):
        """Handle failed trade"""
        self.status_label.text = "Trade failed"
        self.show_popup("Trade Failed", error_msg)
    
    def show_popup(self, title, message):
        """Show popup message"""
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        content.add_widget(Label(text=message, text_size=(None, None)))
        
        close_btn = Button(text='Close', size_hint_y=None, height=40)
        content.add_widget(close_btn)
        
        popup = Popup(title=title, content=content, size_hint=(0.8, 0.6))
        close_btn.bind(on_press=popup.dismiss)
        popup.open()
    
    def debug_connection(self):
        """Debug connection issues"""
        def debug_thread():
            print("=== Starting Connection Debug ===")
            # Test raw socket connection
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex(('92.118.46.58', 5000))  # Match Flask port
                sock.close()
                
                if result == 0:
                    print("Socket connection: SUCCESS")
                else:
                    print(f"Socket connection: FAILED (error {result})")
            except Exception as e:
                print(f"Socket test error: {e}")
            
            # Test HTTP request
            try:
                response = requests.get(f"{self.api_base_url}/status", timeout=10)
                print(f"HTTP status: {response.status_code}")
                print(f"Response: {response.text}")
            except Exception as e:
                print(f"HTTP test error: {e}")
            print("=== End Connection Debug ===")
        
        threading.Thread(target=debug_thread, daemon=True).start()

if __name__ == '__main__':
    GoldTradingApp().run()