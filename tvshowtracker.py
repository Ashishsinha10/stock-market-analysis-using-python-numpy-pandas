'''
UK TV show tracker.
Extracts information from tvguide.co.uk and for user selected shows
sends a reminder to the user 10 minutes (or so) before the show 
commences
Uses postgresql for the database and scrapy for retrieving the data
from the webpage.  
Mailing is set up for gmail currently.
'''

import datetime
import time 
from twisted.internet import reactor
from scrapy.crawler import Crawler
import scrapy.settings.default_settings as default_settings
from scrapy.settings import Settings
from scrapy import signals
import MySpiders
import smtplib
import sys
import json
from multiprocessing import Process
import psycopg2
class Database(object):
    
    def __init__(self):
        #init connection and cursor
        try:
            self.conn = psycopg2.connect("dbname='ashish' user='postgres' host='localhost' password='root'")
        except psycopg2.DatabaseError:
            print('Error %s')
            self.cur = self.conn.cursor()
    
    def update(self):
        #update the table
        data = self._yield_data()
        for item in data:
            self.cur.execute("INSERT INTO shows VALUES (%(show)s, %(channel)s, %(time)s)", item)
            self.conn.commit()

    def query(self, show):
        self.cur.execute("SELECT * FROM shows WHERE show=%(show)s", {'show':show})
        return self.cur.fetchall()
    
    def clear(self):
        self.cur.execute("DELETE FROM shows")
        self.conn.commit()
                    
    def _yield_data(self):
        with open('my_spider_items.json') as f:
            my_dict = json.load(f)
            for item in my_dict:
                yield item
      
class WebCrawler():
    
    def __init__(self):
        default_settings.ITEM_PIPELINES = 'pipelines.JsonExportPipeline'
        self.crawler = Crawler(Settings())
        self.crawler.signals.connect(reactor.stop, signal=signals.spider_closed)
        self.crawler.configure()
            
    def _crawl(self, url):
        spider = MySpiders.TvShowSpider(start_url=url)
        self.crawler.crawl(spider)
        self.crawler.start()
        reactor.run()
        
    def run(self, url):
        p = Process(target=self._crawl, args=[url])
        p.start()
        p.join()
        
class Mailer(object):
    
    def __init__(self, fromaddr,toadrrs,username,password):
        self.fromaddr = fromaddr
        self.toaddrs  = toadrrs 
        self.username = username 
        self.password = password
        self.subject = 'Show Reminder!'
        
    def send_mail(self, body):
        server = smtplib.SMTP('smtp.gmail.com:587')  
        server.starttls()  
        server.login(self.username,self.password)  
        msg = 'Subject: %s\n\n%s' % (self.subject, body)
        server.sendmail(self.fromaddr, self.toaddrs, msg)  
        server.quit()  
        
class ChannelTracker(object):
    
    def __init__(self, database, webcrawler, shows):
        self.database = database 
        self.webcrawler = webcrawler
        self.shows = shows 
        
    def update_channels(self, now):
        #clear db
        self.database.clear()
        
        #crawl and insert crawled data into db
        for url in self._get_urls(now):
            self.webcrawler.run(url=url) 
            self.database.update()
                             
    def get_show_list(self):
        show_list = []
        if len(self.shows) != 0:
            for selected_show in self.shows:
                are_shows = self.database.query(selected_show)
                if are_shows != None:
                    for show in are_shows:
                        show_list.append(show)
        
        #remove duplicates
        show_list = self._remove_duplicates(show_list) 
        
        #sort list by time
        show_list = sorted(show_list, key = lambda x : (x[2]))           
        
        #return reversed list so earliest time is last
        show_list.reverse()
        return show_list
    
    def _get_urls(self, now):
        url_list = []
        base_url = 'http://www.tvguide.co.uk/?systemid=&thistime=%s&thisday=%s&ProgrammeTypeID=&gridSpan=06:00&catColor='
        
        #define the urls for the day
        date = str(now.month) + '/' + str(now.day) + '/' + str(now.year)
        for hour in ['1','7','13','19']:
            url_list.append(base_url % (hour,date))
        return url_list
                    
    def _remove_duplicates(self, show_list):
        return list(set(show_list))
                                                 
def main():

    #parse the user info.  
    mail_info = input("Enter email address to recieve notifications (only works with gmail): ")
    passwd =input("Enter email account password: ")
    shows = []
    while True:
        user_input = input("Enter shows to track.  If all shows to track entered, then enter 'n': ")
        if user_input == "n":
            break
        else:
            shows.append(user_input)

    #generate objects
    database = Database()
    webcrawler = WebCrawler()
    mailer = Mailer(mail_info, mail_info, mail_info, passwd)
    tracker = ChannelTracker(database, webcrawler, shows)
    
    #preset current day
    current_day = datetime.datetime.now().day 
    
    #set time delta for show reminders
    d = datetime.timedelta(minutes=10)
    
    #iterate
    while True:
                
        #populate database
        tracker.update_channels(datetime.datetime.now())
        
        #extract shows from database
        show_list = tracker.get_show_list()
        
        #...and check for upcoming shows
        while datetime.datetime.now().day == current_day:
            
            #see if shows left in show_list
            if len(show_list)==0:
                
                #if not sleep for an hour and then continue loop
                time.sleep(3600)
                continue
                
            #get next show
            next_show = show_list.pop()
            show_time = datetime.datetime.now().replace(hour=next_show[2].hour, minute=next_show[2].minute)
            
            while True:
                now = datetime.datetime.now()
                #check to see if show missed
                if show_time < now:
                    break
                #Check to see if show in less than 10 mins:
                if show_time - now < d:
                    msg = next_show[0] + ' is starting at ' + str(next_show[2]) + ' on ' + next_show[1]  
                    mailer.send_mail(body=msg)
                    break
                #check for show every five minutes
                time.sleep(180)
                
        #update day
        current_day = datetime.datetime.now().day
            
        #TODO implement a process to kill the app

if __name__ == '__main__':
    sys.exit(main())