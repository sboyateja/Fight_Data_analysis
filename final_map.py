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

    airport_coords.columns = airport_coords.columns.str.strip()
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

    df['Origin City Name'] = df['Origin City Name'].str.strip()

    annual_data = df.groupby(['Year', 'Origin City Name', 'state', 'latitude', 'longitude']).agg({
        'Total Passengers': 'sum',
        'Domestic Passengers': 'sum',
        'Outbound International Passengers': 'sum',
        'Avg Fare': 'mean'
    }).reset_index()

    state_agg = df.groupby(['Year', 'state']).agg({'Total Passengers': 'sum'}).reset_index()

    return df, annual_data, state_agg, airport_coords

# Helper to parse "Top N"
def parse_topn(value):
    if isinstance(value, str) and value.startswith("Top"):
        return int(value.replace("Top", "").strip())
    return None

df, annual_data, state_agg, airport_coords = load_data()

# Sidebar filters
st.sidebar.header("Filters")
year_options = ['All Years'] + sorted(df['Year'].unique().astype(str).tolist())
selected_year = st.sidebar.selectbox("Select Year", options=year_options)
selected_state = st.sidebar.selectbox("Filter by State", options=['All States'] + sorted(airport_coords['state'].dropna().unique()))
topn_options = ['All Cities', "Top 5", "Top 10", "Top 15", "Top 20", "Top 50"]
selected_topn = st.sidebar.selectbox("Show Top N Cities", options=topn_options)

# Map creation
def create_map(selected_year=None, top_n=None, selected_state=None):
    if selected_year:
        data = annual_data[annual_data['Year'] == int(selected_year)].copy()
    else:
        data = annual_data.groupby(['Origin City Name', 'state', 'latitude', 'longitude']).agg({
            'Total Passengers': 'sum',
            'Domestic Passengers': 'sum',
            'Outbound International Passengers': 'sum',
            'Avg Fare': 'mean'
        }).reset_index()

    if selected_state and selected_state != 'All States':
        data = data[data['state'] == selected_state]

    data = data.sort_values('Total Passengers', ascending=False)
    data['Rank'] = data['Total Passengers'].rank(method='min', ascending=False).astype(int)

    if top_n:
        # Always include key cities if they exist
        must_include_cities = ['Atlanta', 'Chicago', 'Los Angeles']
        top_data = data.head(top_n)
        for city in must_include_cities:
            city_row = data[data['Origin City Name'].str.contains(city, case=False, na=False)]
            if not city_row.empty:
                top_data = pd.concat([top_data, city_row]).drop_duplicates()
        data = top_data

    data['Avg Fare'] = data['Avg Fare'].fillna(100)

    data['hover_text'] = data.apply(
        lambda x: f"<b>#{x['Rank']} {x['Origin City Name']}</b><br>"
                  f"State: {x['state']}<br>"
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

    fig.update_geos(showland=True, landcolor="rgb(240, 240, 240)", subunitcolor="rgb(217, 217, 217)")
    fig.update_layout(
        margin={"r": 0, "t": 20, "l": 0, "b": 0},
        height=650,
        coloraxis_colorbar=dict(title="Total Passengers")
    )

    return fig

# Main layout
st.markdown("<h1 style='margin-bottom: -30px;'>Air Passenger Traffic by City</h1>", unsafe_allow_html=True)
st.caption(f"Passenger Traffic {'in ' + str(selected_year) if selected_year != 'All Years' else '(All Years)'}")

with st.spinner("Generating map..."):
    year_val = None if selected_year == 'All Years' else selected_year
    topn_val = parse_topn(selected_topn)
    fig = create_map(year_val, topn_val, selected_state)
    st.plotly_chart(fig, use_container_width=True)

# State totals chart
st.subheader("Total Passengers by State")
if selected_year == 'All Years':
    state_plot_data = state_agg.groupby('state')['Total Passengers'].sum().sort_values(ascending=False).reset_index()
else:
    state_plot_data = state_agg[state_agg['Year'] == int(selected_year)].sort_values('Total Passengers', ascending=False)

bar_fig = px.bar(
    state_plot_data,
    x='state',
    y='Total Passengers',
    labels={'Total Passengers': 'Total Passengers'},
    title=f"Total Passengers by State in {selected_year}" if selected_year != 'All Years' else "Total Passengers by State (All Years)",
    color='Total Passengers'
)
bar_fig.update_layout(xaxis_tickangle=-45)
st.plotly_chart(bar_fig, use_container_width=True)

# Info
st.markdown("""
- Use the sidebar to filter by year, state, and number of top cities.
- Bubble size represents total passenger volume.
- Top cities are labeled based on volume.
- Atlanta, Chicago, and Los Angeles are always shown on the map if available.
""")
