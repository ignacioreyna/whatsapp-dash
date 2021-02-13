import os
import logging
import base64
import uuid
import dash
from dash.dependencies import Input, Output, State
import dash_core_components as dcc
import dash_html_components as html
import dash_component_unload as dcu
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate

import plotly.graph_objects as go
import pandas as pd

from utils import get_df_from_content, get_df_for_plotting, showable_dimensions_dict, metrics_dict


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)
TEN_MB = 1024 * 1024 * 10
CURR_DIR = os.path.dirname(os.path.realpath(__file__))

colors = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b',
    '#e377c2', '#7f7f7f', '#bcbd22', '#17becf', '#03012d', '#7cf7de',
    '#fffe7a', '#db4bda', '#aec7e8', '#ffbb78', '#98df8a', '#ff9896',
    '#c5b0d5', '#c49c94', '#f7b6d2', '#c7c7c7', '#dbdb8d', '#bff5ff']  # matplotlib tab20 and some others

# Loading screen CSS
external_stylesheets = [dbc.themes.BOOTSTRAP,
                        "https://codepen.io/chriddyp/pen/brPBPO.css"]

meta_tags = [{'charset': 'utf-8'},
             {'name': 'description',
              'content': 'En esta página vas a poder ver las estadísticas de tus conversaciones de WhatsApp'},
             {'name': 'keywords', 'content': 'whatsapp, estadisticas, stats, chat'},
             {'name': 'author', 'content': 'Ignacio Reyna'},
             {'http-equiv': 'expires', 'content': '3600'},
             {'name': 'viewport', 'content': 'width=device-width, initial-scale=1'},
             {'property': 'og:title', 'content': 'WhatStat'},
             {'property': 'twitter:title', 'content': 'WhatStat'},
             {'property': 'og:description',
              'content': 'En esta página vas a poder ver las estadísticas de tus conversaciones de WhatsApp'},
             {'property': 'twitter:description',
              'content': 'En esta página vas a poder ver las estadísticas de tus conversaciones de WhatsApp'},
             {'property': 'og:site_name', 'content': 'WhatStat'},
             {'property': 'og:url', 'content': 'http://whatstat.site'},
             {'property': 'og:type', 'content': 'website'},
             {'property': 'og:image',
              'content': 'https://cdn.icon-icons.com/icons2/550/PNG/512/business-color_board-30_icon-icons.com_53475.png'},
             {'property': 'og:image:type', 'content': 'image/png'}]

app = dash.Dash(__name__,
                external_stylesheets=external_stylesheets,
                meta_tags=meta_tags)
app.title = 'WhatStat'

app.config.suppress_callback_exceptions = True

app.layout = html.Div(
    className='container-fluid',
    children=[
        html.Div(
            children=[
                html.H1(
                    id='welcome-msg',
                    children=u'En esta página vas a poder ver las estadísticas de tus conversaciones de WhatsApp',
                    className='col-xs-12 text-center mx-auto'
                ),
                html.Br(),
                html.H5(id='instructions',
                        className='col-sm-8 text-center mx-auto'
                        ),
                html.Br(),
                dbc.Spinner(
                    id="uploading",
                    size='xl',
                    color='primary',
                    children=[
                        dcc.Upload(
                            id='datatable-upload',
                            children=html.Div(
                                className='align-self-center',
                                children=[
                                    u'Arrastrá y soltá o ',
                                    html.A(u'elegí un archivo',
                                           href='#'),
                                ],
                            ),
                            className='col-sm-4 text-center rounded mx-auto justify-content-center d-flex',
                            style={'borderStyle': 'dashed', 'height': '100px', 'borderWidth': '1px'},
                            max_size=TEN_MB,
                            accept='.txt',
                            className_reject='reject'
                        )
                    ]
                ),
                html.Div(id='error_parsing')]),
        html.Hr(),
        dcc.Store(id='session-id', storage_type='session'),
        dcc.Store(id='curr_filename', storage_type='session'),
        html.Div(
            children=[
                html.Div(
                    className='row mx-auto',
                    children=[
                        html.Div(
                            id='xaxis-columns-wrapper',
                            className='col-xl-3 offset-xl-3 col-md-5 offset-md-1 col-sm-6 mb-3',
                            children=[dcc.Dropdown(
                                id='xaxis-columns',
                                className='d-none')],
                        ),
                        html.Div(
                            id='yaxis-columns-wrapper',
                            className='col-xl-3 col-md-5 col-sm-6 mb-3',
                            children=[dcc.Dropdown(
                                id='yaxis-columns',
                                className='d-none')],
                        )]),
                html.Div(
                    className='row mx-auto',
                    children=[
                        html.Div(
                            id='optionals_dropdown_wrapper',
                            className='col-md-6 mb-3  mx-auto',
                            children=[
                                dcc.Dropdown(
                                    id='optionals_dropdown',
                                    className='d-none'
                                )
                            ]
                        )
                    ]
                ),
                dbc.Spinner(id="loading",
                            spinner_style={"width": "8rem", "height": "8rem"},
                            color='primary',
                            children=html.Div(id='graph')),
            ]
        ),
        html.Div(id='page-listener-dummy'),
        dcu.DashComponentUnload(id='page-listener'),
    ]
)


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
    Output('loading', 'children'),
    Output('error_parsing', 'children')],
    [Input('datatable-upload', 'contents')],
    [State('datatable-upload', 'filename'),
     State('session-id', 'data')]
)
def update_output(contents, new_filename, sessionid):
    graph = html.Div(id='graph')
    if contents is None:
        sessionid = None
        filename = None
        instructions = [html.P(u'Subí un historial!'),
                        html.P(html.A(u'Cómo exportar un historial de chat.',
                                      href='https://faq.whatsapp.com/android/chats/how-to-save-your-chat-history?lang=es',
                                      target="_blank"))]
        error = None

        return sessionid, filename, instructions, graph, error

    df = parse_contents(contents)
    if df is None:
        error = html.Div(children=[html.Br(),
                                   u'Ocurrió un error! Por favor intentá de nuevo. Si el error persiste, contactate a ',
                                   html.A('iganre@gmail.com', href='mailto:iganre@gmail.com')],
                         style={'textAlign': 'center', 'fontSize': 30})
        return sessionid, None, None, graph, error

    sessionid = str(uuid.uuid4()) if not sessionid else sessionid

    file_location = os.path.join(CURR_DIR, 'cache', f'{sessionid}.feather')
    df.reset_index().to_feather(file_location)

    instructions = u'Si querés cambiar de conversación podés subir otra!'
    error = None
    return (sessionid,
            new_filename,
            instructions,
            graph,
            error)


def plot(df, hue, y, should_group_by_author, should_group_by_year, is_normalized, filename):
    global colors
    if not y:
        y = 'msg'
    metric = f' {metrics_dict[y].lower()}' if not is_normalized else f"% de l{'a' if 'words' == y or 'media' == y else 'o'}s {metrics_dict[y].lower()}"
    rounding = '.2f' if is_normalized else '.2s'
    hovertemplate = f'%{{y:{rounding}}}{metric}<extra></extra>'

    if should_group_by_author:
        x = 'author'
        if should_group_by_year:
            hue = f'year_{hue}' if hue else 'year'
        plotting_df = get_df_for_plotting(df=df, x=x, y=y, hue=hue)
    else:
        x = hue if hue else 'year'
        if should_group_by_year:
            hue = 'year'
        else:
            hue = None
        plotting_df = get_df_for_plotting(df=df, x=x, y=y, hue=hue)

    data = [go.Bar(
        x=plotting_df.index,
        y=plotting_df[c].values,
        text=c,
        textposition='auto',
        hovertemplate=hovertemplate,
        name=c,
        marker_color=colors[index % len(colors)] if should_group_by_author else '#4481e3'
    )
        for index, c in enumerate(plotting_df.columns)]

    layout = dict(
        height=700 if not should_group_by_author else 700 + (33 * (len(set(plotting_df.columns)) // 10)),
        showlegend=x == 'author',
        hovermode='closest',
        title=dict(
            text=(' '.join(filename.split()[:3] + ['<br>'] + filename.split()[3:])
                  if len(filename.split()) > 3
                  else filename)[:-4],
            x=0.5,
            xanchor='center',
            font=dict(
                size=30,
                family='Rockwell, monospace',
                color='black',
            )
        ),
        xaxis=dict(
            type='category',
            rangeslider=dict(
                visible=False
            )
        ),
        yaxis=dict(
            color='#7f7f7f',
            gridcolor='#eaeaea'
        ),
        paper_bgcolor='white',
        plot_bgcolor='white',
        legend=dict(
            x=0.5,
            y=-0.15,
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

    return html.Div(
        className='mx-3',
        children=[
            dcc.Graph(
                id='whatsapp-info',
                figure=figure
            ),
            html.Div(
                children=[
                    'Podés filtrar por autor/a! ',
                    dbc.Tooltip(
                        children='Haciendo click en cada uno de los nombres podés agregarlos o quitarlos. Haciendo doble click en uno, podés quedarte únicamente con ese.',
                        target='author_filter_instructions',
                    ),
                    html.Sup(id='author_filter_instructions', children='(?)')] if should_group_by_author else '',
                className='text-center mx-auto',
                style={'fontSize': 25}
            ),
            html.Br(),
            html.Br(),
            html.Br(),
        ]
    )


def dims_dropdown(value):
    return dcc.Dropdown(
        id='xaxis-columns',
        options=[{'label': v, 'value': k}
                 for k, v in showable_dimensions_dict.items()],
        placeholder='Eje x',
        value=value if value else 'year',
        clearable=False
    )


def metrics_dropdown(value, is_normalized):
    return dcc.Dropdown(
        id='yaxis-columns',
        options=[{'label': v, 'value': k, 'disabled': is_normalized and k == 'wpm'}
                 for k, v in metrics_dict.items()],
        placeholder='Eje y',
        value=value if value and not (is_normalized and value == 'wpm') else 'msg',
        clearable=False
    )


def optionals_dropdown(value):
    return html.Div([
        dcc.Dropdown(
            id='optionals_dropdown',
            options=[
                {'label': 'Agrupar por autor/a', 'value': 'author'},
                {'label': u'Agrupar por año', 'value': 'year'},
                {'label': 'Ver en porcentajes', 'value': 'normalize'}
            ],
            multi=True,
            value=[] if not value else value,
            placeholder='Opciones'
        )]
    )


@app.callback(
    [Output('graph', 'children'),
     Output('xaxis-columns-wrapper', 'children'),
     Output('yaxis-columns-wrapper', 'children'),
     Output('optionals_dropdown_wrapper', 'children')],
    [Input('session-id', 'data'),
     Input('xaxis-columns', 'value'),
     Input('yaxis-columns', 'value'),
     Input('optionals_dropdown', 'value')],
    [State('curr_filename', 'data'),
     State('error_parsing', 'children')]
)
def update_graph(sessionid, x, y, options, filename, error):
    if not sessionid:
        raise PreventUpdate
    elif error is not None:
        return None, None, None, None, None, None
    else:
        normalize_bars = options is not None and 'normalize' in options
        group_by_author = options is not None and 'author' in options
        group_by_year = options is not None and 'year' in options and x != 'year'

        file_location = os.path.join(CURR_DIR, 'cache', f'{sessionid}.feather')
        dff = pd.read_feather(file_location).drop('index', axis=1)
        x_dropdown = html.Div(dims_dropdown(x))
        y_dropdown = html.Div(metrics_dropdown(y, normalize_bars))
        opts_dropdown = optionals_dropdown(options)

        y_col = y_dropdown.children.value
        figure = plot(dff, x, y_col, group_by_author, group_by_year, normalize_bars, filename)

        return figure, x_dropdown, y_dropdown, opts_dropdown


@app.callback(
    Output('page-listener-dummy', 'children'),
    [Input('page-listener', 'close')],
    [State('session-id', 'data')])
def delete_cache(close, sessionid):
    if not close:
        raise PreventUpdate
    file_location = os.path.join(CURR_DIR, 'cache', f'{sessionid}.feather')
    if os.path.isfile(file_location):
        os.remove(file_location)
    return None


port = os.getenv('PORT', None)
is_prod = port and port in ['80', '443']
context = None
if port == '443':
    context = ('keys/fullchain.pem', 'keys/privkey.pem')


server = app.server

if __name__ == '__main__':
    app.run_server(
        debug=not is_prod, 
        ssl_context=context, 
        port=port or 3000
    )
