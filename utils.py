import re
import locale
import calendar
import random
import pandas as pd
import pydateinfer as dateinfer

pd.options.mode.chained_assignment = None

showable_dimensions_dict = dict(
    year=u'Año',
    month='Mes',
    day=u'Día del mes',
    hour=u'Hora del día',
    dayofweek=u'Día de la semana',
    weekofyear=u'Semana del año',
    quarter='Trimestre'
)

dimensions_dict = dict(
    year=u'Año',
    month='Mes',
    day=u'Día del mes',
    hour=u'Hora del día',
    dayofweek=u'Día de la semana',
    weekofyear=u'Semana del año',
    quarter='Trimestre',
    year_month='Año - Mes',
    year_day='Año - Dia del mes',
    year_hour='Año - Hora del día',
    year_dayofweek='Año - Día de la semana',
    year_weekofyear='Año - Semana del año',
    year_quarter='Año - Trimestre'
)

metrics_dict = dict(
    msg='Mensajes',
    words='Palabras',
    wpm='Palabras por mensaje',
    starting='Conversaciones iniciadas',
    media='Audios, fotos y videos'
)

metric_agg_op = dict(
    msg='count',
    words='sum',
    wpm='mean',
    starting='sum',
    media='sum'
)


def read_file(filename):
    """Reads the file and return as as stripped list"""
    trailing_comma = r"(?<=\/[0-9]{2}),"
    with open(filename) as file:
        fr = file.readlines()
        file_stripped = [re.sub(trailing_comma, '', line.strip()) for line in fr]
        return file_stripped


def read_stringio(content):
    trailing_comma = r"(?<=\/[0-9]{2}),"
    content = re.sub(trailing_comma, '', content)
    content_stripped = [line.strip() for line in content.split('\n')]
    return content_stripped


def clean_datetime_string(dts):
    date = dts.lower()
    non_breaking_space = '\xa0'
    if non_breaking_space in date:
        date = date.replace(non_breaking_space, ' ')
    if 'p. m.' in date:
        date = date.replace('p. m.', 'PM')
    elif 'a. m.' in date:
        date = date.replace('a. m.', 'AM')
    return date


def create_df(stripped_data):
    """Returns df with cols date and msg"""
    start_regex = r"^\d{1,4}[\/-]\d{1,2}[\/-]\d{1,4} \d{1,2}:\d{1,2}"  # regex to split only strings like date time
    dates = []
    msgs = []
    for line in stripped_data:
        if re.match(start_regex, line):
            # line_splitted = re.split(start_regex, line, 1)
            line_splitted = line.split(' - ', maxsplit=1)
            if len(line_splitted) == 2:
                date = "/".join([x.zfill(2)
                                 for x in
                                 clean_datetime_string(line_splitted[0]).split("/")])

                dates.append(date)
                msg = line_splitted[1]
                msgs.append(msg)
    df = pd.DataFrame({'date': dates, 'msg': msgs})
    return df


def add_msg_author(df):
    '''Adds msg author and deletes msgs without author'''
    df = df[df["msg"].str.contains(":")]
    maxsplit = 1
    df[["author", "msg"]] = df.msg.str.split(": ", maxsplit, expand=True)
    return df.dropna().reset_index()


def add_date_info(df):
    N = len(df)
    sample_dates = [df.date[i] for i in random.sample(range(N), N if N < 50 else 50)]
    dateformat = dateinfer.infer(sample_dates)
    df['date'] = pd.to_datetime(df["date"], format=dateformat)

    L = ['year', 'month', 'day', 'hour', 'weekofyear', 'quarter']
    # define generator expression of series, one for each attribute
    date_gen = (getattr(df.date.dt, i).rename(i) for i in L)
    # concatenate results and join to original dataframe
    df = df.join(pd.concat(date_gen, axis=1))
    df['year_month'] = df['date'].dt.strftime('%Y-%m')
    df['year_day'] = df['date'].dt.strftime('%Y-%d')
    df["year_hour"] = df['date'].dt.strftime('%Y-%H')
    df["year_weekofyear"] = df["date"].dt.strftime('%Y-%V')
    df['year_quarter'] = pd.Series([f'{y}-{q}' for y, q in zip(df.year, df.quarter)])
    df["dayofweek"] = df["date"].dt.weekday
    df['year_dayofweek'] = df['date'].dt.strftime('%Y-%w')

    return df.reset_index(drop=True)


def add_started_conv(df):
    df["tt_prev"] = (df["date"] - df["date"].shift(1)).astype('timedelta64[h]')
    df["starting"] = df["tt_prev"] > 6
    df['starting'] = df.starting.astype(int)
    df = df.drop("tt_prev", axis=1)
    return df


def add_words_by_msg(df):
    df["words"] = df["msg"].str.count(" ") + 1
    return df


def add_media_count(df):
    df['media'] = ((df.msg == '<Multimedia omitido>') | (df.msg == '<Media omitted>')).astype(int)
    return df


def add_date_dimensions(df):
    df = add_date_info(df)
    df = add_started_conv(df)
    return df


def add_dimensions(df):
    df = add_msg_author(df)
    df = add_words_by_msg(df)
    df = add_date_dimensions(df)
    df = add_media_count(df)
    return df


def get_df_from_filename(filename):
    df = create_df(read_file(filename))
    return add_dimensions(df)


def get_df_from_content(content):
    df = create_df(read_stringio(content))
    return add_dimensions(df).drop(columns=['index'])


def put_locale_names(df, x, hue=None):
    day_names = list(map(lambda name: name.capitalize(), filter(lambda name: name != '', calendar.day_name)))
    month_names = list(map(lambda name: name.capitalize(), filter(lambda name: name != '', calendar.month_name)))
    if hue:
        if hue == 'dayofweek':
            df = df.set_index(pd.Series([day_names[dow] for dow in df.index]))
        elif hue == 'year_dayofweek':
            new_index = []
            for c in df.index:
                y, dow = c.split('-')
                new_index.append(f'{y}-{day_names[int(dow)]}')
            df = df.set_index(pd.Series(new_index))
        elif hue == 'month':
            df = df.set_index(pd.Series([month_names[m-1] for m in df.index]))
        elif hue == 'year_month':
            new_index = []
            for c in df.index:
                y, m = c.split('-')
                new_index.append(f'{y}-{month_names[int(m)-1]}')
            df = df.set_index(pd.Series(new_index))

    if x == 'dayofweek':
        df = df.reindex(df.columns, axis=1)
        df.columns = [day_names[dow] for dow in df.columns]
    elif x == 'year_dayofweek':
        df = df.reindex(df.columns, axis=1)
        new_cols = []
        for c in df.columns:
            y, dow = c.split('-')
            new_cols.append(f'{y}-{day_names[int(dow)]}')
        df.columns = new_cols
    elif x == 'month':
        df = df.reindex(df.columns, axis=1)
        df.columns = [month_names[m-1] for m in df.columns]
    elif x == 'year_month':
        df = df.reindex(df.columns, axis=1)
        new_cols = []
        for c in df.columns:
            y, m = c.split('-')
            new_cols.append(f'{y}-{month_names[int(m)-1]}')
        df.columns = new_cols

    return df


def get_df_for_plotting(df, x, y, hue=None, l='es_ES'):
    """
  Functionality to transform dataframe into plotly required format.

  Parameters
  ----------
      df : pandas.DataFrame
          Base dataframe. It can be grouped.
      x : str
          Column that will represent x axis in the plot
      y : str
          Column that will represent y axis in the plot
      hue : str
          Column that will be used to group colors in the plot

  Returns
  -------
      pandas.DataFrame: the transformed df ready to be plotted
    """
    if not isinstance(df, pd.DataFrame):
        raise ValueError('df should be a valid pandas.DataFrame')
    if not x or not isinstance(x, str):
        raise ValueError('x value should be a column present in the dataframe')
    if not y or not isinstance(y, str):
        raise ValueError('y value should be a column present in the dataframe')

    locale.setlocale(locale.LC_ALL, l)

    if y in metric_agg_op:
        agg_op = metric_agg_op[y]
    else:
        raise ValueError('This metric is not supported yet')

    y = 'words' if y == 'wpm' else y

    df = df.copy()
    cols = [x, y] if not hue else [x, hue, y]
    df = df.reset_index()[cols]

    new_cols = sorted(list(set(df[x])))
    new_index = sorted(list(set(df[hue]))) if hue else list(range(1))
    grouping_cols = cols.copy()
    grouping_cols.remove(y)

    df = df.groupby(grouping_cols)
    agg = getattr(df, agg_op)
    df = agg()

    trans_df = pd.DataFrame(columns=new_cols, index=new_index)

    if hue:
        for idx in df.index:
            trans_df.at[idx[1], idx[0]] = df.loc[idx][y]
    else:
        for idx in df.index:
            trans_df.at[0, idx] = df.loc[idx][y]
        trans_df.index = [dimensions_dict[x]]

    trans_df = put_locale_names(trans_df, x, hue)

    return trans_df.fillna(0)
