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

def format_pitcher_profile(pitcher_data):
    """Create pitcher profile description"""
    arsenal = pitcher_data.get('arsenal', {})
    
    if not arsenal:
        return "Mixed arsenal"
    
    sorted_pitches = sorted(arsenal.items(), key=lambda x: x[1]['usage_rate'], reverse=True)
    
    fastballs = ['Four-Seam', 'Sinker', 'Cutter']
    breaking = ['Slider', 'Curveball', 'Sweeper']
    offspeed = ['Changeup', 'Splitter']
    
    pitch_types = []
    for pitch_type, pitch_data in sorted_pitches[:2]:
        pitch_name = pitch_data.get('name', pitch_type)
        if pitch_name in fastballs:
            pitch_types.append('fastball')
        elif pitch_name in breaking:
            pitch_types.append('breaking')
        elif pitch_name in offspeed:
            pitch_types.append('offspeed')
    
    if 'breaking' in pitch_types:
        if pitch_types.count('breaking') > 1 or pitch_types[0] == 'breaking':
            return "Breaking-heavy mix designed to miss bats and induce weak contact."
        else:
            return "Balanced mix with emphasis on breaking balls to keep hitters off balance."
    elif 'fastball' in pitch_types:
        if pitch_types.count('fastball') > 1 or pitch_types[0] == 'fastball':
            return "Fastball-heavy approach with emphasis on velocity and command in the zone."
        else:
            return "Power pitcher who attacks the zone with quality fastballs."
    elif 'offspeed' in pitch_types:
        return "Offspeed-heavy approach designed to change eye levels and disrupt timing."
    else:
        return "Mixed arsenal with diverse pitch types to keep hitters guessing."

def calculate_lineup_stats(key_matchups, pitcher_name):
    """Calculate lineup performance vs specific pitcher"""
    pitcher_matchups = [m for m in key_matchups if m.get('vs_pitcher') == pitcher_name]
    reliable_matchups = [m for m in pitcher_matchups if m.get('reliability', '').upper() in ['MEDIUM', 'HIGH']]
    
    if not reliable_matchups:
        return {
            'season_ba': 0.250,
            'season_k_pct': 22.5,
            'arsenal_ba': 0.250,
            'arsenal_k_pct': 22.5,
            'ba_diff': 0.0,
            'k_diff': 0.0,
            'batters': []
        }
    
    season_bas = []
    season_k_pcts = []
    arsenal_bas = []
    arsenal_k_pcts = []
    batters = []
    
    for matchup in reliable_matchups:
        baseline = matchup.get('baseline_stats', {})
        if baseline:
            season_ba = baseline.get('season_avg', 0.250)
            season_k = baseline.get('season_k_pct', 22.5)
            season_bas.append(season_ba)
            season_k_pcts.append(season_k)
        else:
            season_ba = 0.250
            season_k = 22.5
        
        arsenal_ba = matchup.get('weighted_est_ba', 0.250)
        arsenal_k = matchup.get('weighted_k_rate', 22.5)
        arsenal_bas.append(arsenal_ba)
        arsenal_k_pcts.append(arsenal_k)
        
        batter = matchup.get('batter', 'Unknown')
        batter_display = batter.replace(', ', ' ').split()
        batter_display = f"{batter_display[1]} {batter_display[0]}" if len(batter_display) >= 2 else batter
        
        batters.append({
            'name': batter_display,
            'season_ba': season_ba,
            'arsenal_ba': arsenal_ba,
            'season_k': season_k,
            'arsenal_k': arsenal_k
        })
    
    avg_season_ba = sum(season_bas) / len(season_bas) if season_bas else 0.250
    avg_season_k = sum(season_k_pcts) / len(season_k_pcts) if season_k_pcts else 22.5
    avg_arsenal_ba = sum(arsenal_bas) / len(arsenal_bas)
    avg_arsenal_k = sum(arsenal_k_pcts) / len(arsenal_k_pcts)
    
    return {
        'season_ba': avg_season_ba,
        'season_k_pct': avg_season_k,
        'arsenal_ba': avg_arsenal_ba,
        'arsenal_k_pct': avg_arsenal_k,
        'ba_diff': avg_arsenal_ba - avg_season_ba,
        'k_diff': avg_arsenal_k - avg_season_k,
        'batters': batters
    }

def generate_game_blog_data(game_report, umpires):
    """Generate structured blog data for a single game"""
    matchup = game_report.get('matchup', 'Unknown')
    away_team, home_team = matchup.split(' @ ') if ' @ ' in matchup else ('Away', 'Home')
    
    # Get pitcher data
    away_pitcher_data = game_report['pitchers']['away']
    home_pitcher_data = game_report['pitchers']['home']
    
    # Format pitcher names
    away_pitcher_name = away_pitcher_data.get('name', 'Unknown').replace(', ', ' ').split()
    away_pitcher_display = f"{away_pitcher_name[1]} {away_pitcher_name[0]}" if len(away_pitcher_name) >= 2 else away_pitcher_data.get('name', 'Unknown')
    
    home_pitcher_name = home_pitcher_data.get('name', 'Unknown').replace(', ', ' ').split()
    home_pitcher_display = f"{home_pitcher_name[1]} {home_pitcher_name[0]}" if len(home_pitcher_name) >= 2 else home_pitcher_data.get('name', 'Unknown')
    
    # Get lineup stats
    key_matchups = game_report['key_matchups']
    away_lineup_stats = calculate_lineup_stats(key_matchups, home_pitcher_data['name'])
    home_lineup_stats = calculate_lineup_stats(key_matchups, away_pitcher_data['name'])
    
    # Find umpire
    umpire = find_game_umpire(umpires, matchup)
    
    # Format arsenal data
    away_arsenal = []
    if away_pitcher_data.get('arsenal'):
        sorted_pitches = sorted(away_pitcher_data['arsenal'].items(), key=lambda x: x[1]['usage_rate'], reverse=True)
        away_arsenal = [
            {
                'name': p[1]['name'],
                'usage': p[1]['usage_rate'] * 100,
                'speed': p[1]['avg_speed']
            } for p in sorted_pitches
        ]
    
    home_arsenal = []
    if home_pitcher_data.get('arsenal'):
        sorted_pitches = sorted(home_pitcher_data['arsenal'].items(), key=lambda x: x[1]['usage_rate'], reverse=True)
        home_arsenal = [
            {
                'name': p[1]['name'],
                'usage': p[1]['usage_rate'] * 100,
                'speed': p[1]['avg_speed']
            } for p in sorted_pitches
        ]
    
    # Format umpire data
    umpire_data = None
    if umpire:
        umpire_data = {
            'name': umpire['umpire'],
            'k_boost': format_boost_percentage(umpire['k_boost']),
            'bb_boost': format_boost_percentage(umpire['bb_boost']),
            'ba_boost': format_boost_percentage(umpire['ba_boost']),
            'obp_boost': format_boost_percentage(umpire['obp_boost']),
            'slg_boost': format_boost_percentage(umpire['slg_boost']),
            'k_multiplier': float(umpire['k_boost'].replace('x', '')),
            'bb_multiplier': float(umpire['bb_boost'].replace('x', ''))
        }
    
    return {
        'matchup': matchup,
        'away_team': away_team,
        'home_team': home_team,
        'away_pitcher': {
            'name': away_pitcher_display,
            'profile': format_pitcher_profile(away_pitcher_data),
            'arsenal': away_arsenal
        },
        'home_pitcher': {
            'name': home_pitcher_display,
            'profile': format_pitcher_profile(home_pitcher_data),
            'arsenal': home_arsenal
        },
        'away_lineup': away_lineup_stats,
        'home_lineup': home_lineup_stats,
        'umpire': umpire_data
    }

def generate_all_blogs():
    """Generate all game blogs and update cache"""
    global blogs_cache
    
    print(f"🚀 Generating blogs at {datetime.now()}")
    
    mlb_reports = get_mlb_data()
    umpires = get_umpire_data()
    
    if not mlb_reports:
        print("❌ No MLB data available")
        return
    
    new_blogs = []
    
    for game_report in mlb_reports:
        try:
            blog_data = generate_game_blog_data(game_report, umpires)
            new_blogs.append(blog_data)
        except Exception as e:
            print(f"❌ Error generating blog: {e}")
            continue
    
    # Update cache
    blogs_cache['blogs'] = new_blogs
    blogs_cache['last_updated'] = datetime.now()
    blogs_cache['umpires_last_updated'] = datetime.now()
    
    print(f"✅ Generated {len(new_blogs)} blogs")

def generate_games_html():
    """Generate HTML for all games"""
    if not blogs_cache['blogs']:
        return '<div class="loading">Loading games...</div>'
    
    html_parts = []
    for blog in blogs_cache['blogs']:
        
        # Pitching section
        pitching_html = f'''
        <div class="section">
            <h3 class="section-title">⚾ Pitching Matchup</h3>
            <div class="pitchers-grid">
                <div class="pitcher-card">
                    <div class="pitcher-name">{blog['away_pitcher']['name']} ({blog['away_team']})</div>
                    <div class="pitcher-profile">{blog['away_pitcher']['profile']}</div>
                    <ul class="arsenal-list">
        '''
        
        for pitch in blog['away_pitcher']['arsenal']:
            pitching_html += f'<li>{pitch["name"]}: {pitch["usage"]:.0f}%, {pitch["speed"]:.1f} mph</li>'
        
        pitching_html += f'''
                    </ul>
                </div>
                <div class="pitcher-card">
                    <div class="pitcher-name">{blog['home_pitcher']['name']} ({blog['home_team']})</div>
                    <div class="pitcher-profile">{blog['home_pitcher']['profile']}</div>
                    <ul class="arsenal-list">
        '''
        
        for pitch in blog['home_pitcher']['arsenal']:
            pitching_html += f'<li>{pitch["name"]}: {pitch["usage"]:.0f}%, {pitch["speed"]:.1f} mph</li>'
        
        pitching_html += '''
                    </ul>
                </div>
            </div>
        </div>
        '''
        
        # Lineup analysis section
        lineup_html = f'''
        <div class="section">
            <h3 class="section-title">🧮 Lineup Analysis vs Opposing Arsenal</h3>
            <div class="lineup-section">
                <div class="lineup-title">{blog['away_team']} Batters vs {blog['home_pitcher']['name']}'s Arsenal</div>
        '''
        
        if blog['away_lineup']['batters']:
            lineup_html += '''
                <table class="lineup-table">
                    <thead>
                        <tr>
                            <th>Batter</th>
                            <th>Season BA</th>
                            <th>xBA vs Arsenal</th>
                            <th>Season K%</th>
                            <th>K% vs Arsenal</th>
                        </tr>
                    </thead>
                    <tbody>
            '''
            
            for batter in blog['away_lineup']['batters']:
                positive_ba = "positive" if batter['arsenal_ba'] > batter['season_ba'] else "negative"
                positive_k = "positive" if batter['arsenal_k'] < batter['season_k'] else "negative"
                
                lineup_html += f'''
                        <tr>
                            <td><strong>{batter['name']}</strong></td>
                            <td>{batter['season_ba']:.3f}</td>
                            <td class="{positive_ba}">{batter['arsenal_ba']:.3f}</td>
                            <td>{batter['season_k']:.1f}%</td>
                            <td class="{positive_k}">{batter['arsenal_k']:.1f}%</td>
                        </tr>
                '''
            
            lineup_html += '</tbody></table>'
            
            # Team summary
            ba_diff_class = "positive" if blog['away_lineup']['ba_diff'] > 0 else "negative"
            k_diff_class = "positive" if blog['away_lineup']['k_diff'] < 0 else "negative"
            
            lineup_html += f'''
                <div class="lineup-summary">
                    <ul>
                        <li><strong>Avg Season BA:</strong> {blog['away_lineup']['season_ba']:.3f}</li>
                        <li><strong>Arsenal-adjusted xBA:</strong> {blog['away_lineup']['arsenal_ba']:.3f} 
                            <span class="{ba_diff_class}">({blog['away_lineup']['ba_diff']*1000:+.0f} pts)</span>
                        </li>
                        <li><strong>Avg Season K%:</strong> {blog['away_lineup']['season_k_pct']:.1f}%</li>
                        <li><strong>Arsenal-adjusted K%:</strong> {blog['away_lineup']['arsenal_k_pct']:.1f}% 
                            <span class="{k_diff_class}">({blog['away_lineup']['k_diff']:+.1f}%)</span>
                        </li>
                    </ul>
            '''
            
            if abs(blog['away_lineup']['ba_diff']) > 0.015:
                impact = "favors the offense" if blog['away_lineup']['ba_diff'] > 0 else "favors the pitcher"
                lineup_html += f'''
                    <div class="insight">
                        <strong>Key Insight:</strong> The {abs(blog['away_lineup']['ba_diff'])*1000:.0f}-point difference 
                        {impact} in this matchup.
                    </div>
                '''
            
            lineup_html += '</div>'
        else:
            lineup_html += '<p><em>Insufficient reliable data for lineup analysis.</em></p>'
        
        lineup_html += '</div>'
        
        # Home lineup (similar structure)
        lineup_html += f'''
            <div class="lineup-section">
                <div class="lineup-title">{blog['home_team']} Batters vs {blog['away_pitcher']['name']}'s Arsenal</div>
        '''
        
        if blog['home_lineup']['batters']:
            lineup_html += '''
                <table class="lineup-table">
                    <thead>
                        <tr>
                            <th>Batter</th>
                            <th>Season BA</th>
                            <th>xBA vs Arsenal</th>
                            <th>Season K%</th>
                            <th>K% vs Arsenal</th>
                        </tr>
                    </thead>
                    <tbody>
            '''
            
            for batter in blog['home_lineup']['batters']:
                positive_ba = "positive" if batter['arsenal_ba'] > batter['season_ba'] else "negative"
                positive_k = "positive" if batter['arsenal_k'] < batter['season_k'] else "negative"
                
                lineup_html += f'''
                        <tr>
                            <td><strong>{batter['name']}</strong></td>
                            <td>{batter['season_ba']:.3f}</td>
                            <td class="{positive_ba}">{batter['arsenal_ba']:.3f}</td>
                            <td>{batter['season_k']:.1f}%</td>
                            <td class="{positive_k}">{batter['arsenal_k']:.1f}%</td>
                        </tr>
                '''
            
            lineup_html += '</tbody></table>'
            
            # Team summary
            ba_diff_class = "positive" if blog['home_lineup']['ba_diff'] > 0 else "negative"
            k_diff_class = "positive" if blog['home_lineup']['k_diff'] < 0 else "negative"
            
            lineup_html += f'''
                <div class="lineup-summary">
                    <ul>
                        <li><strong>Avg Season BA:</strong> {blog['home_lineup']['season_ba']:.3f}</li>
                        <li><strong>Arsenal-adjusted xBA:</strong> {blog['home_lineup']['arsenal_ba']:.3f} 
                            <span class="{ba_diff_class}">({blog['home_lineup']['ba_diff']*1000:+.0f} pts)</span>
                        </li>
                        <li><strong>Avg Season K%:</strong> {blog['home_lineup']['season_k_pct']:.1f}%</li>
                        <li><strong>Arsenal-adjusted K%:</strong> {blog['home_lineup']['arsenal_k_pct']:.1f}% 
                            <span class="{k_diff_class}">({blog['home_lineup']['k_diff']:+.1f}%)</span>
                        </li>
                    </ul>
            '''
            
            if abs(blog['home_lineup']['ba_diff']) > 0.015:
                impact = "favors the offense" if blog['home_lineup']['ba_diff'] > 0 else "favors the pitcher"
                lineup_html += f'''
                    <div class="insight">
                        <strong>Key Insight:</strong> The {abs(blog['home_lineup']['ba_diff'])*1000:.0f}-point difference 
                        {impact} in this matchup.
                    </div>
                '''
            
            lineup_html += '</div>'
        else:
            lineup_html += '<p><em>Insufficient reliable data for lineup analysis.</em></p>'
        
        lineup_html += '</div></div>'
        
        # Umpire section
        umpire_html = '''
        <div class="umpire-section">
            <h3 class="section-title">👨‍⚖️ Umpire Impact</h3>
        '''
        
        if blog['umpire']:
            umpire_html += f'''
            <div class="umpire-name">{blog['umpire']['name']}</div>
            <p>Today's plate umpire, <strong>{blog['umpire']['name']}</strong>, is a known variable — especially when it comes to strikeouts and walks.</p>
            
            <table class="umpire-table">
                <thead>
                    <tr>
                        <th>Stat</th>
                        <th>Historical Impact</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Strikeouts</td>
                        <td class="{'boost' if 'boost' in blog['umpire']['k_boost'] else 'decrease'}">
                            {blog['umpire']['k_boost']}
                        </td>
                    </tr>
                    <tr>
                        <td>Walks</td>
                        <td class="{'boost' if 'boost' in blog['umpire']['bb_boost'] else 'decrease'}">
                            {blog['umpire']['bb_boost']}
                        </td>
                    </tr>
                    <tr>
                        <td>Batting Average</td>
                        <td class="{'boost' if 'boost' in blog['umpire']['ba_boost'] else 'decrease'}">
                            {blog['umpire']['ba_boost']}
                        </td>
                    </tr>
                    <tr>
                        <td>OBP</td>
                        <td class="{'boost' if 'boost' in blog['umpire']['obp_boost'] else 'decrease'}">
                            {blog['umpire']['obp_boost']}
                        </td>
                    </tr>
                    <tr>
                        <td>SLG</td>
                        <td class="{'boost' if 'boost' in blog['umpire']['slg_boost'] else 'decrease'}">
                            {blog['umpire']['slg_boost']}
                        </td>
                    </tr>
                </tbody>
            </table>
            
            <div class="umpire-analysis">
            '''
            
            if blog['umpire']['k_multiplier'] > 1.1:
                umpire_html += "This umpire has historically favored pitchers, boosting strikeout rates significantly. That's something to watch, especially for totals or K prop bets."
            elif blog['umpire']['k_multiplier'] < 0.9:
                umpire_html += "This umpire tends to have a tighter strike zone, leading to fewer strikeouts and more contact. Good for over bets on hits and runs."
            else:
                umpire_html += "This umpire maintains fairly neutral tendencies, close to league average across most categories."
            
            if blog['umpire']['bb_multiplier'] > 1.1:
                umpire_html += " Expect more walks than usual due to this umpire's historically wider zone."
            elif blog['umpire']['bb_multiplier'] < 0.9:
                umpire_html += " This umpire tends to squeeze the zone, leading to fewer walks and more aggressive swinging."
            
            umpire_html += '</div>'
        else:
            umpire_html += '''
            <div class="umpire-name">TBA</div>
            <p>Umpire assignment not yet available for this game.</p>
            <p><em>Note: Umpire data will be updated when assignments are confirmed closer to game time.</em></p>
            '''
        
        umpire_html += '</div>'
        
        # Combine all sections
        html_parts.append(f'''
        <div class="game-card">
            <div class="matchup-header">
                <div class="matchup-title">🏟️ {blog['away_team']} @ {blog['home_team']}</div>
            </div>
            {pitching_html}
            {lineup_html}
            {umpire_html}
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
        
        # Count umpires assigned
        umpires_count = sum(1 for blog in blogs_cache['blogs'] if blog.get('umpire'))
        
        # Count total matchups (batters)
        matchups_count = 0
        for blog in blogs_cache['blogs']:
            matchups_count += len(blog.get('away_lineup', {}).get('batters', []))
            matchups_count += len(blog.get('home_lineup', {}).get('batters', []))
        
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
    schedule.every().hour.do(generate_all_blogs)  # Refresh hourly for umpire updates
    
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
