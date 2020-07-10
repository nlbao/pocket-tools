import random
import plotly
import pandas as pd
from typing import List, Dict, Tuple, Any
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import plotly.express as px

from data import load_cache, count_words_in_title, get_word_counts, get_reading_time, get_domain_counts
from data import get_added_time_series, get_archived_time_series, get_language_counts, get_favorite_count
from constants import DEFAULT_READING_SPEED


app = dash.Dash()
data = load_cache()


def plot_two_columns(col0: Any, col1: Any) -> html.Div:
    return html.Div(className='row', children=[
        html.Div([col0], className='two-columns--0'),
        html.Div([col1], className='two-columns--1'),
    ])


def word_cloud_plot(data: List[Dict]) -> html.Div:
    word_cnts = count_words_in_title(data)
    n_word = len(word_cnts)
    words = list(word_cnts.keys())
    weights = [word_cnts[w] for w in words]
    colors = [plotly.colors.DEFAULT_PLOTLY_COLORS[random.randrange(1, 10)] for i in range(n_word)]
    data = go.Scatter(x=[random.random() for i in range(n_word)],
                      y=[random.random() for i in range(n_word)],
                      mode='text',
                      text=words,
                      marker={'opacity': 0.3},
                      textfont={'size': weights,
                                'color': colors})
    layout = go.Layout({'xaxis': {'showgrid': False, 'showticklabels': False, 'zeroline': False},
                        'yaxis': {'showgrid': False, 'showticklabels': False, 'zeroline': False}})
    fig = go.Figure(data=[data], layout=layout)
    return html.Div([
        dcc.Graph(id='word-cloud', figure=fig)
    ])


def articles_over_time_plot(data: List[Dict], should_cumsum: bool = True) -> dcc.Graph:
    df = get_added_time_series(data)
    archived_df = get_archived_time_series(data)
    if len(archived_df) > 0:
        df = pd.merge(df, archived_df, how='outer', left_index=True, right_index=True)
    if should_cumsum:
        df.fillna(0, inplace=True)
        df = df.cumsum()
    fig = px.line(df,
                  labels={'index': 'Date', 'value': 'Number of articles'},
                  title='Article Count Over Time')
    return dcc.Graph(id='time_series', figure=fig)


def word_counts_plot(data: List[Dict]) -> dcc.Graph:
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=get_word_counts(data, filters=[['status', '=', 0]]),  # unread
        name='Unread articles',
    ))
    fig.add_trace(go.Histogram(
        x=get_word_counts(data, filters=[['status', '=', 1]]),  # archived
        name='Archived articles',
    ))
    fig.update_layout(
        title_text='Word Count Distribution',  # title of plot
        xaxis_title_text='Number of words',
        yaxis_title_text='Number of articles',
        barmode='stack'  # The two histograms are drawn on top of another
    )
    return dcc.Graph(id='word-count', figure=fig)


# -------------------- Reading time -------------------- #
def get_reading_time_chart(reading_speed: int) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=get_reading_time(data, reading_speed=reading_speed, filters=[['status', '=', 0]]),  # unread
        name='Unread articles',
    ))
    fig.add_trace(go.Histogram(
        x=get_reading_time(data, reading_speed=reading_speed, filters=[['status', '=', 1]]),  # archived
        name='Archived articles',
    ))
    fig.update_layout(
        title_text='Reading Time Distribution',  # title of plot
        xaxis_title_text=f'Estimated reading time (minutes) with reading speed = {reading_speed} wpm',
        yaxis_title_text='Number of articles',
        barmode='stack'  # The two histograms are drawn on top of another
    )
    return fig


def get_reading_time_needed(reading_speed: int) -> str:
    total_minutes = int(sum(get_reading_time(data, reading_speed=reading_speed, filters=[['status', '=', 0]])))
    days, hours, minutes = int(int(total_minutes/24)/60), int(total_minutes/60) % 24, total_minutes % 60
    ans = ''
    if days > 0:
        ans += f' {days} days'
    if hours > 0:
        ans += f' {hours} hours'
    if minutes > 0:
        ans += f' {minutes} minutes'
    return html.Div([
        html.H3(children='Total reading time needed', className='center-text'),
        html.Div(children=ans, className='center-text highlight'),
    ])


@app.callback(
    [Output(component_id='reading-time', component_property='figure'),
     Output(component_id='reading-time-needed', component_property='children')],
    [Input(component_id='reading-speed', component_property='value')]
)
def update_reading_time_components(reading_speed: int) -> Tuple[go.Figure, str]:
    return (get_reading_time_chart(reading_speed),
            get_reading_time_needed(reading_speed))


def reading_time_plot(data: List[Dict]) -> html.Div:
    max_reading_speed = DEFAULT_READING_SPEED * 3
    return html.Div([
        html.H3(children='Reading speed (wpm)', className='center-text'),
        dcc.Slider(
            id='reading-speed',
            marks={i: str(i) for i in range(100, max_reading_speed, 100)},
            min=1, max=max_reading_speed, step=10, value=DEFAULT_READING_SPEED
        ),
        html.Div(id='reading-time-needed', children=''),
        dcc.Graph(id='reading-time', figure=go.Figure()),  # figure will be updated by update_reading_time_components()
    ])


# -------------------- Domain -------------------- #
def domain_counts_plot(data: List[Dict], limit: int = 20) -> dcc.Graph:
    top_pairs = list(get_domain_counts(data).items())  # both unread + archived
    top_pairs.sort(key=lambda p: -p[1])  # sort desc by count
    top_pairs = top_pairs[:limit]  # display top items only
    top_pairs.reverse()  # because px.bar display the items in a reversed order
    top_domains = [p[0] for p in top_pairs]
    unread_domain_cnts = get_domain_counts(data, filters=[['status', '=', 0]])
    archived_domain_cnts = get_domain_counts(data, filters=[['status', '=', 1]])
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[unread_domain_cnts.get(d, 0) for d in top_domains],
        y=top_domains,
        name='Unread articles',
        orientation='h',
    ))
    fig.add_trace(go.Bar(
        x=[archived_domain_cnts.get(d, 0) for d in top_domains],
        y=top_domains,
        name='Archived articles',
        orientation='h',
    ))
    fig.update_layout(
        title_text='Top Domains',
        barmode='stack',
        yaxis=dict(tickmode='linear'),  # to show ALL labels
    )
    return dcc.Graph(id='domain-counts', figure=fig)


def language_counts_plot(data: List[Dict]) -> dcc.Graph:
    pairs = list(get_language_counts(data).items())
    fig = go.Figure(
        data=[
            go.Pie(
                labels=[p[0] for p in pairs],
                values=[p[1] for p in pairs],
            ),
        ],
        layout_title_text="Languages",
    )
    return dcc.Graph(id='language-counts', figure=fig)


def favorite_count_plot(data: List[Dict]) -> html.Div:
    res = get_favorite_count(data)
    return html.Div(
        [
            html.H2(children='Favorite', className='center-text'),
            html.H2(
                children=f"{res['count']} articles ({'%.2f' % (100.0 * res['percent'])} %)",
                className='center-text highlight',
            )
        ],
        className='favorite-div',
    )


app.title = "Pocket Stats"
app.layout = html.Div(style={}, children=[
    word_cloud_plot(data),
    articles_over_time_plot(data),
    plot_two_columns(word_counts_plot(data), reading_time_plot(data)),
    domain_counts_plot(data),
    plot_two_columns(language_counts_plot(data), favorite_count_plot(data)),
])
