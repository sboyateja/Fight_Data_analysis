import streamlit as st
import pandas as pd
import plotly.express as px

# Load data
@st.cache_data
def load_data():
    df = pd.read_csv('Summary_By_Origin_Airport.csv', low_memory=False)
    coords = pd.read_csv('airports_location.csv')
    fare = pd.read_csv('AverageFare_USA.csv')

    # Clean fare columns
    fare.columns = fare.columns.str.strip()
    fare.rename(columns={
        'Airport Code': 'Origin Airport Code',
        'Average Fare ($)': 'Avg Fare',
        'Inflation Adjusted Average Fare ($)': 'Adj Avg Fare'
    }, inplace=True)
    fare['Avg Fare'] = fare['Avg Fare'].astype(str).str.replace(r'[\$,]', '', regex=True).astype(float)
    fare['Adj Avg Fare'] = fare['Adj Avg Fare'].astype(str).str.replace(r'[\$,]', '', regex=True).astype(float)

    # Clean passenger columns
    for col in ['Total Passengers', 'Domestic Passengers', 'Outbound International Passengers']:
        df[col] = df[col].astype(str).str.replace(r'[,"]', '', regex=True).astype(float)

    df['Year'] = pd.to_numeric(df['Year'].astype(str).str.extract(r'(\d{4})')[0], errors='coerce').astype('Int64')
    df = df.dropna(subset=['Year'])

    df = df.merge(
        coords[['code', 'latitude', 'longitude', 'state']],
        left_on='Origin Airport Code',
        right_on='code',
        how='left'
    ).dropna(subset=['latitude', 'longitude'])

    df = df.merge(
        fare[['Origin Airport Code', 'Year', 'Avg Fare']],
        on=['Origin Airport Code', 'Year'],
        how='left'
    )

    annual = df.groupby(['Year', 'Origin City Name', 'state', 'latitude', 'longitude']).agg({
        'Total Passengers': 'sum',
        'Domestic Passengers': 'sum',
        'Outbound International Passengers': 'sum',
        'Avg Fare': 'mean'
    }).reset_index()

    return df, annual

df, annual_data = load_data()

# Sidebar Controls
st.title("Air Passenger Traffic by City")
year_options = ['All Years'] + sorted(df['Year'].dropna().unique().astype(int).tolist())
selected_year = st.selectbox("Select Year:", year_options, index=0)

top_n_options = ['All Cities', 5, 10, 15, 20, 50]
top_n = st.selectbox("Show Top N Cities:", top_n_options, index=2)

# Prepare data
if selected_year != 'All Years':
    data = annual_data[annual_data['Year'] == int(selected_year)].copy()
else:
    data = annual_data.groupby(['Origin City Name', 'state', 'latitude', 'longitude']).agg({
        'Total Passengers': 'sum',
        'Domestic Passengers': 'sum',
        'Outbound International Passengers': 'sum',
        'Avg Fare': 'mean'
    }).reset_index()

data = data.sort_values('Total Passengers', ascending=False)
data['Rank'] = data['Total Passengers'].rank(method='min', ascending=False).astype(int)
if top_n != 'All Cities':
    data = data.head(int(top_n))

data['Avg Fare'] = data['Avg Fare'].fillna(100)

data['hover_text'] = data.apply(
    lambda x: f"<b>#{x['Rank']} {x['Origin City Name']}, {x['state']}</b><br>"
              f"Total: {x['Total Passengers']:,.0f}<br>"
              f"Domestic: {x['Domestic Passengers']:,.0f}<br>"
              f"International: {x['Outbound International Passengers']:,.0f}<br>"
              f"Average Fare: ${x['Avg Fare']:,.2f}",
    axis=1
)

# Plot
fig = px.scatter_geo(
    data,
    lat='latitude',
    lon='longitude',
    size='Total Passengers',
    color='Total Passengers',
    hover_name='hover_text',
    scope='usa',
    projection='albers usa',
    title=f"Passenger Traffic by City {'in ' + str(selected_year) if selected_year != 'All Years' else '(All Years)'} {f'(Top {top_n})' if top_n != 'All Cities' else ''}",
    size_max=30,
    color_continuous_scale=px.colors.sequential.Viridis
)

fig.update_layout(
    margin={"r": 0, "t": 40, "l": 0, "b": 0},
    height=600
)

st.plotly_chart(fig, use_container_width=True)

st.info("Bubble size represents total passengers. Top 50 cities are labeled when viewing all cities.")

