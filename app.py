from flask import Flask, request, jsonify
import MetaTrader5 as mt5
import hashlib
import hmac
import json
import time
from functools import wraps

app = Flask(__name__)

# Security configuration
API_KEY = "12345"
API_SECRET = "mysecret123"
MAX_REQUEST_AGE = 60000  # 60 seconds in milliseconds

# Global variable to store the detected gold symbol
GOLD_SYMBOL = None

def verify_signature(f):
    """Decorator to verify API request signatures"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        signature = request.headers.get('X-Signature')
        
        if not api_key or not signature:
            return jsonify({'error': 'Missing authentication headers'}), 401
        
        if api_key != API_KEY:
            return jsonify({'error': 'Invalid API key'}), 401
        
        # Verify signature
        data = request.get_json() or {}
        expected_signature = hmac.new(
            API_SECRET.encode('utf-8'),
            json.dumps(data, sort_keys=True).encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            return jsonify({'error': 'Invalid signature'}), 401
        
        # Check timestamp to prevent replay attacks
        timestamp = data.get('timestamp', 0)
        current_time = int(time.time() * 1000)
        if abs(current_time - timestamp) > MAX_REQUEST_AGE:
            return jsonify({'error': 'Request too old'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

def detect_gold_symbol():
    """Auto-detect the gold symbol used by the broker"""
    global GOLD_SYMBOL
    
    print("Detecting gold symbol...")
    
    # Common gold symbol variations used by different brokers
    possible_symbols = [
        'XAUUSD', 'GOLD', 'GOLDUSD', 'XAU/USD', 'XAU_USD', 'GOLD.a',
        'GOLD.c', 'GOLD.m', 'GOLDm', 'XAUUSDm', 'Au', 'AUUSD', 'GC',
        'XAUEUR', 'XAUGBP'
    ]
    
    # Get all available symbols
    try:
        all_symbols = mt5.symbols_get()
        if not all_symbols:
            print("No symbols available from broker")
            return None
        
        available_symbol_names = [s.name for s in all_symbols]
        print(f"Total symbols available: {len(available_symbol_names)}")
        
        # Method 1: Try exact matches first
        for symbol in possible_symbols:
            if symbol in available_symbol_names:
                if mt5.symbol_select(symbol, True):
                    tick = mt5.symbol_info_tick(symbol)
                    if tick is not None:
                        print(f"✓ Found gold symbol: {symbol}")
                        GOLD_SYMBOL = symbol
                        return symbol
        
        # Method 2: Search for symbols containing gold-related keywords
        gold_keywords = ['XAU', 'GOLD', 'AU', 'GC']
        found_gold_symbols = []
        
        for symbol_obj in all_symbols:
            symbol_name = symbol_obj.name.upper()
            for keyword in gold_keywords:
                if keyword in symbol_name:
                    if 'USD' in symbol_name or keyword == 'GOLD':
                        found_gold_symbols.append(symbol_obj.name)
                        break
        
        print(f"Found potential gold symbols: {found_gold_symbols}")
        
        # Test each found symbol
        for symbol in found_gold_symbols:
            if mt5.symbol_select(symbol, True):
                tick = mt5.symbol_info_tick(symbol)
                symbol_info = mt5.symbol_info(symbol)
                
                if tick is not None and symbol_info is not None:
                    avg_price = (tick.bid + tick.ask) / 2
                    if 1000 <= avg_price <= 5000:  # Reasonable gold price range
                        print(f"✓ Auto-detected gold symbol: {symbol} (Price: ${avg_price:.2f})")
                        GOLD_SYMBOL = symbol
                        return symbol
        
        print("\nCould not auto-detect gold symbol. Available symbols containing potential gold keywords:")
        for symbol in found_gold_symbols[:10]:
            try:
                if mt5.symbol_select(symbol, True):
                    tick = mt5.symbol_info_tick(symbol)
                    if tick:
                        avg_price = (tick.bid + tick.ask) / 2
                        print(f"  {symbol}: ${avg_price:.2f}")
            except:
                continue
        
        if found_gold_symbols:
            print(f"\nTo manually set gold symbol, use /api/set_gold_symbol endpoint with one of: {found_gold_symbols}")
        
        return None
        
    except Exception as e:
        print(f"Error detecting gold symbol: {str(e)}")
        return None

def get_gold_symbol():
    """Get the detected gold symbol or try to detect it"""
    global GOLD_SYMBOL
    
    if GOLD_SYMBOL is None:
        GOLD_SYMBOL = detect_gold_symbol()
    
    return GOLD_SYMBOL

def initialize_mt5():
    """Initialize MT5 connection"""
    print("Attempting MT5 initialization...")
    if not mt5.initialize():
        print(f"MT5 initialization failed: {mt5.last_error()}")
        return False
    
    account_info = mt5.account_info()
    if account_info is not None:
        print(f"MT5 logged in - Account: {account_info.login}, Server: {account_info.server}, Balance: ${account_info.balance}")
        return True
    
    # Replace with your MT5 credentials
    MT5_LOGIN = None  # Set your account number
    MT5_PASSWORD = None  # Set your password
    MT5_SERVER = None  # Set your server
    
    if MT5_LOGIN and MT5_PASSWORD and MT5_SERVER:
        print("Attempting MT5 login...")
        if mt5.login(MT5_LOGIN, MT5_PASSWORD, MT5_SERVER):
            print("MT5 login successful")
            return True
        else:
            print(f"MT5 login failed: {mt5.last_error()}")
            return False
    
    print("MT5 not logged in - please login manually in MT5 terminal")
    return False

@app.route('/api/detect_gold_symbol', methods=['POST'])
@verify_signature
def detect_gold_symbol_endpoint():
    """Endpoint to manually trigger gold symbol detection"""
    try:
        if not mt5.initialize():
            return jsonify({'error': 'MT5 initialization failed'}), 500
        
        detected_symbol = detect_gold_symbol()
        if detected_symbol:
            return jsonify({
                'success': True,
                'gold_symbol': detected_symbol,
                'message': f'Gold symbol auto-detected as: {detected_symbol}'
            }), 200
        else:
            symbols = mt5.symbols_get()
            gold_like_symbols = []
            
            if symbols:
                for s in symbols:
                    name_upper = s.name.upper()
                    if any(keyword in name_upper for keyword in ['XAU', 'GOLD', 'AU', 'GC']):
                        gold_like_symbols.append(s.name)
            
            return jsonify({
                'success': False,
                'message': 'Could not auto-detect gold symbol',
                'possible_gold_symbols': gold_like_symbols[:20],
                'instruction': 'Please check MT5 terminal for the exact gold symbol name or use /api/set_gold_symbol'
            }), 200
    
    except Exception as e:
        print(f"Error in detect_gold_symbol_endpoint: {str(e)}")
        return jsonify({'error': f'Detection failed: {str(e)}'}), 500

@app.route('/api/list_symbols', methods=['POST'])
@verify_signature
def list_symbols():
    """Get list of available symbols from MT5"""
    try:
        if not mt5.initialize():
            return jsonify({'error': 'MT5 initialization failed'}), 500
        
        symbols = mt5.symbols_get()
        if not symbols:
            return jsonify({'error': 'No symbols available'}), 500
        
        if GOLD_SYMBOL is None:
            detect_gold_symbol()
        
        gold_symbols = [s.name for s in symbols if any(keyword in s.name.upper() for keyword in ['XAU', 'GOLD', 'AU', 'GC'])]
        sample_symbols = [s.name for s in symbols][:10]
        
        print(f"Available gold-related symbols: {gold_symbols}")
        print(f"Sample symbols: {sample_symbols}")
        print(f"Detected gold symbol: {GOLD_SYMBOL}")
        
        return jsonify({
            'success': True,
            'detected_gold_symbol': GOLD_SYMBOL,
            'gold_related_symbols': gold_symbols,
            'sample_symbols': sample_symbols,
            'total_symbols': len(symbols)
        }), 200
        
    except Exception as e:
        print(f"Error fetching symbols: {str(e)}")
        return jsonify({'error': f'Failed to fetch symbols: {str(e)}'}), 500

@app.route('/api/get_price', methods=['POST'])
@verify_signature
def get_price():
    """Get current price for a symbol"""
    try:
        if not mt5.initialize():
            return jsonify({'error': 'MT5 initialization failed'}), 500
        
        data = request.get_json()
        symbol = data.get('symbol')
        
        if not symbol:
            symbol = get_gold_symbol()
            if not symbol:
                return jsonify({'error': 'No symbol provided and could not auto-detect gold symbol'}), 400
        
        if not mt5.symbol_select(symbol, True):
            return jsonify({'error': f'Symbol {symbol} not found or not available'}), 400
        
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return jsonify({'error': f'Could not get symbol info for {symbol}'}), 400
        
        if symbol_info.trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
            return jsonify({'error': f'Trading disabled for {symbol}'}), 400
        
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return jsonify({'error': f'No price data available for {symbol} (market may be closed)'}), 400
        
        price = (tick.bid + tick.ask) / 2
        
        return jsonify({
            'success': True,
            'symbol': symbol,
            'price': round(price, 2),
            'bid': round(tick.bid, 2),
            'ask': round(tick.ask, 2),
            'spread': round(tick.ask - tick.bid, 2),
            'timestamp': tick.time
        }), 200
        
    except Exception as e:
        print(f"Error in get_price: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/execute_trade', methods=['POST'])
@verify_signature
def execute_trade():
    """Execute a trade order"""
    try:
        if not mt5.initialize():
            return jsonify({'error': 'MT5 initialization failed'}), 500
        
        data = request.get_json()
        symbol = data.get('symbol')
        action = data.get('action')
        lot_size = float(data.get('lot_size', 0.01))
        
        if not symbol:
            symbol = get_gold_symbol()
            if not symbol:
                return jsonify({'error': 'No symbol provided and could not auto-detect gold symbol'}), 400
        
        if action not in ['buy', 'sell']:
            return jsonify({'error': 'Invalid action. Use "buy" or "sell"'}), 400
        
        if not mt5.symbol_select(symbol, True):
            return jsonify({'error': f'Symbol {symbol} not found or not available'}), 400
        
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return jsonify({'error': f'Could not get symbol info for {symbol}'}), 400
        
        if symbol_info.trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
            return jsonify({'error': f'Trading disabled for {symbol}'}), 400
        
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return jsonify({'error': f'No price data available for {symbol} (market may be closed)'}), 400
        
        if lot_size < symbol_info.volume_min:
            return jsonify({'error': f'Lot size too small. Minimum: {symbol_info.volume_min}'}), 400
        
        if lot_size > symbol_info.volume_max:
            return jsonify({'error': f'Lot size too large. Maximum: {symbol_info.volume_max}'}), 400
        
        order_type = mt5.ORDER_TYPE_BUY if action == 'buy' else mt5.ORDER_TYPE_SELL
        price = tick.ask if action == 'buy' else tick.bid
        
        request_data = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": 234000,
            "comment": "Gold trading app",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request_data)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return jsonify({
                'success': False,
                'error': f'Trade failed: {result.comment}',
                'retcode': result.retcode,
                'symbol_used': symbol
            }), 400
        
        return jsonify({
            'success': True,
            'order_id': result.order,
            'volume': result.volume,
            'price': result.price,
            'action': action,
            'symbol': symbol
        }), 200
        
    except Exception as e:
        print(f"Error in execute_trade: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_account_info', methods=['POST'])
@verify_signature
def get_account_info():
    """Get account information"""
    try:
        if not mt5.initialize():
            return jsonify({'error': 'MT5 initialization failed'}), 500
        
        account_info = mt5.account_info()
        if account_info is None:
            return jsonify({'error': 'Failed to get account info'}), 500
        
        return jsonify({
            'success': True,
            'balance': round(account_info.balance, 2),
            'equity': round(account_info.equity, 2),
            'margin': round(account_info.margin, 2),
            'free_margin': round(account_info.margin_free, 2),
            'leverage': account_info.leverage,
            'currency': account_info.currency
        }), 200
        
    except Exception as e:
        print(f"Error in get_account_info: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_positions', methods=['POST'])
@verify_signature
def get_positions():
    """Get current positions"""
    try:
        if not mt5.initialize():
            return jsonify({'error': 'MT5 initialization failed'}), 500
        
        all_positions = mt5.positions_get()
        if all_positions is None:
            all_positions = []
        
        gold_symbol = get_gold_symbol()
        if gold_symbol:
            gold_positions = mt5.positions_get(symbol=gold_symbol)
            if gold_positions is None:
                gold_positions = []
        else:
            gold_positions = []
        
        position_list = []
        for pos in all_positions:
            position_list.append({
                'ticket': pos.ticket,
                'symbol': pos.symbol,
                'volume': pos.volume,
                'type': 'buy' if pos.type == mt5.POSITION_TYPE_BUY else 'sell',
                'price_open': round(pos.price_open, 2),
                'price_current': round(pos.price_current, 2),
                'profit': round(pos.profit, 2),
                'comment': pos.comment
            })
        
        gold_position_list = []
        for pos in gold_positions:
            gold_position_list.append({
                'ticket': pos.ticket,
                'symbol': pos.symbol,
                'volume': pos.volume,
                'type': 'buy' if pos.type == mt5.POSITION_TYPE_BUY else 'sell',
                'price_open': round(pos.price_open, 2),
                'price_current': round(pos.price_current, 2),
                'profit': round(pos.profit, 2),
                'comment': pos.comment
            })
        
        return jsonify({
            'success': True,
            'all_positions': position_list,
            'gold_positions': gold_position_list,
            'detected_gold_symbol': gold_symbol
        }), 200
        
    except Exception as e:
        print(f"Error in get_positions: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/set_gold_symbol', methods=['POST'])
@verify_signature
def set_gold_symbol():
    """Manually set the gold symbol if auto-detection fails"""
    try:
        if not mt5.initialize():
            return jsonify({'error': 'MT5 initialization failed'}), 500
        
        data = request.get_json()
        symbol = data.get('symbol')
        
        if not symbol:
            return jsonify({'error': 'Symbol parameter required'}), 400
        
        if not mt5.symbol_select(symbol, True):
            return jsonify({'error': f'Symbol {symbol} not found or not available'}), 400
        
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return jsonify({'error': f'No price data available for {symbol}'}), 400
        
        global GOLD_SYMBOL
        GOLD_SYMBOL = symbol
        price = (tick.bid + tick.ask) / 2
        
        print(f"Gold symbol manually set to: {symbol}")
        
        return jsonify({
            'success': True,
            'message': f'Gold symbol set to {symbol}',
            'symbol': symbol,
            'current_price': round(price, 2)
        }), 200
        
    except Exception as e:
        print(f"Error setting gold symbol: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
def status():
    """Check API status and gold symbol detection"""
    try:
        mt5_connected = mt5.account_info() is not None
        gold_symbol = get_gold_symbol()
        
        status_info = {
            'success': True,
            'mt5_connected': mt5_connected,
            'detected_gold_symbol': gold_symbol,
            'api_version': '1.1',
            'message': 'Flask API is alive'
        }
        
        if gold_symbol:
            try:
                tick = mt5.symbol_info_tick(gold_symbol)
                if tick:
                    status_info['gold_price'] = round((tick.bid + tick.ask) / 2, 2)
            except:
                status_info['gold_price'] = None
                status_info['message'] = f'Gold symbol {gold_symbol} detected but price unavailable'
        
        return jsonify(status_info), 200
        
    except Exception as e:
        print(f"Error in status endpoint: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

if __name__ == '__main__':
    if initialize_mt5():
        print("Starting Flask API server...")
        print("Detecting gold symbol...")
        
        detected = detect_gold_symbol()
        if detected:
            print(f"✓ Gold symbol detected: {detected}")
        else:
            print("⚠ Could not auto-detect gold symbol. Use /api/detect_gold_symbol or /api/set_gold_symbol endpoints")
        
        print("\nAPI Endpoints:")
        print("- GET /api/status - Check status and detected symbols")
        print("- POST /api/detect_gold_symbol - Re-run gold symbol detection")
        print("- POST /api/set_gold_symbol - Manually set gold symbol")
        print("- POST /api/list_symbols - List all available symbols")
        print("- POST /api/get_price - Get current price")
        print("- POST /api/execute_trade - Execute trades")
        print("- POST /api/get_positions - Get current positions")
        print("- POST /api/get_account_info - Get account information")
        
        try:
            print("Starting Flask server on port 5000...")
            print("Server accessible at: http://92.118.46.58:5000")
            app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
        except Exception as e:
            print(f"Failed to start server: {e}")
    else:
        print("Failed to initialize MT5")