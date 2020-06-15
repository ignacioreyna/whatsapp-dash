import os
import logging
import base64
import io
import dash
from dash.dependencies import Input, Output, State
import dash_core_components as dcc
import dash_html_components as html
import dash_table
from dash.exceptions import PreventUpdate

import plotly.graph_objects as go
import pandas as pd

from utils import get_df_from_content, get_df_for_plotting, labels_dict, add_date_metrics

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
TEN_MB = 1024*1024*10

# Loading screen CSS
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css',
                        'https://codepen.io/chriddyp/pen/brPBPO.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

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
            style={
                'width': '50%', 'height': '60px', 'lineHeight': '60px',
                'borderWidth': '1px',
                'borderRadius': '5px', 'textAlign': 'center', 'margin': 'auto'
            }),
    dcc.Upload(
        id='datatable-upload',
        children=html.Div([
            html.P(['Arrastra y solta o ',
                    html.A('elegi un archivo'), '. Tiene que ser .txt']),
            html.P(u'Tamaño maximo: 10 MB')
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
    html.Hr(),
    dcc.Store(id='raw_data', storage_type='memory'),
    dcc.Store(id='data', storage_type='session'),
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
                                html.Div(style={'width': '20%', 'display': 'inline-block', 'margin': 'auto'}), 
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
    ]),
])


def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        return get_df_from_content(decoded.decode('utf-8'))
    except Exception as e:
        logger.error()
        return html.Div([
            'There was an error processing this file.'
        ])


@app.callback([
    Output('data', 'clear_data'),
    Output('raw_data', 'data'),
    Output('curr_filename', 'data'), 
    Output('instructions', 'children')],
    [Input('datatable-upload', 'contents')],
    [State('datatable-upload', 'filename'),  
    State('curr_filename', 'data')]
)
def update_output(contents, new_filename, curr_filename):
    if contents is None:
        clear_data = True
        raw_data = None
        filename = None
        instructions = 'Subi un historial!'
        return clear_data, raw_data, filename, instructions
    
    if new_filename != curr_filename:
    
        df = parse_contents(contents, new_filename)
        clear_data = True
        raw_data = df.to_json(orient='split', index=False)
        date_format = None
        instructions = 'Si queres cambiar de conversacion podes subir otra!'
        
        return (clear_data, 
                raw_data, 
                new_filename,
                instructions)


@app.callback(
    [Output('raw_data', 'clear_data'), 
    Output('data', 'data')], 
    [Input('raw_data', 'data')]
)
def parse_raw_data(raw_data):
    if raw_data is None:
        raise PreventUpdate
    else:
        clear_raw_data = True
        dff = pd.read_json(raw_data, orient='split')
        data = add_date_metrics(dff).to_json(
            date_format='iso', orient='split', index=False)
    return clear_raw_data, data


def plot(df, filename, hue, y, group_by_author):
    if not y: 
        y = 'msg'
    metric = 'mensajes' if y == 'msg' else 'palabras'
    hovertemplate = f'%{{y:.3s}} {metric}<extra></extra>'
    ops = dict(
        msg='count',
        words='sum',
        wpm='mean'
    )
    agg_op = ops[y]
    
    if y == 'wpm':
        y = 'words'
        
    if not group_by_author or len(group_by_author) == 0:
        x = hue if hue else 'year'
        plotting_df = get_df_for_plotting(df=df, x=x, y=y, hue=None, agg_op=agg_op)
    else:
        plotting_df = get_df_for_plotting(
            df=df, x='author', y=y, hue=hue, agg_op=agg_op)
    
    data = [go.Bar(
        x=plotting_df.index,
        y=plotting_df[c].values,
        text=c,
        textposition='auto',
        meta=c,
        hovertemplate=hovertemplate
    )
        for c in plotting_df.columns]
    return html.Div([
        dcc.Graph(
            id='example-graph',
            figure={
                'data': data,
                'layout': {
                    'title': filename[:-4],
                    'showlegend': False,
                    'hovermode': 'closest',
                    'height': 800,
                    'xaxis': {'type': 'category'},
                }
            }
        )
    ])
    


def dims_dropdown(df, value):
    dimensions = filter(lambda x: x not in [
                        'msg', 'words', 'author', 'date'], df.columns)
    return dcc.Dropdown(
        id='xaxis-columns',
        options=[{'label': labels_dict[i], 'value': i}
                for i in dimensions],
        placeholder='Eje x',
        value=value if value else 'year',
        clearable=False
    )


def metrics_dropdown(value):
    return dcc.Dropdown(
        id='yaxis-columns',
        options=[{'label': 'Mensajes', 'value': 'msg'},
                {'label': 'Palabras', 'value': 'words'},
                {'label': 'Palabras por mensaje', 'value': 'wpm'}],
        placeholder='Eje y',
        value=value if value else 'msg',
        clearable=False
    )



def group_by_author_checklist(group_by_author, hue):
    return html.Div([
                    dcc.Checklist(
                            id='group_by_author',
                            options=[{'label': 'Agrupar por autor/a.', 'value': 1, 'disabled': not hue}],
                            value=[] if not group_by_author or not hue else group_by_author,
                            style={'width': '50%', 'margin': 'auto', 'textAlign': 'center', 'color': '#8c8c8c' if not hue else '#323232'}),
                    html.Div(
                            children='Para agrupar por autor/a debes elegir un valor para el eje x' if not hue else '', 
                            style={'width': '50%', 'margin': 'auto', 'textAlign': 'center'})])


@app.callback(
    [Output('graph', 'children'),
    Output('xaxis-columns-wrapper', 'children'),
    Output('yaxis-columns-wrapper', 'children'),
    Output('group_by_author_wrapper', 'children')],
    [Input('data', 'data'),
    Input('xaxis-columns', 'value'), 
    Input('yaxis-columns', 'value'), 
    Input('group_by_author', 'value')],
    [State('curr_filename', 'data')]
)
def update_graph(data, hue, y_col, group_by_author, filename):
    if not data:
        raise PreventUpdate
    else:
        dff = pd.read_json(data, orient='split')
        group_by_author = [] if not hue else group_by_author
        x_dropdown = html.Div(dims_dropdown(dff, hue))
        y_dropdown = html.Div(metrics_dropdown(y_col))
        author_checklist = group_by_author_checklist(group_by_author, x_dropdown.children.value)
        figure = plot(dff, filename, hue, y_col, group_by_author)
        
        return figure, x_dropdown, y_dropdown, author_checklist


if __name__ == '__main__':
    app.run_server(port=int(os.environ.get('PORT', '3005')))
