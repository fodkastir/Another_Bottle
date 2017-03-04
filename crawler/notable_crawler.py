import re
import sys
import pymysql
from urllib.request import urlopen, Request

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

def find_notable ():

    url = 'https://www.beeradvocate.com/members/?sort=beers'
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    response = urlopen(req).read()
    pattern = re.compile(b'\>([\d,]+?)</div>[\s\S]+?name"><b>([\s\S]+?)</b>')
    
    return [(res[1], int(res[0].decode('UTF-8').replace(',',''))) for res in re.findall(pattern, response)]

def main (db_user, db_pass):
    db_info = {'HOST':'yen-6740db.czewfafbu0y5.us-east-1.rds.amazonaws.com',
           'PORT':3306,
           'USER':db_user,
           'PASSWD':db_pass,
           'DB':'beer_db',}
    conn = get_conn(db_info)
    cur = init_cur(conn)
    cur.executemany(
        """INSERT INTO notable (user_name, review_number)
           VALUES (%s, %s)""",find_notable ())
    conn.commit()
    conn.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('please enter db_user and db_pass')
    else:
        main(sys.argv[1], sys.argv[2]) 