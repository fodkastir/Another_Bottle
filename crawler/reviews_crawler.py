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

def find_notable ():
    
    url = 'https://www.beeradvocate.com/members/?sort=beers'
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urlopen(req)
    soup = BeautifulSoup(response.read(),"lxml")
    user_list = [node.findAll(text=True) for node in soup.findAll('a', { 'class':'username'})]
    user_list = [user[0] for user in user_list if user != []]
    user_list = user_list[0:user_list.index('larryi86')+1]
   
    return user_list

def get_review_link (user):
    
    url = 'https://www.beeradvocate.com/user/beers/?start=0&&ba={user}'.format(user=user)
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urlopen(req).read()
    rev_num = int(re.findall(b'Ratings:\s([\d]*?)\s', response)[0])
    
    review_list = []
    for start in range(0,rev_num,50):
        reviews = []
        url = 'https://www.beeradvocate.com/user/beers/?start={start}&ba={user}&order=dateD&view=R'.format(user=user, start=start)
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urlopen(req)
        soup = BeautifulSoup(response.read(),"lxml")
        for a in soup.findAll('a'):
            try:
                if '#review' in a['href']:
                    reviews.append(a['href'])
            except:continue
        check = soup.findAll('i',{'class':["fa fa-check", "fa fa-file-text-o"]})[2:]
        review_list += [review for review,check in zip(reviews, check) if 'text' in str(check)]
    return review_list

def get_review (link):
    
    url = 'https://www.beeradvocate.com/' + link
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urlopen(req).read()
    soup = BeautifulSoup(response,"lxml")
    beer_name, brewer, source = soup.title.text.split(' | ')
    review = BeautifulSoup(re.findall(b'[\d%]+</span><br><br>([\s\S]*?)characters', response)[0],"lxml").text
    
    return beer_name, source, review, brewer

def main (db_info):
    conn = get_conn(db_info)
    cur = init_cur(conn)
    user_list = find_notable()
    for user in tqdm(user_list[243:244]):
        review_link = get_review_link(user)
        for link in tqdm(review_link):
            connected = False
            while not connected:
                try:
                    beer_name, source, review, brewer = get_review (link)
                    connected = True
                except urllib.error.URLError as err:
                    print(err.reason)
                    print(link)
                    sleep(60)
            review = review.replace('"',"'")
            beer_name = beer_name.replace('"',"'")
            query = """INSERT INTO beer_reviews 
                    VALUES ("{source}", "{user_name}","{beer_name}","{brewer}","{review}")""".format(source=source,user_name=user,review=review,beer_name=beer_name,brewer=brewer)
            cur.execute(query)
            conn.commit()
    conn.close()

db_info = {'HOST':'yen-6740db.czewfafbu0y5.us-east-1.rds.amazonaws.com',
           'PORT':3306,
           'USER':'fodkastir',
           'PASSWD':'fodka1234stir',
           'DB':'beer_db',}

if __name__ == '__main__':
    main (db_info) 