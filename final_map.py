import streamlit as st
st.set_page_config(page_title="Air Passenger Traffic Map", layout="wide")

import pandas as pd
import plotly.express as px

# 1. Load and clean data
@st.cache_data
def load_and_prepare_data():
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

    annual_data = df.groupby(['Year', 'Origin City Name', 'state', 'latitude', 'longitude']).agg({
        'Total Passengers': 'sum',
        'Domestic Passengers': 'sum',
        'Outbound International Passengers': 'sum',
        'Avg Fare': 'mean'
    }).reset_index()

    return df, annual_data

df, annual_data = load_and_prepare_data()

# 2. Map creation
def create_map(selected_year=None, top_n=None):
    if selected_year:
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

    if top_n:
        data = data.head(top_n)

    data['Avg Fare'] = data['Avg Fare'].fillna(100)

    data['hover_text'] = data.apply(
        lambda x: f"<b>#{x['Rank']} {x['Origin City Name']}, {x['state']}</b><br>"
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
        title=f"Passenger Traffic by City {'in ' + str(selected_year) if selected_year else '(All Years)'} {f'(Top {top_n})' if top_n else ''}",
        size_max=30,
        color_continuous_scale=px.colors.sequential.Viridis
    )

    max_annotations = 50 if top_n is None else min(top_n, 50)
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
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        height=600
    )

    return fig

# 3. Streamlit UI
st.title("✈️ Air Passenger Traffic by City")
st.markdown("Explore U.S. passenger traffic trends across cities and years.")

col1, col2 = st.columns(2)

with col1:
    year_option = st.selectbox(
        "Select Year:",
        options=["All Years"] + sorted(df['Year'].unique().astype(str).tolist()),
        index=0
    )

with col2:
    top_n_option = st.selectbox(
        "Show Top N Cities:",
        options=[5, 10, 15, 20, 50, "All Cities"],
        index=1
    )

selected_year = None if year_option == "All Years" else int(year_option)
top_n = None if top_n_option == "All Cities" else top_n_option

fig = create_map(selected_year, top_n)
st.plotly_chart(fig, use_container_width=True)

st.info("• Use dropdowns to explore yearly and ranked passenger traffic.\n\n"
        "• Bubble size represents total passenger volume.\n\n"
        "• Top 50 cities are labeled when showing all cities.")
