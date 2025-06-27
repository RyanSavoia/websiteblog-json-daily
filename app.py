from flask import Flask
import requests
import json
from datetime import datetime
import os
import threading
import time
import schedule

app = Flask(__name__)

# API endpoints
MLB_API_URL = "https://mlb-matchup-api-savant.onrender.com/latest"
UMPIRE_API_URL = "https://umpire-json-api.onrender.com"

# Global storage for blogs and last update time
blogs_cache = {
    'blogs': [],
    'last_updated': None,
    'umpires_last_updated': None
}

def get_mlb_data():
    """Fetch MLB matchup data"""
    try:
        print("🌐 Fetching MLB data...")
        response = requests.get(MLB_API_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
        print(f"✅ Got {len(data.get('reports', []))} games")
        return data.get('reports', [])
    except Exception as e:
        print(f"❌ Error fetching MLB data: {e}")
        return []

def get_umpire_data():
    """Fetch umpire data"""
    try:
        print("🌐 Fetching umpire data...")
        response = requests.get(UMPIRE_API_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
        print(f"✅ Got umpire data for {len(data)} umpires")
        return data
    except Exception as e:
        print(f"❌ Error fetching umpire data: {e}")
        return []

def find_game_umpire(umpires, matchup):
    """Find the umpire for a specific game matchup"""
    for ump in umpires:
        if ump.get('matchup', '-') == matchup:
            return ump
    
    if ' @ ' in matchup:
        away_team, home_team = matchup.split(' @ ')
        for ump in umpires:
            ump_matchup = ump.get('matchup', '-')
            if away_team in ump_matchup and home_team in ump_matchup:
                return ump
    
    return None

def format_boost_percentage(multiplier_str):
    """Convert multiplier like '1.25x' to percentage like '25% boost'"""
    try:
        multiplier = float(multiplier_str.replace('x', ''))
        if multiplier > 1.0:
            percentage = (multiplier - 1.0) * 100
            return f"{percentage:.0f}% boost"
        elif multiplier < 1.0:
            percentage = (1.0 - multiplier) * 100
            return f"{percentage:.0f}% decrease"
        else:
            return "No change"
    except:
        return multiplier_str

def generate_all_blogs():
    """Generate all game blogs and update cache"""
    global blogs_cache
    
    print(f"🚀 Generating blogs at {datetime.now()}")
    
    mlb_reports = get_mlb_data()
    umpires = get_umpire_data()
    
    if not mlb_reports:
        print("❌ No MLB data available")
        return
    
    # Simple blog data for now
    blogs_cache['blogs'] = []
    for game_report in mlb_reports:
        try:
            matchup = game_report.get('matchup', 'Unknown')
            blogs_cache['blogs'].append({
                'matchup': matchup,
                'away_team': matchup.split(' @ ')[0] if ' @ ' in matchup else 'Away',
                'home_team': matchup.split(' @ ')[1] if ' @ ' in matchup else 'Home'
            })
        except Exception as e:
            print(f"❌ Error processing game: {e}")
    
    blogs_cache['last_updated'] = datetime.now()
    print(f"✅ Generated {len(blogs_cache['blogs'])} blogs")

def generate_games_html():
    """Generate HTML for all games"""
    if not blogs_cache['blogs']:
        return '<div class="loading">Loading games...</div>'
    
    html_parts = []
    for blog in blogs_cache['blogs']:
        html_parts.append(f'''
        <div class="game-card">
            <div class="matchup-header">
                <div class="matchup-title">🏟️ {blog['away_team']} @ {blog['home_team']}</div>
            </div>
            <div class="section">
                <h3 class="section-title">⚾ Game Analysis</h3>
                <p>Detailed analysis coming soon for this matchup!</p>
            </div>
        </div>
        ''')
    
    return ''.join(html_parts)

@app.route('/')
def index():
    """Main page showing all game blogs"""
    try:
        # Read the HTML template
        with open('index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Replace placeholders
        current_date = datetime.now().strftime('%B %d, %Y')
        games_count = len(blogs_cache['blogs'])
        umpires_count = 0  # Count umpires when implemented
        matchups_count = games_count * 2  # Rough estimate
        
        last_updated = blogs_cache['last_updated'].strftime('%I:%M %p ET') if blogs_cache['last_updated'] else 'Never'
        
        html_content = html_content.replace('CURRENT_DATE_PLACEHOLDER', current_date)
        html_content = html_content.replace('GAMES_COUNT_PLACEHOLDER', str(games_count))
        html_content = html_content.replace('UMPIRES_COUNT_PLACEHOLDER', str(umpires_count))
        html_content = html_content.replace('MATCHUPS_COUNT_PLACEHOLDER', str(matchups_count))
        html_content = html_content.replace('LAST_UPDATED_PLACEHOLDER', last_updated)
        html_content = html_content.replace('GAMES_CONTENT_PLACEHOLDER', generate_games_html())
        
        return html_content
        
    except Exception as e:
        return f'''
        <html><body style="font-family: Arial; padding: 50px; text-align: center;">
        <h1>MLB Daily Game Analysis</h1>
        <p>Loading data...</p>
        <p style="color: red;">Error: {e}</p>
        </body></html>
        '''

@app.route('/api/blogs')
def api_blogs():
    """API endpoint returning JSON of all blogs"""
    return {
        'blogs': blogs_cache['blogs'],
        'last_updated': blogs_cache['last_updated'].isoformat() if blogs_cache['last_updated'] else None,
        'total_games': len(blogs_cache['blogs'])
    }

@app.route('/api/refresh')
def api_refresh():
    """API endpoint to manually refresh all blogs"""
    generate_all_blogs()
    return {'status': 'success', 'message': 'Blogs refreshed', 'total_games': len(blogs_cache['blogs'])}

@app.route('/health')
def health():
    """Health check endpoint for Render"""
    return {'status': 'healthy', 'timestamp': datetime.now().isoformat()}

# Background scheduler
def run_scheduler():
    """Run the background scheduler"""
    schedule.every().day.at("11:00").do(generate_all_blogs)  # 6 AM ET
    schedule.every().hour.do(generate_all_blogs)  # For now, refresh hourly
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# Initialize on startup
def initialize_app():
    """Initialize the app with initial data"""
    print("🚀 Initializing MLB Blog Service")
    generate_all_blogs()
    
    # Start background scheduler in a separate thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print("✅ Background scheduler started")

if __name__ == '__main__':
    initialize_app()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
