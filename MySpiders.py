from scrapy.spider import BaseSpider
from scrapy.selector import HtmlXPathSelector
from items import TvShowItem

class TvShowSpider(BaseSpider): 
    
    name = 'my_spider'    
    allowed_domains = ["tvguide.co.uk"]
    
    def __init__(self, *args, **kwargs): 
      super(TvShowSpider, self).__init__(*args, **kwargs) 
      
      self.start_urls = [kwargs.get('start_url')] 

    def parse(self, response):
        hxs = HtmlXPathSelector(response)
        sites = hxs.select('//tr')
        items = []
        for site in sites:
            channel = site.select('td/b/a/font/text()').extract()
            shows = site.select('td/a/@qt-title').extract()
            for show in shows:
                if '-' in show:
                    item = TvShowItem()
                    if len(channel) == 0:
                        item['channel'] = items[-1]['channel']
                    else:
                        item['channel'] = channel[0]    
                    item['show'] = " ".join(show.split()[1:])
                    item['time'] = " ".join(show.split()[:1]).split('-')[0]
                    items.append(item)           
        return items