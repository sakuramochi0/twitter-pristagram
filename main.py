import re
import logging
import json
from tweepy import OAuthHandler, API, TweepError
import requests
import yaml
from sqlalchemy import create_engine, Column, Boolean, String
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class Media(Base):
    __tablename__ = 'media'
    id = Column(String, primary_key=True)
    tweeted = Column(Boolean, default=False)


def make_twitter_api():
    with open('credentials.yaml') as f:
        credentials = yaml.load(f)
    auth = OAuthHandler(
        consumer_key=credentials['twitter_consumer_key'],
        consumer_secret=credentials['twitter_consumer_secret'],
    )
    auth.set_access_token(
        key=credentials['twitter_access_token'],
        secret=credentials['twitter_access_token_secret'],
    )
    return API(auth)


def decode_json_string(string):
    string += '"' # needed by json function
    decoded_string, _ = json.decoder.scanstring(string, 0)
    return decoded_string


def parse_name_and_ids(screen_name: str) -> [str]:
    url = 'https://www.instagram.com/{user_name}/'.format(user_name=screen_name)
    r = requests.get(url)
    if not r.ok:
        return (None, None)
    ids = re.findall(r'"code": ?"([^"]+)"', r.text)
    full_name = re.search(r'"full_name": ?"([^"]+)"', r.text).group(1)
    full_name = decode_json_string(full_name)
    return (full_name, ids)


def tweet(name :str, screen_name: str, id: str) -> None:
    engine = create_engine(settings['database_path'])
    Session = sessionmaker()
    session = Session(bind=engine)

    media = session.query(Media).filter(Media.id == id).first()
    tweeted = (media is not None) and (media.tweeted is True)
    if not media:
        media = Media(id=id)
        session.add(media)
        session.commit()

    if not tweeted:
        url = 'https://instagram.com/p/{id}'.format(id=id)
        status = '{name} ({screen_name})\n{url}'.format(
            name=name, screen_name=screen_name, url=url)
        try:
            api.update_status(status=status)
            logger.info('tweeted: {}'.format(status))
            session.query(Media).filter(Media.id == id).update({'tweeted': True})
            session.commit()
        except TweepError as e:
            logger.error('TweepError: {}'.format(e))


if __name__ == '__main__':
    with open('settings.yaml') as f:
        settings = yaml.load(f)
    api = make_twitter_api()
    engine = create_engine(settings['database_path'])
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('twitter_prism_gram')
    for screen_name in settings['screen_names']:
        logger.info('fetching user: {}'.format(screen_name))
        name, ids = parse_name_and_ids(screen_name)
        if name == None and ids == None:
            logger.error('not found: {}'.format(screen_name))
            continue
        logger.info('ids: {}'.format(ids))
        for id in reversed(ids):
            tweet(name, screen_name, id)
