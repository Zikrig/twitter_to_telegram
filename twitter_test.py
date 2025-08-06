import json
from datetime import datetime, timedelta

from Twitter import Twitter


API_HOST = 'twitter241.p.rapidapi.com'
API_KEY = '34df59c0aemshf4c684e2f49ddc1p12f8b0jsn019a0b39d7f8'


# user = '1570754138648023043'
user = '2455740283'


twitter = Twitter(API_HOST, API_KEY)

id = twitter.get_user_by_username('popcrave')
print(id)

print(twitter.get_user_tweets(int(id['data']), '5', datetime.now()-timedelta(hours=6)))


# with open('twitter_response.json', 'r', encoding='utf-8') as f:
#     data = json.load(f)
    
    
# # Извлеките посты
# posts = twitter.extract(data)
# print(posts)