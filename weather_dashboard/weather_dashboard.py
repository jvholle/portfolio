import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State
from dash.exceptions import PreventUpdate
import pandas as pd
import plotly.express as px
from predict_valuesinput import PerfPrec
from get_data import QryApi

# Initial set of States for main query
states = ['CA', 'MA', 'VA', 'LA', 'AK']
# filter df by four time periods per day, Extract the hour from 'datetime' column; anomoly detect python Luminol


def procdata(df):
    # Ensure 'timestamp' column is in datetime format and convert to UTC
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_convert('UTC')
    df['hour'] = df['timestamp'].dt.hour
    df['dayofweek'] = df['timestamp'].dt.dayofweek
    pred_precip = PerfPrec.linear_regr_timeseries(df)  # get precip & predict values w/new df & make the predict df the df.
    df = pred_precip

    # use pivot df conversion with the resample() method to resample the time series data to another frequency
    grp2 = df.pivot(index="timestamp", columns="station_id", values="temperature")  # reconfig df > stations w/precip
    grp3 = df.pivot(index="timestamp", columns="station_id", values="wind_speed")  # reconfig df > stations w/precip
    grppcip = df.pivot(index="timestamp", columns="station_id", values="precipitation")  # reconfig df > stations w/precip

    # add week to the predicted df for predicted data
    df['timepredict'] = df['timestamp'] + pd.Timedelta(days=7)  # plusweek_df = df[df['timestamp'] + pd.Timedelta(days=7)]
    grp4 = df.pivot(index="timepredict", columns="station_id", values="predict_nextweek")  # reconfig df > stations w/precip
    print(type(grp2))
    # define an average graph of values per day by station; resample in parentheses, is a code D=Daily, MS=Month;
    day_aver = grp2.resample("D").mean()  # .plot(style="-o", figsize=(10, 5))  # must have stat like mean | max
    return df, grp2, grp3, grp4, grppcip, day_aver


# df = procdata(pd.read_csv('weather_obs_precip071724.csv'))[0]  # get unique station names for DD
# sta_names = list(df['station_id'].unique())

# Initialize the Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])  # BOOTSTRAP

# Layout of the app
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H1("Weather Station Data", className="text-center"), width=12)
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Dropdown(
                id='state-dropdown',
                options=[{'label': name, 'value': name} for name in states],
                multi=False,
                placeholder="Select a State"
            ),
        ], width=12),
        dbc.Col([
            dcc.Dropdown(
                id='station-dropdown',
                # options=[{'label': name, 'value': name} for name in sta_names],
                multi=True,
                placeholder="Select Weather Stations"
            ),
        ], width=12)
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Graph(id='map', style={"margin-bottom": "15px"})  # Use CSS styles for formating.
        ], width=12)
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Graph(id='temperature-graph')  # , className='text-center' , 'text-bold'
        ], width=6),
        dbc.Col([
            dcc.Graph(id='wind-graph')
        ], width=6, className="container px-4")
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Graph(id='precip-graph', style={"margin-top": "15px", "margin-bottom": "15px"})
        ], width=6, className="container px-4"),
        dbc.Col([
            dcc.Graph(id='pred-precip-graph', style={"margin-top": "15px", "margin-bottom": "15px"})
        ], width=6, className="container px-4")
    ]),
    dbc.Row([
        dbc.Col([
            dbc.Table(id='data-table', bordered=True, hover=True, responsive=True, striped=True)
        ], width=12, className="container px-4", style={"title": "Weather Service Data", "margin-bottom": "15px"})
    ]),
    dcc.Store(id='memory-output')
], fluid=True)


# Separate callback for dynamic dropdown; interaction with gui uses the input/outputs to pass parameters.
@app.callback(
    Output("station-dropdown", "options"),
    Input('memory-output', 'data')
    # State("my-multi-dynamic-dropdown", "value")
)
def update_multi_options(data):
    if not data:
        raise PreventUpdate
    # get and return the stations from dict for dd.
    return list(set(it['station_id'] for it in data))  # sta_names = list(df['station_id'].unique())


# In memory to share between callbacks; once State is selected, the state specific df pass to station callback pop figs
@app.callback(Output('memory-output', 'data'), Input('state-dropdown', 'value'))
def update_data(value):
    if value is None:
        value = 'MA'  # raise PreventUpdate
    print("Was the state named passed to the get data func? ", value)
    # expensive data processing step  // get data, work in fabicate precip data if none.
    resdf = QryApi.main(value)

    return resdf.to_dict('records')


@app.callback(
    [Output('map', 'figure'),
     Output('temperature-graph', 'figure'),
     Output('wind-graph', 'figure'),
     Output('precip-graph', 'figure'),
     Output('pred-precip-graph', 'figure'),
     Output('data-table', 'children')],
    [Input('memory-output', 'data'), Input('station-dropdown', 'value')]
)
def update_output(data, selected_stations):  # add the df from other func, then resample...
    # pause update until State is selected
    if data is None:
        raise PreventUpdate

    temp_df = pd.DataFrame.from_dict(data=data)  # , orient='index')
    temp_df = temp_df.drop('geometry', axis=1)
    df, grp2, grp3, grp4, grppcip, day_aver = procdata(temp_df)  # Data has to be json for Dash app; not dataframe.
    # convert the geometry object field to string;  df = df.drop('geometry', axis=1)  #df['geometry'].apply(str)
    if selected_stations is None or len(selected_stations) == 0:
        filtered_df, day_aver, ws_day_aver, precip_aver, pred_aver = \
            df, grp2.resample("D").mean(), grp3.resample("D").mean(), grppcip.resample("D").mean(), grp4.resample("D").mean()
    else:
        filtered_df = df[df['station_id'].isin(selected_stations)]
        # exclude name column; print(data.loc[:, data.columns != 'name'])
        fil_grp2, fil_grp3, fil_precip_aver, fil_pred_aver = grp2.loc[:, selected_stations], grp3.loc[:, selected_stations], \
                                         grppcip.loc[:, selected_stations], grp4.loc[:, selected_stations]
        day_aver = fil_grp2.resample("D").mean()
        ws_day_aver = fil_grp3.resample("D").mean()
        precip_aver = fil_precip_aver.resample("D").mean()
        pred_aver = fil_pred_aver.resample("D").mean()

    # Map
    map_fig = px.scatter_mapbox(
        filtered_df,
        lat="latitude",
        lon="longitude",
        hover_name="station_id",  # "station_name",
        hover_data=["temperature", "wind_speed"],
        color_discrete_sequence=["fuchsia"],
        zoom=6,
        height=500
    )
    map_fig.update_layout(mapbox_style="open-street-map")
    map_fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})

    # Temperature Graph >> Add pivot table directly...
    temp_fig = px.bar(
        day_aver, barmode='group', title='Mean Temp by Day'
    )  # , labels=dict(xaxis_title='Day', yaxis_title='Temps'))
    # config chart
    temp_fig.update_layout(xaxis_title='Day', yaxis_title='Temps', title_x=0.5)  # title='Mean Temp by Day',

    # wind Graph
    wind_fig = px.line(
        ws_day_aver, markers=True  # orientation='h'  # line_group='timestamp',
    )
    # config chart
    wind_fig.update_layout(title='Mean Windspeed by Day',
                           xaxis_title='Day',
                           yaxis_title='Wind Speed (km/hr)', title_x=0.5)

    # Precipitation Graph
    precip_fig = px.line(
        precip_aver, markers=True  # predict_day_aver orientation='h'  # line_group='timestamp',
    )
    # config chart
    precip_fig.update_layout(title='Precipitation by Day',
                           xaxis_title='Day',
                           yaxis_title='Precipitation (mm)', title_x=0.5)

    # Predict Precip Graph
    predict_precip = px.line(
        pred_aver, markers=True  # predict_day_aver orientation='h'  # line_group='timestamp',
    )
    # config chart
    predict_precip.update_layout(title='Predicted Precipitation by Day',
                           xaxis_title='Day',
                           yaxis_title='Predicted (mm)', title_x=0.5)

    # Data Table
    table_header = [
        html.Thead(html.Tr([html.Th(col) for col in filtered_df.columns]))
    ]
    table_body = [
        html.Tbody([
            html.Tr([
                html.Td(filtered_df.iloc[i][col]) for col in filtered_df.columns
            ]) for i in range(len(filtered_df))
        ])
    ]
    table = table_header + table_body

    return map_fig, temp_fig, wind_fig, precip_fig, predict_precip, table


if __name__ == '__main__':
    app.run_server(debug=True)
