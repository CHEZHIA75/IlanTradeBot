import pandas as pd
import requests
from bs4 import BeautifulSoup

def get_sp500():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    table = pd.read_html(url)[0]
    return table['Symbol'].tolist()

def get_asx200():
    url = 'https://en.wikipedia.org/wiki/S%26P/ASX_200'
    r = requests.get(url)
    soup = BeautifulSoup(r.content, 'lxml')
    table = soup.find('table', {'class': 'wikitable'})
    df = pd.read_html(str(table))[0]
    return [f"{code}.AX" for code in df['ASX code']]

def get_nifty50():
    url = 'https://en.wikipedia.org/wiki/NIFTY_50'
    table = pd.read_html(url)[1]
    return [f"{code}.NS" for code in table['Symbol']]

