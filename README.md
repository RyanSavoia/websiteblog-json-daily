# MLB Daily Game Analysis

A comprehensive web service that generates daily MLB game analysis blogs using advanced pitch-specific data and umpire tendencies.

## 🎯 Features

- **Daily Game Analysis**: Complete breakdowns for every MLB game
- **Pitcher Arsenal Analysis**: Detailed pitch mix, usage rates, and velocities
- **Lineup vs Arsenal Projections**: How each batter performs against opposing pitcher's specific arsenal
- **Umpire Impact Analysis**: Historical tendencies and game impact predictions
- **Automatic Updates**: 
  - Full refresh daily at 6 AM ET
  - Umpire data updates every hour
- **Responsive Design**: Works perfectly on desktop and mobile
- **API Access**: JSON endpoints for data integration

## 🚀 Live Demo

Visit the live service: [Your Render URL]

## 📊 What's Included

### Game Analysis
- **Pitching Matchup**: Complete arsenal breakdowns with pitch types, usage rates, and speeds
- **Individual Batter Analysis**: Season stats vs arsenal-adjusted expected performance
- **Team-Level Insights**: Lineup advantages and disadvantages
- **Key Takeaways**: Data-driven insights for fantasy and betting

### Umpire Impact
- **Historical Multipliers**: How each umpire affects game outcomes
- **Percentage Changes**: Clear boost/decrease formatting (e.g., "25% boost", "16% decrease")
- **Strategic Insights**: What to expect based on umpire tendencies

## 🔧 Technical Details

### Data Sources
- **MLB Data**: `mlb-matchup-api-savant.onrender.com/latest`
- **Umpire Data**: `umpire-json-api.onrender.com`

### Update Schedule
- **6:00 AM ET**: Full blog regeneration with fresh MLB data
- **Every Hour**: Umpire assignment updates
- **Manual**: API endpoints for immediate refreshes

### Reliability Filtering
Only includes batter matchups with `MEDIUM` or `HIGH` reliability scores to ensure data quality.

## 🌐 API Endpoints

- `GET /` - Main web interface
- `GET /api/blogs` - JSON data for all game blogs
- `GET /api/refresh` - Manually refresh all blogs
- `GET /api/refresh-umpires` - Update only umpire data
- `GET /health` - Service health check

## 🏗️ Deployment

### Render Deployment
1. Fork this repository
2. Connect to Render as a Web Service
3. Use these settings:
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
4. Deploy!

### Local Development
```bash
# Clone the repository
git clone [your-repo-url]
cd mlb-blog-service

# Install dependencies
pip install -r requirements.txt

# Run locally
python app.py
```

Visit `http://localhost:5000` to see the local version.

## 📁 Project Structure

```
mlb-blog-service/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── render.yaml           # Render deployment config
├── templates/
│   └── index.html        # Web interface template
├── README.md             # This file
├── .gitignore           # Git ignore rules
└── Procfile             # Alternative deployment config
```

## 🎨 Features Showcase

### Responsive Design
- Modern gradient backgrounds
- Card-based game layouts
- Mobile-optimized tables
- Hover effects and animations

### Data Visualization
- Color-coded performance indicators
- Organized arsenal displays
- Clear statistical comparisons
- Insightful team summaries

### Real-Time Updates
- Automatic background scheduling
- Live umpire assignment tracking
- Manual refresh capabilities
- Status indicators for last updates

## 🔄 Data Flow

1. **Morning**: Service fetches fresh MLB game data and generates initial blogs
2. **Hourly**: Umpire assignments are updated as they become available
3. **Real-Time**: Web interface serves cached data for fast loading
4. **Manual**: API endpoints allow immediate data refresh when needed

## 🎯 Use Cases

- **Fantasy Baseball**: Lineup optimization and pitcher streaming
- **Sports Betting**: Data-driven insights for props and totals
- **General Fans**: Deep understanding of daily matchups
- **Data Analysis**: JSON API for further processing

## 🤝 Contributing

This is a personal project, but suggestions and improvements are welcome!

## 📝 License

MIT License - Feel free to use and modify as needed.

## 🙏 Acknowledgments

- MLB data sourced from Baseball Savant
- Umpire data from comprehensive historical analysis
- Built with Flask, modern CSS, and lots of ⚾ love

---

*Last updated: June 2025*
