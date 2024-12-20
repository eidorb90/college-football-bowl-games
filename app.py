from flask import Flask, jsonify, request, render_template, session, redirect, url_for, abort
from datetime import datetime
import json
import os
from functools import wraps

# Initialize Flask application
app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # In production, use a secure secret key

# Constants for application configuration
VALID_CODE = 'BWCFBG'  # Access code users need to enter
ADMIN_CODE = 'BlainSucks'  # Admin access code
ADMIN_USERS = {'BrodieAdmin', 'RhettAdmin'}  # Set of admin usernames
GAMES_FILE = 'data/games.json'  # File storing bowl game information
PICKS_FILE = 'data/picks.json'  # File storing user picks

# Ensure data directory exists at startup
os.makedirs('data', exist_ok=True)

def login_required(f):
    """
    Decorator to require login for protected routes.
    Redirects to login page if user is not authenticated.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """
    Decorator to require admin access for protected routes.
    Returns 403 if user is not an admin.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session or 'is_admin' not in session:
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def initialize_picks():
    """Initialize or validate the picks data file."""
    if not os.path.exists(PICKS_FILE):
        with open(PICKS_FILE, 'w') as f:
            json.dump({}, f, indent=2)
    else:
        try:
            with open(PICKS_FILE, 'r') as f:
                json.load(f)
        except json.JSONDecodeError:
            with open(PICKS_FILE, 'w') as f:
                json.dump({}, f, indent=2)

def ensure_valid_games_file():
    """Ensure the games.json file exists and contains valid data."""
    try:
        with open(GAMES_FILE, 'r') as f:
            json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        games = {"games": [
            {
                "id": "celebration-bowl",
                "name": "Celebration Bowl",
                "team1": "South Carolina State",
                "team2": "Jackson State",
                "date": "Dec 14, 2024",
                "time": "12:00 PM ET",
                "location": "Mercedes-Benz Stadium, Atlanta, Georgia",
                "status": "scheduled",
                "winner": None
            }
        ]}
        with open(GAMES_FILE, 'w') as f:
            json.dump(games, f, indent=2)

@app.route('/')
def login():
    """Serve the login page or redirect to picker if already logged in."""
    if 'username' in session:
        return redirect(url_for('picker'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def handle_login():
    """Handle login form submission."""
    username = request.form.get('username')
    code = request.form.get('code')
    
    if code != VALID_CODE:
        return jsonify({'error': 'Invalid access code'}), 401
    
    session['username'] = username
    return jsonify({'status': 'success'})

@app.route('/picker')
@login_required
def picker():
    """Serve the main picker page."""
    return render_template('picker.html')

@app.route('/leaderboard')
@login_required
def leaderboard():
    """Serve the leaderboard page."""
    return render_template('leaderboard.html')

@app.route('/admin')
@login_required
def admin_panel():
    """Serve the admin panel page."""
    return render_template('admin.html')

@app.route('/api/admin/verify', methods=['POST'])
@login_required
def verify_admin():
    """Verify admin code and grant admin privileges"""
    try:
        admin_code = request.json.get('admin_code')
        if admin_code == ADMIN_CODE:
            session['is_admin'] = True
            return jsonify({'status': 'success'})
        return jsonify({'error': 'Invalid admin code'}), 401
    except Exception as e:
        print(f"Error in admin verification: {str(e)}")
        return jsonify({'error': 'Verification error'}), 500

@app.route('/logout')
def logout():
    """Handle user logout."""
    session.pop('username', None)
    session.pop('is_admin', None)
    return redirect(url_for('login'))

@app.route('/api/games')
@login_required
def get_games():
    """Return all bowl games data."""
    try:
        with open(GAMES_FILE, 'r') as f:
            data = json.load(f)
            return jsonify(data['games'])
    except (FileNotFoundError, json.JSONDecodeError):
        ensure_valid_games_file()
        with open(GAMES_FILE, 'r') as f:
            data = json.load(f)
            return jsonify(data['games'])

@app.route('/api/submit-picks', methods=['POST'])
@login_required
def submit_picks():
    """Submit picks for a user."""
    try:
        user_picks = request.json
        username = session['username']
        
        if not os.path.exists(PICKS_FILE):
            initialize_picks()
            all_picks = {}
        else:
            try:
                with open(PICKS_FILE, 'r') as f:
                    all_picks = json.load(f)
            except json.JSONDecodeError:
                all_picks = {}
        
        all_picks[username] = {
            'picks': user_picks.get('picks', {}),
            'championship_prediction': user_picks.get('championship_prediction', {
                'team1_score': None,
                'team2_score': None
            }),
            'timestamp': datetime.now().isoformat()
        }
        
        with open(PICKS_FILE, 'w') as f:
            json.dump(all_picks, f, indent=2)
        
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error in submit_picks: {str(e)}")
        return jsonify({'error': 'Error submitting picks'}), 500

@app.route('/api/community-picks')
@login_required
def get_community_picks():
    """Return aggregated community picks for all games."""
    try:
        if not os.path.exists(PICKS_FILE):
            initialize_picks()
            return jsonify({})
            
        with open(PICKS_FILE, 'r') as f:
            try:
                all_picks = json.load(f)
            except json.JSONDecodeError:
                initialize_picks()
                return jsonify({})
                
        community_picks = {}
        for username, user_data in all_picks.items():
            picks = user_data['picks']
            for game_id, team in picks.items():
                if game_id not in community_picks:
                    community_picks[game_id] = {
                        'picks': {},
                        'users': {}
                    }
                if team not in community_picks[game_id]['picks']:
                    community_picks[game_id]['picks'][team] = 0
                    community_picks[game_id]['users'][team] = []
                
                community_picks[game_id]['picks'][team] += 1
                community_picks[game_id]['users'][team].append(username)
        
        return jsonify(community_picks)
    except Exception as e:
        print(f"Error in get_community_picks: {str(e)}")
        return jsonify({})

@app.route('/api/admin/update-game', methods=['POST'])
@login_required
@admin_required
def admin_update_game():
    """Update game details, status, and winner."""
    try:
        game_data = request.json
        game_id = game_data.get('game_id')
        status = game_data.get('status')
        winner = game_data.get('winner')

        with open(GAMES_FILE, 'r') as f:
            data = json.load(f)

        for game in data['games']:
            if game['id'] == game_id:
                game['team1'] = game_data.get('team1', game['team1'])
                game['team2'] = game_data.get('team2', game['team2'])
                game['date'] = game_data.get('date', game['date'])
                game['time'] = game_data.get('time', game['time'])
                game['location'] = game_data.get('location', game['location'])
                game['status'] = status
                game['winner'] = winner
                break

        with open(GAMES_FILE, 'w') as f:
            json.dump(data, f, indent=2)

        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error updating game: {str(e)}")
        return jsonify({'error': 'Error updating game'}), 500

@app.route('/api/admin/update-picks', methods=['POST'])
@login_required
@admin_required
def admin_update_picks():
    """Update picks for a specific user."""
    try:
        data = request.json
        username = data.get('username')
        new_picks = data.get('picks')
        
        if not username or not new_picks:
            return jsonify({'error': 'Missing required data'}), 400
            
        with open(PICKS_FILE, 'r') as f:
            all_picks = json.load(f)
            
        if username not in all_picks:
            return jsonify({'error': 'User not found'}), 404
            
        all_picks[username]['picks'] = new_picks
        all_picks[username]['timestamp'] = datetime.now().isoformat()
        
        with open(PICKS_FILE, 'w') as f:
            json.dump(all_picks, f, indent=2)
            
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error updating picks: {str(e)}")
        return jsonify({'error': 'Error updating picks'}), 500

@app.route('/api/admin/clear-picks', methods=['POST'])
@login_required
@admin_required
def admin_clear_picks():
    """Clear all picks for a specific user."""
    try:
        username = request.json.get('username')
        
        if not username:
            return jsonify({'error': 'Username required'}), 400
            
        with open(PICKS_FILE, 'r') as f:
            all_picks = json.load(f)
            
        if username not in all_picks:
            return jsonify({'error': 'User not found'}), 404
            
        all_picks[username]['picks'] = {}
        all_picks[username]['championship_prediction'] = {
            'team1_score': None,
            'team2_score': None
        }
        all_picks[username]['timestamp'] = datetime.now().isoformat()
        
        with open(PICKS_FILE, 'w') as f:
            json.dump(all_picks, f, indent=2)
            
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error clearing picks: {str(e)}")
        return jsonify({'error': 'Error clearing picks'}), 500

@app.route('/api/admin/upload-picks', methods=['POST'])
@login_required
@admin_required
def admin_upload_picks():
    """Upload entire picks dataset."""
    try:
        new_picks = request.json
        
        if not isinstance(new_picks, dict):
            return jsonify({'error': 'Invalid picks data format'}), 400
            
        # Validate the structure of uploaded picks
        for username, user_data in new_picks.items():
            if not isinstance(user_data, dict) or 'picks' not in user_data:
                return jsonify({'error': f'Invalid data format for user {username}'}), 400
        
        with open(PICKS_FILE, 'w') as f:
            json.dump(new_picks, f, indent=2)
            
        return jsonify({'status': 'success'})
    except Exception as e:
        print(f"Error uploading picks: {str(e)}")
        return jsonify({'error': 'Error uploading picks'}), 500

@app.route('/api/all-picks')
@login_required
def get_all_picks():
    """Return all user picks data."""
    try:
        with open(PICKS_FILE, 'r') as f:
            all_picks = json.load(f)
        return jsonify(all_picks)
    except Exception as e:
        print(f"Error getting all picks: {str(e)}")
        return jsonify({}), 500

@app.route('/api/leaderboard')
@login_required
def get_leaderboard():
    """Calculate and return the leaderboard based on completed games."""
    try:
        # Get completed games
        with open(GAMES_FILE, 'r') as f:
            games_data = json.load(f)
        completed_games = {
            game['id']: game['winner'] 
            for game in games_data['games'] 
            if game.get('status') == 'completed' and game.get('winner')
        }
        
        # Get all user picks
        with open(PICKS_FILE, 'r') as f:
            all_picks = json.load(f)
        
        # Calculate scores for each user
        leaderboard = []
        for username, user_data in all_picks.items():
            correct_picks = 0
            total_applicable_picks = 0
            
            user_picks = user_data['picks']
            for game_id, picked_team in user_picks.items():
                if game_id in completed_games:
                    total_applicable_picks += 1
                    if picked_team == completed_games[game_id]:
                        correct_picks += 1
            
            percentage = (correct_picks / total_applicable_picks * 100) if total_applicable_picks > 0 else 0
            
            leaderboard.append({
                'username': username,
                'correct_picks': correct_picks,
                'total_picks': total_applicable_picks,
                'percentage': round(percentage, 1)
            })
        
        # Sort by correct picks (desc) and username (asc)
        leaderboard.sort(key=lambda x: (-x['correct_picks'], x['username']))
        
        return jsonify(leaderboard)
    except Exception as e:
        print(f"Error generating leaderboard: {str(e)}")
        return jsonify([])

def create_app():
    """Create and configure the Flask application."""
    os.makedirs('data', exist_ok=True)
    initialize_picks()
    ensure_valid_games_file()
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
