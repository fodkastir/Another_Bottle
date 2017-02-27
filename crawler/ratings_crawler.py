import pymysql
import re
import urllib 
from urllib.request import urlopen, Request
from bs4 import BeautifulSoup
from time import sleep
from tqdm import tqdm

def get_conn(db_info):
    conn = pymysql.connect(host=db_info['HOST'],
                           port=db_info['PORT'],
                           user=db_info['USER'],
                           passwd=db_info['PASSWD'],
                           db=db_info['DB'])
    conn.set_charset('utf8')
    return conn

def init_cur(conn):
    cur = conn.cursor()
    cur.execute('SET NAMES utf8;')
    cur.execute('SET CHARACTER SET utf8;')
    cur.execute('SET character_set_connection=utf8;')
    return cur

def get_stylelist ():
    url = 'https://www.beeradvocate.com/beer/style/'
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urlopen(req).read()
    soup = BeautifulSoup(response,"lxml")
    style_list = []
    for soup in soup.findAll('a'):
        try:
            if 'style' in str(soup['href']):
                style_list.append((soup.text, soup['href']))
        except:
            continue
    return style_list [2:-1]

def get_bottlelist (style_link):
    url = 'https://www.beeradvocate.com' + style_link
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urlopen(req).read()
    bottle_num = int(re.findall(b'out of\s(\d*)\)', response)[0])
    bottle_list = [] 
    for start in range(0,bottle_num,50):
        bottles = []
        url = 'https://www.beeradvocate.com' + style_link + '?sort=revsD&start={start}'.format(start=start)
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urlopen(req)
        soup = BeautifulSoup(response.read(),"lxml")
        for soup in soup.findAll('a'):
            try:
                if 'profile' in str(soup['href']) and 'bros' not in str(soup['href']):
                    bottles.append((soup.text, soup['href']))
            except:
                continue
        bottle_list += bottles
    return [bottle for bottle in bottle_list if len(bottle[1].split('/')) == 6]

def get_bottleinfo (bottle_link):
    
    url = 'https://www.beeradvocate.com' + bottle_link
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urlopen(req).read()
    soup = BeautifulSoup(response,"lxml")
    abv = float(re.findall(b'(\d\.\d\d)%', response)[0])
    rating_num = int(re.findall(b'"ba-reviews">([\d,]*?)</span>', response)[0].decode('UTF-8').replace(',',''))
    pattern = re.compile(b'Description:</b>\n\t\t<br>\n\t\t([A-Za-z\s\w\W.]*?)<br><br>Added')
    note = BeautifulSoup(re.findall(pattern, response)[0],"lxml").text.replace('"',"'")
    beer_name, brewer, source = soup.title.text.split(' | ')
    beer_name = beer_name.replace('"',"'")
    
    return abv, note, rating_num, brewer, source

def get_ratings(link, bottle_name, source, start, brewer):
    
    url = 'https://www.beeradvocate.com' + link + '?sort=revsD&start={start}'.format(start=start)
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urlopen(req).read()
    pattern = re.compile(b'(look\:[\s\S]+?\d)</span><br><br>[\s\S]+?"username">([\s\S]+?)</a>\,')
    
    return [(source, soup[1], bottle_name, brewer, *re.findall(b'[\d.]+',soup[0])) for soup in re.findall(pattern, response) if len(soup[1]) < 50]

def main (db_info):
    conn = get_conn(db_info)
    cur = init_cur(conn)
    style_list = get_stylelist ()
    for style in tqdm(style_list): 
        bottle_list = get_bottlelist (style[1])
        for bottle in tqdm(bottle_list):
            bottle_name = bottle[0]
            abv, note, rating_num, brewer, source = get_bottleinfo(bottle[1])
            query = """INSERT INTO beer_info 
                        VALUES ("{source}", "{beer_name}","{brewer}","{style}",{abv},"{note}")""".format(source=source,beer_name=bottle[0],brewer=brewer,style=style[0],abv=abv,note=note)
            cur.execute(query)
            conn.commit()
            
            if rating_num < 10:break
            
            for start in tqdm(range(0,rating_num,25)):
                result = get_ratings(bottle[1], bottle[0], source, start, brewer)
                cur.executemany(
                    """INSERT INTO ratings (source, user_name, beer_name, brewer, look, smell, taste, feel, overall)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",result)
                conn.commit()
    conn.close()

db_info = {'HOST':'yen-6740db.czewfafbu0y5.us-east-1.rds.amazonaws.com',
           'PORT':3306,
           'USER':'fodkastir',
           'PASSWD':'fodka1234stir',
           'DB':'beer_db',}

if __name__ == '__main__':
    main (db_info) 