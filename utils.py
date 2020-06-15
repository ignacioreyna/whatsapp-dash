import re
import datetime
import pandas as pd
pd.options.mode.chained_assignment = None


labels_dict = dict(year=u'Año',
                   month='Mes',
                   day='Dia del mes',
                   hour='Hora del dia',
                   dayofweek='Dia de la semana',
                   weekofyear=u'Semana del año',
                   quarter='Trimestre',
                   year_week=u'Año-semana',
                   year_month=u'Año-mes'
                   )

# In some cases, whatsapp exports chats with a trailing comma in the dates.
def clean_file(filename):
    # regex that captures commas in strings like mm/dd/yy,
    trailing_comma = r"(?<=\/[0-9]{2}),"
    with open(filename) as f:
        file_str = f.read()
        file_str = re.sub(trailing_comma, '', file_str)
    with open(filename, "w") as f:
        f.write(file_str)

def clean_stringIO(content):
  trailing_comma = r"(?<=\/[0-9]{2}),"
  file_str = re.sub(trailing_comma, '', content)
  return file_str

def read_file(filename):
    """Reads the file and return as as stripped list"""
    with open(filename) as file:
        fr = file.readlines()
        file_stripped = [line.strip() for line in fr]
        return file_stripped
      
def read_stringio(content):
  content = clean_stringIO(content)
  content_stripped = [line.strip() for line in content.split('\n')]
  return content_stripped

def create_df(stripped_data):
    """Returns df with cols date and msg"""
    start_regex = r"(?<=\d{2}:\d{2}) - "  # regex to split only strings like HH:MM -
    dates = []
    msgs = []
    for line in stripped_data:
        if " - " in line:
            # maxsplit=1 so we dont split in case it was inside a message
            line_splitted = re.split(start_regex, line, 1)
            if len(line_splitted) == 2:
              dates.append("/".join([x.zfill(2)
                                    for x in line_splitted[0].split("/")]))
              msg = line_splitted[1]
              msgs.append(msg)
    df = pd.DataFrame(data=[dates, msgs]).T
    df.columns = ["date", "msg"]
    return df


def add_msg_author(df):
    '''Adds msg author and deletes msgs without author'''
    df = df[df["msg"].str.contains(":")]
    # maxsplit=1 so we dont split in case it was inside a message
    df[["author", "msg"]] = df.msg.str.split(": ", 1, expand=True)
    
    #TODO remove this specific replace
    df["author"] = df["author"].str.replace(
        "\+54 9 11 2871-3647", "Eric Villadeza")  # Only for lospi.txt
    df["author"] = df["author"].str.replace(
        "\+54 9 11 4191-0068", "Herni Beres")
    #TODO remove this specific replace
    
    return df.dropna()


def add_date_info(df):
    # pd.to_datetime(df["date"], format=date_format)
    
    L = ['year', 'month', 'day', 'hour', 'weekofyear', 'quarter']
# define generator expression of series, one for each attribute
    date_gen = (getattr(df.date.dt, i).rename(i) for i in L)
# concatenate results and join to original dataframe
    df = df.join(pd.concat(date_gen, axis=1))
    df["dayofweek"] = df["date"].dt.day_name()
    df["year_week"] = df["date"].dt.strftime('%y-%V')
    df["year_month"] = df["date"].dt.strftime('%y-%m')
    return df
  

def add_started_conv(df):
    df["tt_prev"] = (df["date"]-df["date"].shift(1)).astype('timedelta64[h]')
    df["starting"] = df["tt_prev"] > 6
    df["days_to_prev_msg"] = df["tt_prev"] // 24
    df = df.drop("tt_prev", axis=1)
    return df


def add_words_by_msg(df):
    df["words"] = df["msg"].str.count(" ") + 1
    return df


def get_df_from_filename(filename):
    clean_file(filename)
    df = create_df(read_file(filename))
    df = add_msg_author(df)
    df = add_words_by_msg(df)
    # df = add_date_info(df)
    return df
  
def get_df_from_content(content):
  df = create_df(read_stringio(content))
  df = add_msg_author(df)
  df = add_words_by_msg(df)
  # df = add_date_info(df)
  return df


def add_date_metrics(df):
  df = add_date_info(df)
  # df = add_started_conv(df)
  return df

def get_df_for_plotting(df, x, y, hue, is_grouped=False, agg_op='count', zfill=True):
  '''
Functionality to transform dataframe into plotly required format.

Parameters
----------
    df : pandas.DataFrame
        Base dataframe. It can be groupped.
    x : str
        Column that will represent x axis in the plot
    y : str
        Column that will represent y axis in the plot
    hue : str
        Column that will be used to group colors in the plot
    is_grouped : bool, default False
        Is df already groupped?
    agg_op : str, default 'count'
        How to aggregate df after groupping
    zfill : bool, default True
        Fill NaN with zeroes

Returns:
    pandas.DataFrame: the transformed df ready to be plotted
  '''
  if not isinstance(df, pd.DataFrame):
    raise ValueError('df should be a valid pandas.DataFrame')
  if not x or not isinstance(x, str):
    raise ValueError('x value should be a column present in the dataframe')
  if not y or not isinstance(y, str):
    raise ValueError('y value should be a column present in the dataframe')

  df = df.copy()
  cols = [x, y] if not hue else [x, hue, y]
  df = df.reset_index()[cols]

  new_cols = sorted(list(set(df[x])))
  new_index = sorted(list(set(df[hue]))) if hue else list(range(1))
  groupping_cols = cols.copy()
  groupping_cols.remove(y)

  if not is_grouped:
    df = df.groupby(groupping_cols)
    if not agg_op or not isinstance(agg_op, str):
      raise ValueError('You should specify how to aggregate the ' +
                       'dataframe after groupping with agg_op param')
    else:
      agg = getattr(df, agg_op)
      df = agg()
  else:
    df = df.set_index(groupping_cols)

  trans_df = pd.DataFrame(columns=new_cols, index=new_index)

  if hue:
    for idx in df.index:
      trans_df.at[idx[1], idx[0]] = df.loc[idx][y]
  else:
    for idx in df.index:
      trans_df.at[0, idx] = df.loc[idx][y]
      
  if not hue:
    trans_df.index = [labels_dict[x]]

  return trans_df.fillna(0) if zfill else trans_df




# add_date_info(get_df_from_filename('../Downloads/toto_pbs.txt'), '%d/%m/%y  %H:%M').to_csv('toto_pbs.csv')
