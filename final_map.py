import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html
from dash.dependencies import Input, Output

# 1. Load and clean data
print("Loading data...")
df = pd.read_csv('Summary_By_Origin_Airport.csv', low_memory=False)
airport_coords = pd.read_csv('airports_location.csv')
fare = pd.read_csv('AverageFare_USA.csv')

# Clean fare column names
fare.columns = fare.columns.str.strip()

# Rename fare columns
fare.rename(columns={
    'Airport Code': 'Origin Airport Code',
    'Average Fare ($)': 'Avg Fare',
    'Inflation Adjusted Average Fare ($)': 'Adj Avg Fare'
}, inplace=True)

# Clean fare values
fare['Avg Fare'] = fare['Avg Fare'].astype(str).str.replace(r'[\$,]', '', regex=True)
fare['Adj Avg Fare'] = fare['Adj Avg Fare'].astype(str).str.replace(r'[\$,]', '', regex=True)
fare['Avg Fare'] = pd.to_numeric(fare['Avg Fare'], errors='coerce')
fare['Adj Avg Fare'] = pd.to_numeric(fare['Adj Avg Fare'], errors='coerce')

# Clean numeric columns in main dataset
numeric_cols = ['Total Passengers', 'Domestic Passengers', 'Outbound International Passengers']
for col in numeric_cols:
    if df[col].dtype == object:
        df[col] = df[col].astype(str).str.replace(r'[,"]', '', regex=True)
    df[col] = pd.to_numeric(df[col], errors='coerce')

# Extract and clean Year
df['Year'] = pd.to_numeric(df['Year'].astype(str).str.extract(r'(\d{4})')[0], errors='coerce')
df = df.dropna(subset=['Year'])
df['Year'] = df['Year'].astype(int)

# Merge airport coordinates and state
print("Merging airport coordinates...")
df = df.merge(
    airport_coords[['code', 'latitude', 'longitude', 'state']],
    left_on='Origin Airport Code',
    right_on='code',
    how='left'
).dropna(subset=['latitude', 'longitude'])

# Merge with fare data
print("Merging fare data...")
df = df.merge(
    fare[['Origin Airport Code', 'Year', 'Avg Fare']],
    on=['Origin Airport Code', 'Year'],
    how='left'
)

# Pre-calculate yearly aggregates including state
print("Pre-calculating yearly aggregates...")
annual_data = df.groupby(['Year', 'Origin City Name', 'state', 'latitude', 'longitude']).agg({
    'Total Passengers': 'sum',
    'Domestic Passengers': 'sum',
    'Outbound International Passengers': 'sum',
    'Avg Fare': 'mean'
}).reset_index()

# 2. Map creation function
def create_map(selected_year=None, top_n=None):
    start_time = pd.Timestamp.now()
    print(f"Generating map for year: {selected_year}, top_n: {top_n}")

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

    # Annotate top 50
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

    print(f"Map created in {(pd.Timestamp.now() - start_time).total_seconds():.2f}s")
    return fig

# 3. Dash App Setup
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("Air Passenger Traffic by City", style={'textAlign': 'center'}),

    html.Div([
        html.Div([
            html.Label("Select Year:"),
            dcc.Dropdown(
                id='year-dropdown',
                options=[{'label': 'All Years', 'value': 'all'}] +
                        [{'label': str(y), 'value': y} for y in sorted(df['Year'].unique())],
                value='all',
                clearable=False
            )
        ], style={'width': '48%', 'display': 'inline-block'}),

        html.Div([
            html.Label("Show Top N Cities:"),
            dcc.Dropdown(
                id='topn-dropdown',
                options=[
                    {'label': 'Top 5', 'value': 5},
                    {'label': 'Top 10', 'value': 10},
                    {'label': 'Top 15', 'value': 15},
                    {'label': 'Top 20', 'value': 20},
                    {'label': 'Top 50', 'value': 50},
                    {'label': 'All Cities', 'value': 'all'}
                ],
                value=10,
                clearable=False
            )
        ], style={'width': '48%', 'display': 'inline-block', 'float': 'right'})
    ], style={'padding': '20px'}),

    dcc.Loading(dcc.Graph(id='city-map'), type="circle"),

    html.Div([
        html.P("Use dropdowns to explore yearly and ranked passenger traffic."),
        html.P("Bubble size represents total passenger volume."),
        html.P("Top 50 cities are labeled when showing all cities."),
    ], style={'padding': '0 40px'})
])

# 4. Callback
@app.callback(
    Output('city-map', 'figure'),
    Input('year-dropdown', 'value'),
    Input('topn-dropdown', 'value')
)
def update_map(selected_year, top_n):
    if selected_year == 'all':
        selected_year = None
    if top_n == 'all':
        top_n = None
    return create_map(selected_year, top_n)

# 5. Run App
if __name__ == "__main__":
    app.run_server(debug=True)
