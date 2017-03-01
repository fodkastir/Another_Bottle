import re
import sys
import random
import pymysql
from urllib.error import URLError, HTTPError
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
    conn.set_charset('utf8mb4')
    return conn

def init_cur(conn):
    cur = conn.cursor()
    cur.execute('SET NAMES utf8mb4;')
    cur.execute('SET CHARACTER SET utf8mb4;')
    cur.execute('SET character_set_connection=utf8mb4;')
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

def get_bottlelink (style_link, threshold):
    url = 'https://www.beeradvocate.com' + style_link
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urlopen(req).read()
    bottle_num = int(re.findall(b'out of\s(\d*)\)', response)[0])
    bottle_link = [] 
    for start in range(0,bottle_num,50):
        links = []
        url = 'https://www.beeradvocate.com' + style_link + '?sort=revsD&start={start}'.format(start=start)
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urlopen(req).read()
        soup = BeautifulSoup(response,"lxml")
        if int(re.findall(b'<b>(\d+?)</b>',response)[0]) < threshold : break
        for soup in soup.findAll('a'):
            try:
                if 'profile' in str(soup['href']) and 'bros' not in str(soup['href']):
                    links.append(soup['href'])
            except:
                continue
        bottle_link += links
    return [link for link in bottle_link if len(link.split('/')) == 6]

def get_bottleinfo (bottle_link):
    
    url = 'https://www.beeradvocate.com' + bottle_link
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urlopen(req).read()
    try:abv = float(re.findall(b'(\d\.\d\d)%', response)[0])
    except:abv = 0
    rating_num = int(re.findall(b'"ba-reviews">([\d,]*?)</span>', response)[0].decode('UTF-8').replace(',',''))
    try:note = BeautifulSoup(re.findall(b'Description:([\s\S]*?)Added', response)[0],'html.parser').text.lstrip('\n').lstrip('\t').replace('"',"'")
    except:note = 'No notes at this time.'
    soup = BeautifulSoup(response,"lxml")
    bottle_name, brewer, source = soup.title.text.split(' | ')
    bottle_name = bottle_name.replace('"',"'")
    
    return abv, note, rating_num, brewer, source, bottle_name

def get_ratings(link, bottle_name, source, start, brewer):
    
    headers = [
    'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0; .NET CLR 2.0.50727; .NET CLR 3.0.04506.30; .NET CLR 3.0.04506.648)',
    'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0; .NET CLR 2.0.50727; InfoPath.1',
    'Mozilla/4.0 (compatible; GoogleToolbar 5.0.2124.2070; Windows 6.0; MSIE 8.0.6001.18241)',
    'Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; WOW64; Trident/5.0)',
    'Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; WOW64; Trident/5.0; Sleipnir/2.9.8)',
    ]
    connected = False
    while not connected:
        try:
            url = 'https://www.beeradvocate.com' + link + '?sort=revsD&start={start}'.format(start=start)
            req = Request(url, headers={'User-Agent': random.choice(headers)})
            response = urlopen(req).read()
            pattern = re.compile(b'\>(look\:[\s\S]+?\d)</span><br><br>([\s\S]+?)<br><br><i[\s\S]+?"username">([\s\S]+?)</a>')
            connected = True
        except URLError as err:
            print('Reason: ', err.reason)
            print(url)
            sleep(5)

        except HTTPError as err:
            print('Error code: ', err.code)
            print(url)
            sleep(5)
    
    return [(source, soup[2], bottle_name, brewer, *re.findall(b'[\d.]+',soup[0]), soup[1]) for soup in re.findall(pattern, response)]

def main (db_user, db_pass, interval, threshold):
    db_info = {'HOST':'yen-6740db.czewfafbu0y5.us-east-1.rds.amazonaws.com',
           'PORT':3306,
           'USER':db_user,
           'PASSWD':db_pass,
           'DB':'beer_db',}
    conn = get_conn(db_info)
    cur = init_cur(conn)
    style = get_stylelist ()
    for style in tqdm(style): 
        bottle_link = get_bottlelink (style[1],int(threshold))
        for link in tqdm(bottle_link):
            try:
                abv, note, rating_num, brewer, source, bottle_name = get_bottleinfo(link)
                query = """INSERT INTO beer_info 
                            VALUES ("{source}", "{bottle_name}","{brewer}","{style}",{abv},"{note}")""".format(source=source,bottle_name=bottle_name,brewer=brewer,style=style[0],abv=abv,note=note)
                cur.execute(query)
                conn.commit()
            except:
                print(link)         
            for start in tqdm(range(0,rating_num,25)):
                try:
                    result = get_ratings(link, bottle_name, source, start, brewer)
                    cur.executemany(
                        """INSERT INTO ratings (source, user_name, bottle_name, brewer, look, smell, taste, feel, overall, review)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",result)
                    conn.commit()
                    sleep(int(interval))
                except KeyboardInterrupt:
                    raise
                except:
                    print(link,start)
    conn.close()

if __name__ == '__main__':
    if len(sys.argv) < 4:
        print('please enter db_user, db_pass, request interval and threshold')
    else:
        main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]) 