import pandas as pd
import plotly.express as px
import streamlit as st

# Set full width layout
st.set_page_config(layout="wide")

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
        airport_coords[['code', 'latitude', 'longitude']],
        left_on='Origin Airport Code',
        right_on='code',
        how='left'
    ).dropna(subset=['latitude', 'longitude'])

    df = df.merge(
        fare[['Origin Airport Code', 'Year', 'Avg Fare']],
        on=['Origin Airport Code', 'Year'],
        how='left'
    )

    annual_data = df.groupby(['Year', 'Origin City Name', 'latitude', 'longitude']).agg({
        'Total Passengers': 'sum',
        'Domestic Passengers': 'sum',
        'Outbound International Passengers': 'sum',
        'Avg Fare': 'mean'
    }).reset_index()

    return df, annual_data

# Helper to parse "Top N"
def parse_topn(value):
    if isinstance(value, str) and value.startswith("Top"):
        return int(value.replace("Top", "").strip())
    return None

df, annual_data = load_data()

# Sidebar filters
st.sidebar.header("Filters")
year_options = ['All Years'] + sorted(df['Year'].unique().astype(str).tolist())
selected_year = st.sidebar.selectbox("Select Year", options=year_options)

topn_options = ['All Cities', "Top 5", "Top 10", "Top 15", "Top 20", "Top 50"]
selected_topn = st.sidebar.selectbox("Show Top N Cities", options=topn_options)

city_options = ['All Cities'] + sorted(df['Origin City Name'].unique())
selected_city = st.sidebar.selectbox("Filter by City", options=city_options)

# Map creation
def create_map(selected_year=None, top_n=None, selected_city=None):
    if selected_year:
        data = annual_data[annual_data['Year'] == int(selected_year)].copy()
    else:
        data = annual_data.groupby(['Origin City Name', 'latitude', 'longitude']).agg({
            'Total Passengers': 'sum',
            'Domestic Passengers': 'sum',
            'Outbound International Passengers': 'sum',
            'Avg Fare': 'mean'
        }).reset_index()

    if selected_city and selected_city != 'All Cities':
        data = data[data['Origin City Name'] == selected_city]
    elif top_n:
        data = data.sort_values('Total Passengers', ascending=False).head(top_n)
    else:
        data = data.sort_values('Total Passengers', ascending=False)

    data['Rank'] = data['Total Passengers'].rank(method='min', ascending=False).astype(int)
    data['Avg Fare'] = data['Avg Fare'].fillna(100)

    data['hover_text'] = data.apply(
        lambda x: f"<b>#{x['Rank']} {x['Origin City Name']}</b><br>"
                  f"Total: {x['Total Passengers']:,.0f}<br>"
                  f"Domestic: {x['Domestic Passengers']:,.0f}<br>"
                  f"International: {x['Outbound International Passengers']:,.0f}<br>"
                  f"Average Fare: ${x['Avg Fare']:,.2f}",
        axis=1
    )

    fig = px.scatter_geo(
        data,
        lat='latitude',
        lon='longitude',
        size='Total Passengers',
        color='Total Passengers',
        hover_name='hover_text',
        scope='usa',
        projection='albers usa',
        size_max=30,
        color_continuous_scale=px.colors.sequential.Viridis
    )

    max_annotations = min(len(data), 50)
    for _, row in data.head(max_annotations).iterrows():
        fig.add_annotation(
            x=row['longitude'],
            y=row['latitude'],
            text=f"#{row['Rank']}",
            showarrow=False,
            font=dict(size=10, color='white'),
            yshift=10
        )

    fig.update_geos(
        showland=True,
        landcolor="rgb(240, 240, 240)",
        subunitcolor="rgb(217, 217, 217)"
    )

    fig.update_layout(
        margin={"r": 0, "t": 20, "l": 0, "b": 0},
        height=650,
        coloraxis_colorbar=dict(title="Total Passengers")
    )

    return fig, data

# Main layout
st.markdown("<h1 style='margin-bottom: -10px;'>Passengers Travelling by City in the Flights</h1>", unsafe_allow_html=True)
st.caption(f"Passengers Travelling by City {'in ' + str(selected_year) if selected_year != 'All Years' else '(All Years)'}")

# Total passengers display
if selected_year != 'All Years':
    total_passengers_display = int(df[df['Year'] == int(selected_year)]['Total Passengers'].sum())
else:
    total_passengers_display = int(df['Total Passengers'].sum())

st.markdown(
    f"<h2 style='text-align:center; color:#2ca02c;'>🛫 Total Passengers: {total_passengers_display:,.0f}</h2>",
    unsafe_allow_html=True
)

# Map generation
with st.spinner("Generating map..."):
    year_val = None if selected_year == 'All Years' else selected_year
    topn_val = parse_topn(selected_topn) if selected_city == 'All Cities' else None
    fig_map, filtered_data = create_map(year_val, topn_val, selected_city)
    st.plotly_chart(fig_map, use_container_width=True)

# Info section
st.markdown("""
- Use the sidebar to filter by year, city, or number of top cities.
- Bubble size represents total passenger volume.
- It shows top cities in order of passenger traffic.
""")

# Bar chart: Total Passengers by City
st.markdown("### 📊 Total Passengers by City")
bar_data = filtered_data.sort_values('Total Passengers', ascending=False)
fig_bar = px.bar(
    bar_data,
    x='Origin City Name',
    y='Total Passengers',
    color='Total Passengers',
    color_continuous_scale='Viridis',
    title='Total Passengers by City',
    labels={'Total Passengers': 'Passengers', 'Origin City Name': 'City'},
)
fig_bar.update_layout(xaxis_tickangle=-45, height=500, margin=dict(t=50, b=150))
st.plotly_chart(fig_bar, use_container_width=True)

# Li chart: Average Fare by Year for Selected Cities
st.markdown("### 💰 Average Fare by Year and City")

# Determine which cities to plot
if selected_city != 'All Cities':
    cities = [selected_city]
elif topn_val:
    cities = filtered_data['Origin City Name'].tolist()
else:
    top5_overall = annual_data.groupby('Origin City Name')['Total Passengers'].sum() \
                              .nlargest(5).index.tolist()
    cities = top5_overall

fare_trend = annual_data[annual_data['Origin City Name'].isin(cities)]

fig_fare = px.line(
    fare_trend,
    x='Year',
    y='Avg Fare',
    color='Origin City Name',
    markers=True,
    title='Average Fare by Year for Selected Cities',
    labels={'Avg Fare': 'Average Fare ($)', 'Year': 'Year'}
)
fig_fare.update_layout(height=500, margin=dict(t=50, b=50))
st.plotly_chart(fig_fare, use_container_width=True)
