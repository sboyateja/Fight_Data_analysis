import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ----------------------------
# Page configuration (must be first)
st.set_page_config(page_title="Air Passenger Traffic Map", layout="wide")

# ----------------------------
# Load and clean data
@st.cache_data
def load_data():
    df = pd.read_csv('Summary_By_Origin_Airport.csv', low_memory=False)
    airport_coords = pd.read_csv('airports_location.csv')
    fare = pd.read_csv('AverageFare_USA.csv')

    fare.columns = fare.columns.str.strip()
    fare.rename(columns={
        'Airport Code': 'Origin Airport Code',
        'Average Fare ($)': 'Avg Fare',
        'Inflation Adjusted Average Fare ($)': 'Adj Avg Fare'
    }, inplace=True)

    fare['Avg Fare'] = fare['Avg Fare'].astype(str).str.replace(r'[\$,]', '', regex=True)
    fare['Adj Avg Fare'] = fare['Adj Avg Fare'].astype(str).str.replace(r'[\$,]', '', regex=True)
    fare['Avg Fare'] = pd.to_numeric(fare['Avg Fare'], errors='coerce')
    fare['Adj Avg Fare'] = pd.to_numeric(fare['Adj Avg Fare'], errors='coerce')

    numeric_cols = ['Total Passengers', 'Domestic Passengers', 'Outbound International Passengers']
    for col in numeric_cols:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.replace(r'[,"]', '', regex=True)
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df['Year'] = pd.to_numeric(df['Year'].astype(str).str.extract(r'(\d{4})')[0], errors='coerce')
    df = df.dropna(subset=['Year'])
    df['Year'] = df['Year'].astype(int)

    df = df.merge(
        airport_coords[['code', 'latitude', 'longitude', 'state']],
        left_on='Origin Airport Code',
        right_on='code',
        how='left'
    ).dropna(subset=['latitude', 'longitude'])

    df = df.merge(
        fare[['Origin Airport Code', 'Year', 'Avg Fare']],
        on=['Origin Airport Code', 'Year'],
        how='left'
    )

    df['Avg Fare'] = df['Avg Fare'].fillna(100)

    # Aggregate annually
    annual_data = df.groupby(['Year', 'Origin City Name', 'state', 'latitude', 'longitude']).agg({
        'Total Passengers': 'sum',
        'Domestic Passengers': 'sum',
        'Outbound International Passengers': 'sum',
        'Avg Fare': 'mean'
    }).reset_index()

    return annual_data

annual_data = load_data()

# ----------------------------
# Sidebar controls
st.sidebar.title("Filters")

years = sorted(annual_data['Year'].unique())
selected_year = st.sidebar.selectbox("Select Year", ["All Years"] + years)

city_list = annual_data['Origin City Name'].unique()
selected_city = st.sidebar.selectbox("Select City (highlight)", ["None"] + sorted(city_list))

top_n = st.sidebar.selectbox("Show Top N Cities", [5, 10, 15, 20, 50, "All"])

# ----------------------------
# Filter data
if selected_year != "All Years":
    data = annual_data[annual_data['Year'] == selected_year].copy()
else:
    data = annual_data.groupby(['Origin City Name', 'state', 'latitude', 'longitude']).agg({
        'Total Passengers': 'sum',
        'Domestic Passengers': 'sum',
        'Outbound International Passengers': 'sum',
        'Avg Fare': 'mean'
    }).reset_index()

data = data.sort_values('Total Passengers', ascending=False)
data['Rank'] = data['Total Passengers'].rank(method='min', ascending=False).astype(int)

if top_n != "All":
    data = data.head(int(top_n))

data['hover_text'] = data.apply(
    lambda x: f"<b>#{x['Rank']} {x['Origin City Name']}, {x['state']}</b><br>"
              f"Total: {x['Total Passengers']:,.0f}<br>"
              f"Domestic: {x['Domestic Passengers']:,.0f}<br>"
              f"International: {x['Outbound International Passengers']:,.0f}<br>"
              f"Average Fare: ${x['Avg Fare']:,.2f}",
    axis=1
)

# ----------------------------
# Create map
fig = px.scatter_geo(
    data,
    lat='latitude',
    lon='longitude',
    size='Total Passengers',
    color='Total Passengers',
    hover_name='hover_text',
    scope='usa',
    projection='albers usa',
    title=f"Passenger Traffic by City {'in ' + str(selected_year) if selected_year != 'All Years' else '(All Years)'} {f'(Top {top_n})' if top_n != 'All' else ''}",
    size_max=30,
    color_continuous_scale=px.colors.sequential.Viridis
)

# Annotate top 50
for _, row in data.head(50).iterrows():
    fig.add_annotation(
        x=row['longitude'],
        y=row['latitude'],
        text=f"#{row['Rank']}",
        showarrow=False,
        font=dict(size=10, color='white'),
        yshift=10
    )

# Highlight selected city
if selected_city != "None":
    selected_data = data[data['Origin City Name'] == selected_city]
    if not selected_data.empty:
        fig.add_trace(go.Scattergeo(
            lon=selected_data['longitude'],
            lat=selected_data['latitude'],
            text=selected_data['hover_text'],
            marker=dict(
                size=25,
                color=selected_data['Total Passengers'],
                colorscale='Viridis',
                line=dict(width=3, color='white'),
                sizemode='area',
                sizeref=2.*max(data['Total Passengers'])/(30.**2),
                sizemin=4
            ),
            name=f"Selected: {selected_city}",
            hoverinfo='text',
            mode='markers'
        ))

fig.update_geos(
    showland=True,
    landcolor="rgb(240, 240, 240)",
    subunitcolor="rgb(217, 217, 217)"
)

fig.update_layout(
    margin={"r": 0, "t": 40, "l": 0, "b": 0},
    height=600
)

# ----------------------------
# Display in Streamlit
st.title("Air Passenger Traffic by City")
st.plotly_chart(fig, use_container_width=True)

st.markdown("""
- Use the sidebar to select a specific year and optionally highlight a city.
- Bubble size and color represent total passenger volume.
- The top 50 cities are labeled automatically.
""")
