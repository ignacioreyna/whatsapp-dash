import os
import sys
import logging
import base64
import io
import uuid
import random
import dash
from dash.dependencies import Input, Output, State
import dash_core_components as dcc
import dash_html_components as html
import dash_table
from dash.exceptions import PreventUpdate

import plotly.graph_objects as go
import pandas as pd
import feather

from utils import get_df_from_content, get_df_for_plotting, dimensions_dict, metrics_dict

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
TEN_MB = 1024*1024*10
CURR_DIR = '/'.join(sys.argv[0].split('/')[:-1])

colors = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', 
    '#e377c2', '#7f7f7f', '#bcbd22', '#17becf', '#03012d', '#7cf7de', 
    '#fffe7a', '#db4bda', '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', 
    '#c5b0d5', '#c49c94', '#f7b6d2', '#c7c7c7', '#dbdb8d', '#bff5ff']  # matplotlib tab20 and some others

# Loading screen CSS
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css',
                        'https://codepen.io/chriddyp/pen/brPBPO.css']

meta_tags=[{'charset': 'utf-8'}, 
            {'name': 'description', 'content': 'En esta pagina vas a poder ver las estadisticas de tus conversaciones de WhatsApp'}, 
            {'name': 'keywords', 'content': 'whatsapp, estadisticas, stats, chat'}, 
            {'name': 'author', 'content': 'Ignacio Reyna'}, 
            {'http-equiv': 'expires', 'content': '3600'},
            {'name':'viewport','content':'width=device-width, initial-scale=1'},
            {'property': 'og:title', 'content': 'Whatstat'},
            {'property': 'twtitter:title', 'content': 'Whatstat'},
            {'property': 'og:description', 'content': 'En esta pagina vas a poder ver las estadisticas de tus conversaciones de WhatsApp'}, 
            {'property': 'twitter:description', 'content': 'En esta pagina vas a poder ver las estadisticas de tus conversaciones de WhatsApp'},
            {'property': 'og:site_name', 'content': 'Whatstat'}]

app = dash.Dash(__name__, 
                external_stylesheets=external_stylesheets, 
                meta_tags=meta_tags)
app.title = 'Whatstat'

server = app.server

app.config.suppress_callback_exceptions = True

app.layout = html.Div([
    html.H1(id='welcome-msg', 
            children='En esta pagina vas a poder ver las estadisticas de tus conversaciones de WhatsApp', 
            style={
                'width': '100%', 'height': '100%',
                'textAlign': 'center', 'margin': 'auto'
            }),
    html.H5(id='instructions',
            children='Subi un historial!',
            style={
                'width': '50%', 'height': '60px', 'lineHeight': '60px',
                'borderWidth': '1px',
                'borderRadius': '5px', 'textAlign': 'center', 'margin': 'auto'
            }),
    dcc.Upload(
        id='datatable-upload',
        children=html.Div([
            html.P(['Arrastra y solta o ',
                    html.A('elegi un archivo')]),
            html.P(['Aca podes ver como ', 
                    html.A('exportar un historial de chat', 
                            href='https://faq.whatsapp.com/android/chats/how-to-save-your-chat-history?lang=es', 
                            target="_blank")])
        ]),
        style={
            'width': '25%', 'height': '100%', 'lineHeight': '60px',
            'borderWidth': '1px', 'borderStyle': 'dashed',
            'borderRadius': '5px', 'textAlign': 'center', 'margin': 'auto'
        },
        max_size=TEN_MB,
        accept='.txt',
        className_reject='reject'
    ),
    html.Div(id='error_parsing'),
    html.Hr(),
    # dcc.Store(id='data', storage_type='session'),
    dcc.Store(id='session-id', storage_type='session'),
    dcc.Store(id='curr_filename', storage_type='session'),
    html.Div([
        dcc.Loading(id="loading",
                    children=[html.Div([
                                html.Div(style={'width': '20%', 'display': 'inline-block', 'margin': 'auto'}), 
                                html.Div(
                                    id='xaxis-columns-wrapper',
                                    children=[dcc.Dropdown(id='xaxis-columns',
                                                            style={'display': 'none'})],
                                    style={'width': '20%', 'display': 'inline-block', 'margin': 'auto'}),
                                html.Div(
                                    id='normalize_bars_wrapper',
                                    children=[dcc.Checklist(id='normalize_bars', 
                                                            style={'display': 'none'})],
                                    style={'width': '20%', 'display': 'inline-block', 'margin': 'auto', 'verticalAlign': 'top'}), 
                                html.Div(
                                    id='yaxis-columns-wrapper',
                                    children=[dcc.Dropdown(id='yaxis-columns',
                                                            style={'display': 'none'})],
                                    style={'width': '20%', 'display': 'inline-block', 'margin': 'auto'}), 
                                html.Div(style={'width': '20%', 'display': 'inline-block', 'margin': 'auto'})]),
                                html.Div(
                                    id='group_by_author_wrapper',
                                    children=[dcc.Checklist(
                                            id='group_by_author', 
                                            style={'display': 'none'})]
                                ),
                            html.Div(id='graph'), 
                    ],
                    type='circle')
    ])
])


def parse_contents(contents):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        return get_df_from_content(decoded.decode('utf-8'))
    except Exception as e:
        logger.error(e)
        return None


@app.callback([
    Output('session-id', 'data'),
    Output('curr_filename', 'data'), 
    Output('instructions', 'children'), 
    Output('error_parsing', 'children')],
    [Input('datatable-upload', 'contents')],
    [State('datatable-upload', 'filename'),
    State('session-id', 'data')]
)
def update_output(contents, new_filename, sessionid):
    if contents is None:
        sessionid = None
        filename = None
        instructions = 'Subi un historial!'
        error = None
        return sessionid, filename, instructions, error
    
    
    df = parse_contents(contents)
    if df is None:
        error = html.Div(children=[ html.Br(),
                                    'Ocurrio un error! Por favor intenta de nuevo. Si el error persiste, contactate a ',
                                    html.A('iganre@gmail.com', href='mailto:iganre@gmail.com')],
                        style={'textAlign': 'center', 'fontSize': 30})
        return sessionid, None, None, error
    
    sessionid = str(uuid.uuid4()) if not sessionid else sessionid
    
    file_location = os.path.join(CURR_DIR, 'cache', f'{sessionid}.feather')
    df.reset_index().to_feather(file_location)
    
    instructions = 'Si queres cambiar de conversacion podes subir otra!'
    error = None
    return (sessionid, 
            new_filename,
            instructions,
            error)


def plot(df, hue, y, group_by_author, normalize_bars):
    global colors
    is_normalized = normalize_bars is not None and len(normalize_bars) > 0
    if not y: 
        y = 'msg'
    metric = f' {metrics_dict[y].lower()}' if not is_normalized else f"% de l{'a' if 'words' == y or 'media' == y else 'o'}s {metrics_dict[y].lower()}"
    rounding = '.2f' if is_normalized else ''
    hovertemplate = f'%{{y:{rounding}}}{metric}<extra></extra>'
        
    if not group_by_author or len(group_by_author) == 0:
        x = hue if hue else 'year'
        plotting_df = get_df_for_plotting(df=df, x=x, y=y)
    else:
        x = 'author'
        plotting_df = get_df_for_plotting(
            df=df, x=x, y=y, hue=hue)
    
    data = [go.Bar(
        x=plotting_df.index,
        y=plotting_df[c].values,
        text=c,
        textposition='auto',
        hovertemplate=hovertemplate,
        name=c,
        marker_color=colors[index % len(colors)]
    )
        for index, c in enumerate(plotting_df.columns)]
    
    layout = dict(
        height=820,
        showlegend=x == 'author',
        hovermode='closest',
        xaxis=dict(
            type='category',
            rangeslider = {'visible': True}
        ),
        yaxis=dict(
            color='#7f7f7f',
            gridcolor='#eaeaea'
        ),
        paper_bgcolor='white',
        plot_bgcolor='white',
        legend=dict(
            x=0.5,
            y=1.15,
            orientation='h',
            xanchor='center',
            font=dict(
                size=15
            )
        ),
        hoverlabel=dict(
            bgcolor='white',
            font=dict(
                size=16,
                family='Rockwell'
            )
        ),
        barnorm='percent' if is_normalized else None
    )
    
    figure = go.Figure(data=data, layout=layout)
    
    return html.Div([
        dcc.Graph(
            id='whatsapp-info',
            figure=figure
        )
    ])
    


def dims_dropdown(df, value):
    return dcc.Dropdown(
        id='xaxis-columns',
        options=[{'label': v, 'value': k}
                for k, v in dimensions_dict.items()],
        placeholder='Eje x',
        value=value if value else 'year',
        clearable=False
    )


def metrics_dropdown(value, normalize_bars):
    is_normalized = normalize_bars is not None and len(normalize_bars) > 0
    return dcc.Dropdown(
        id='yaxis-columns',
        options=[{'label': v, 'value': k, 'disabled': is_normalized and k == 'wpm'} 
                for k, v in metrics_dict.items()],
        placeholder='Eje y',
        value=value if value and not (is_normalized and value == 'wpm') else 'msg',
        clearable=False
    )


def normalize_bars_checklist(is_normalized):
    return dcc.Checklist(
        id='normalize_bars',
        options=[{'label': 'Ver en porcentajes', 'value': 1}],
        value=[] if not is_normalized else is_normalized,
        style={'textAlign': 'center'}
    )


def group_by_author_checklist(group_by_author, filename):
    return html.Div([
                    dcc.Checklist(
                            id='group_by_author',
                            options=[{'label': 'Agrupar por autor/a.', 'value': 1}],
                            value=[] if not group_by_author else group_by_author,
                            style={'width': '50%', 'margin': 'auto', 'textAlign': 'center'}),
                    html.Div(
                            children=[html.Br(), 'Podes filtrar por autor/a!'] if len(group_by_author) > 0 else '', 
                            style={'width': '50%', 'margin': 'auto', 'textAlign': 'center', 
                                    'fontSize': 20}), 
                    html.Div(id='graph-title',
                            children=[html.Br(), filename[:-4]], 
                            style={'width': '50%', 'margin': 'auto', 'textAlign': 'center', 
                                    'fontSize': 25}),
                    ])


@app.callback(
    [Output('graph', 'children'),
    Output('xaxis-columns-wrapper', 'children'),
    Output('yaxis-columns-wrapper', 'children'),
    Output('normalize_bars_wrapper', 'children'),
    Output('group_by_author_wrapper', 'children')],
    [Input('session-id', 'data'),
    Input('xaxis-columns', 'value'), 
    Input('yaxis-columns', 'value'), 
    Input('normalize_bars', 'value'),
    Input('group_by_author', 'value')],
    [State('curr_filename', 'data'), 
     State('error_parsing', 'children')]
)
def update_graph(sessionid, hue, y_col, normalize_bars, group_by_author, filename, error):
    if not sessionid:
        raise PreventUpdate
    elif error is not None:
        return None, None, None, None, None
    else:
        file_location = os.path.join(CURR_DIR, 'cache', f'{sessionid}.feather')
        dff = pd.read_feather(file_location).drop('index', axis=1)
        group_by_author = [] if not hue else group_by_author
        x_dropdown = html.Div(dims_dropdown(dff, hue))
        y_dropdown = html.Div(metrics_dropdown(y_col, normalize_bars))
        normalize_checklist = normalize_bars_checklist(normalize_bars)
        author_checklist = group_by_author_checklist(group_by_author, filename)
        
        y_col = y_dropdown.children.value
        figure = plot(dff, hue, y_col, group_by_author, normalize_bars)
        
        return figure, x_dropdown, y_dropdown, normalize_checklist, author_checklist

is_prod = 'PORT' in os.environ and os.getenv('PORT') == '80'
if __name__ == '__main__':
    app.run_server(debug=not is_prod)
