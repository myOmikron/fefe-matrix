import asyncio
import logging

import feedparser
from hopfenmatrix.matrix import MatrixBot
from sqlalchemy import create_engine, String, Column, Integer, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


async def rss_fetcher(matrix: MatrixBot, db):
    while True:
        try:
            feed = feedparser.parse("https://blog.fefe.de/rss.xml?html")
            for i in range(len(feed.entries)-1, -1, -1):
                entry = feed.entries[i]
                if len(db.query(Item).filter_by(item_id=entry.id).all()) == 0:
                    db.add(Item(item_id=entry.id))
                    db.commit()
                    for room in [x.room_id for x in db.query(Room).all()]:
                        message = f"{entry.summary}"
                        await matrix.send_message(message, room_id=room)
        except Exception as err:
            logger.error(err)
        await asyncio.sleep(60)


def subscribe_command(db):
    async def callback(matrix: MatrixBot, room, event):
        if event.sender == matrix.client.user:
            return
        rooms = db.query(Room).filter_by(room_id=room.room_id).all()
        if len(rooms) == 0:
            db.add(Room(room_id=room.room_id))
            db.commit()
            await matrix.send_message("You have subscribed successfully!", room.room_id)
            logger.info(f"Room {room.room_id} has subscribed.")
        else:
            await matrix.send_message("You have already subscribed!", room.room_id)
    return callback


def unsubscribe_command(db):
    async def callback(matrix: MatrixBot, room, event):
        if event.sender == matrix.client.user:
            return
        rooms = db.query(Room).filter_by(room_id=room.room_id).all()
        if len(rooms) > 0:
            db.delete(rooms[0])
            db.commit()
            await matrix.send_message("You have successfully unsubscribed", room.room_id)
            logger.info(f"Room {room.room_id} has unsubscribed.")
        else:
            await matrix.send_message("You haven't subscribed yet!", room.room_id)
    return callback


async def main(db):
    matrix = MatrixBot(display_name="Fefe Bot")
    matrix.set_auto_join()
    matrix.register_command(subscribe_command(db), accepted_aliases=["sub", "subscribe"])
    matrix.register_command(unsubscribe_command(db), accepted_aliases=["unsub", "unsubscribe"])
    matrix.add_coroutine_callback(rss_fetcher(matrix, db))
    await matrix.start_bot()


if __name__ == '__main__':
    Base = declarative_base()

    class Item(Base):
        __tablename__ = "item"
        id = Column(Integer, autoincrement=True, unique=True, primary_key=True)
        item_id = Column(String, unique=True)

    class Room(Base):
        __tablename__ = "room"
        room_id = Column(String, unique=True, primary_key=True)

    engine = create_engine(f"sqlite:///fefe.sqlite3")
    Base.metadata.create_all(engine)
    DBSession = sessionmaker(bind=engine)
    session = DBSession()

    asyncio.get_event_loop().run_until_complete(main(session))
